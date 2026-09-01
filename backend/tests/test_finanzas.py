import csv
import io
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base, FinanceMovement
from services import finanzas


def canonical_csv(*rows):
    rows = rows or ({},)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=finanzas.CANONICAL_COLUMNS)
    writer.writeheader()
    for row in rows:
        base = {column: "" for column in finanzas.CANONICAL_COLUMNS}
        base.update({
            "id_movimiento": "mov-1", "empresa": "TLA", "banco": "AMEX",
            "tipo_cuenta": "Tarjeta", "naturaleza_cuenta": "Crédito", "moneda": "MXN",
            "fecha_operacion": "2026-08-01", "descripcion_original": "SERVICIO NUBE",
            "cargo": "100.00", "abono": "0", "importe_neto": "-100.00",
            "periodo_estado": "2026-08", "archivo_fuente": "estado.csv",
        })
        base.update(row)
        writer.writerow(base)
    return output.getvalue().encode("utf-8-sig")


class FinanceModuleTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        self.temp = tempfile.TemporaryDirectory()
        self.source = Path(self.temp.name) / "Amex_historico.csv"
        self.session_patch = patch.object(finanzas, "SessionLocal", self.Session)
        self.paths_patch = patch.dict(finanzas.FINANCE_SOURCE_PATHS, {"tla_amex": self.source}, clear=True)
        self.file_ids_patch = patch.dict(finanzas.FINANCE_SOURCE_FILE_IDS, {"tla_amex": ""}, clear=True)
        self.session_patch.start(); self.paths_patch.start(); self.file_ids_patch.start()

    def tearDown(self):
        self.file_ids_patch.stop(); self.paths_patch.stop(); self.session_patch.stop(); self.temp.cleanup()

    def test_parser_preserves_canonical_sign_convention(self):
        row = finanzas.parse_canonical_csv(canonical_csv())[0]
        self.assertEqual(row["operation_date"], date(2026, 8, 1))
        self.assertEqual(float(row["net_amount"]), -100.0)
        self.assertTrue(row["account_nature"], "Crédito")

    def test_parser_rejects_duplicate_stable_ids(self):
        with self.assertRaisesRegex(ValueError, "duplicado"):
            finanzas.parse_canonical_csv(canonical_csv({}, {}))

    def test_source_sync_is_idempotent_and_preserves_enrichment(self):
        self.source.write_bytes(canonical_csv())
        first = finanzas.sync_source("tla_amex")
        self.assertEqual(first["row_count"], 1)
        db = self.Session()
        movement = db.query(FinanceMovement).one()
        movement.category_override = "Software"; db.commit(); db.close()

        second = finanzas.sync_source("tla_amex", force=True)
        db = self.Session()
        rows = db.query(FinanceMovement).all()
        self.assertEqual(second["row_count"], 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].category_override, "Software")
        db.close()

    def test_source_sync_removes_rows_deleted_from_canonical_history(self):
        self.source.write_bytes(canonical_csv({}, {"id_movimiento": "mov-2"}))
        finanzas.sync_source("tla_amex")
        self.source.write_bytes(canonical_csv())
        finanzas.sync_source("tla_amex", force=True)
        db = self.Session()
        self.assertEqual([row.external_id for row in db.query(FinanceMovement).all()], ["mov-1"])
        db.close()

    def test_missing_source_is_reported_without_fake_data(self):
        result = finanzas.sync_source("tla_amex")
        self.assertFalse(result["available"])
        db = self.Session()
        self.assertEqual(db.query(FinanceMovement).count(), 0)
        db.close()

    def test_overview_and_movements_honor_bank_and_date_scope(self):
        self.source.write_bytes(canonical_csv(
            {"id_movimiento": "amex-aug", "banco": "AMEX", "fecha_operacion": "2026-08-01", "importe_neto": "100.00", "cargo": "0", "abono": "100.00"},
            {"id_movimiento": "bbva-aug", "banco": "BBVA", "fecha_operacion": "2026-08-15", "importe_neto": "200.00", "cargo": "0", "abono": "200.00"},
            {"id_movimiento": "amex-sep", "banco": "AMEX", "fecha_operacion": "2026-09-01", "importe_neto": "300.00", "cargo": "0", "abono": "300.00"},
        ))
        finanzas.sync_source("tla_amex")

        result = finanzas.overview("TLA", "AMEX", date(2026, 8, 1), date(2026, 8, 31))
        self.assertEqual(result["monthly"], [{"month": "2026-08", "entries": 100.0, "exits": 0.0, "net": 100.0}])
        self.assertEqual(result["kpis"]["entries_month"], 100.0)

        movements = finanzas.list_movements(
            company="TLA", search="", category="", bank="AMEX",
            start_date=date(2026, 8, 1), end_date=date(2026, 8, 31),
            page=1, page_size=5000, sort="operation_date", direction="desc",
        )
        self.assertEqual(movements["total"], 1)
        self.assertEqual(movements["items"][0]["id_movimiento"], "amex-aug")

    def test_xml_invoice_extracts_cfdi_fields_without_claiming_validation(self):
        xml = b'''<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Fecha="2026-08-01T10:00:00" Total="116.00" Moneda="MXN"><cfdi:Emisor Rfc="AAA010101AAA"/><cfdi:Receptor Rfc="BBB010101BBB"/><cfdi:Complemento><tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" UUID="ABC-123"/></cfdi:Complemento></cfdi:Comprobante>'''
        path = Path(self.temp.name) / "factura.xml"; path.write_bytes(xml)
        result = finanzas._xml_invoice(path)
        self.assertEqual(result["uuid"], "ABC-123")
        self.assertEqual(result["issuer_rfc"], "AAA010101AAA")
        self.assertEqual(float(result["total"]), 116.0)


if __name__ == "__main__":
    unittest.main()
