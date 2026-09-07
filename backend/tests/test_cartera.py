import io
import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook, load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base, Client, Insurer, Policy, Product, User
from services import cartera


def sura_workbook(*rows) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "SURA"
    sheet.append(["Póliza", "Póliza actual", "Contratante", "Prospectador", "Porcentaje", "Inicio de pago"])
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def aarco_axa_workbook(*rows) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    # The production file currently keeps this legacy tab name. Parsing must
    # depend on the Aseguradora header, not on the worksheet title.
    sheet.title = "SURA"
    sheet.append(["Aseguradora", "Póliza", "Póliza actual", "Contratante", "Prospectador", "Porcentaje", "Inicio de pago"])
    for row in rows:
        sheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


class CarteraModuleTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        db = self.Session()
        db.add_all([
            User(id="usr_pamela", name="Pamela", email="pamela@taiico.com", role="management"),
            Insurer(id="sura", name="SURA"),
            Insurer(id="axa", name="AXA"),
            Insurer(id="aarco", name="AARCO"),
            Product(id="prod_sura_gmm", insurer_id="sura", name="SURA GMM", branch="GMM"),
        ])
        db.commit()
        db.close()

    def test_parser_uses_last_repeated_policy_and_normalizes_columns(self):
        rows = cartera.parse_cartera_workbook(sura_workbook(
            (37, "", "", "PRIMERO", 0.5, None),
            (37, "37-A", "Cliente final", "CORRECTO", 0.8, date(2026, 9, 1)),
        ), "SURA")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["policy_number"], "37")
        self.assertEqual(rows[0]["current_policy_number"], "37-A")
        self.assertEqual(rows[0]["prospector"], "CORRECTO")
        self.assertEqual(rows[0]["percentage"], Decimal("0.8"))
        self.assertEqual(rows[0]["payment_start_date"], "2026-09-01")

    def test_sync_creates_missing_records_and_updates_existing_without_erasing_name(self):
        db = self.Session()
        client = Client(full_name="Nombre existente", responsible_user_id="usr_pamela", metadata_json={})
        db.add(client)
        db.flush()
        db.add(Policy(
            policy_number="37", client_id=client.id, insurer_id="sura", product_id="prod_sura_gmm",
            effective_start_date=date(2026, 1, 1), effective_end_date=date(2027, 1, 1),
            premium_amount=0, payment_frequency="annual", responsible_user_id="usr_pamela",
            commission_percentage=0,
        ))
        db.commit()

        result = cartera.sync_cartera_source("sura", contents=sura_workbook(
            (37, 37, "", "ANA", 0.8, None),
            (38, 38, "", "LUIS", 0.5, None),
        ), db=db)

        self.assertEqual(result["updated"], 1)
        self.assertEqual(result["created"], 1)
        policies = {item.policy_number: item for item in db.query(Policy).filter_by(insurer_id="sura").all()}
        self.assertEqual(policies["37"].client.full_name, "Nombre existente")
        self.assertEqual(policies["37"].metadata_json["prospector"], "ANA")
        self.assertEqual(policies["38"].client.full_name, "SURA CLIENT P-38")
        db.close()

    def test_combined_parser_treats_aarco_as_broker_and_accepts_any_carrier(self):
        rows = cartera.parse_cartera_workbook(aarco_axa_workbook(
            ("AXA", "AX-1", "", "Cliente AXA", "ANA", 0.4, None),
            ("AARCO", "AR-1", "", "Cliente AARCO", "LUIS", 0.5, None),
            ("", "SIN-1", "", "Sin aseguradora", "ANA", 0.6, None),
            ("OTRA", "OT-1", "", "Otra", "ANA", 0.7, None),
        ), "aarco_axa")

        self.assertEqual([(row["insurer"], row["carrier"], row["policy_number"]) for row in rows], [
            ("aarco", "AXA", "AX-1"),
            ("aarco", "AARCO", "AR-1"),
            ("aarco", "", "SIN-1"),
            ("aarco", "OTRA", "OT-1"),
        ])

    def test_combined_sync_stores_carrier_metadata_under_aarco_broker(self):
        db = self.Session()
        result = cartera.sync_cartera_source("aarco_axa", contents=aarco_axa_workbook(
            ("AXA", "AX-1", "", "Cliente AXA", "ANA", 0.4, None),
            ("AARCO", "AR-1", "", "Cliente AARCO", "LUIS", 0.5, None),
        ), db=db)

        policies = {policy.policy_number: policy for policy in db.query(Policy).all()}
        self.assertEqual(result["insurer"], "aarco_axa")
        self.assertEqual(result["created"], 2)
        self.assertEqual(policies["AX-1"].insurer_id, "aarco")
        self.assertEqual(policies["AR-1"].insurer_id, "aarco")
        self.assertEqual(policies["AX-1"].metadata_json["carrier"], "AXA")
        db.close()

    def test_canonical_edit_updates_drive_and_keeps_percentage_as_ratio(self):
        original = sura_workbook((37, 37, "Cliente", "ANA", 0.5, None))
        uploaded = {}
        payload = cartera.CarteraRecordPayload(
            policy_number="37", current_policy_number="37", contractor="Cliente",
            prospector="ANA", percentage=80, payment_start_date=None,
            insurer="sura", policy_type="GMM",
        )
        with patch.object(cartera, "download_drive_file_bytes", return_value=original), \
             patch.object(cartera, "_upload_drive_workbook", side_effect=lambda file_id, contents: uploaded.update(file_id=file_id, contents=contents)), \
             patch.dict(cartera.CARTERA_SOURCE_FILE_IDS, {"sura": "drive-sura"}, clear=True), \
             patch.object(cartera, "SURA_PATHS", {"CARTERA": Path("/missing/local/Cartera SURA.xlsx")}):
            cartera._write_canonical(payload, "37")

        workbook = load_workbook(io.BytesIO(uploaded["contents"]), data_only=True)
        self.assertEqual(uploaded["file_id"], "drive-sura")
        self.assertEqual(workbook["SURA"]["E2"].value, 0.8)

    def test_combined_canonical_edit_writes_actual_insurer(self):
        original = aarco_axa_workbook(("AXA", "AX-1", "AX-1", "Cliente", "ANA", 0.5, None))
        uploaded = {}
        payload = cartera.CarteraRecordPayload(
            policy_number="AX-1", current_policy_number="AX-1", contractor="Cliente",
            prospector="ANA", percentage=80, payment_start_date=None,
            insurer="aarco", carrier="Chubb", policy_type="GMM",
        )
        with patch.object(cartera, "download_drive_file_bytes", return_value=original), \
             patch.object(cartera, "_upload_drive_workbook", side_effect=lambda file_id, contents: uploaded.update(file_id=file_id, contents=contents)), \
             patch.dict(cartera.CARTERA_SOURCE_FILE_IDS, {"aarco_axa": "drive-combined"}, clear=True), \
             patch.object(cartera, "AARCO_PATHS", {"CARTERA": Path("/missing/local/Cartera AARCO.xlsx")}):
            cartera._write_canonical(payload, "AX-1")

        workbook = load_workbook(io.BytesIO(uploaded["contents"]), data_only=True)
        self.assertEqual(uploaded["file_id"], "drive-combined")
        self.assertEqual(workbook.active["A2"].value, "Chubb")
        self.assertEqual(workbook.active["F2"].value, 0.8)

    def test_sql_export_preserves_existing_carrier_when_legacy_sql_has_none(self):
        db = self.Session()
        product = Product(id="prod_aarco_vida", insurer_id="aarco", name="AARCO VIDA", branch="VIDA")
        client = Client(full_name="Cliente SQL", responsible_user_id="usr_pamela", metadata_json={})
        db.add_all([product, client])
        db.flush()
        db.add(Policy(
            policy_number="AR-1", client_id=client.id, insurer_id="aarco", product_id=product.id,
            effective_start_date=date(2026, 1, 1), effective_end_date=date(2027, 1, 1),
            premium_amount=0, payment_frequency="annual", responsible_user_id="usr_pamela",
            commission_percentage=Decimal("0.5"), metadata_json={"prospector": "ANA"},
        ))
        db.commit()
        original = aarco_axa_workbook(("Mapfre", "AR-1", "", "Anterior", "", 0, None))
        uploaded = {}
        with patch.object(cartera, "download_drive_file_bytes", return_value=original), \
             patch.object(cartera, "_upload_drive_workbook", side_effect=lambda file_id, contents: uploaded.update(file_id=file_id, contents=contents)), \
             patch.dict(cartera.CARTERA_SOURCE_FILE_IDS, {"aarco_axa": "drive-combined"}, clear=True), \
             patch.object(cartera, "AARCO_PATHS", {"CARTERA": Path("/missing/local/Cartera AARCO.xlsx")}):
            result = cartera.sync_cartera_sql_to_canonical("aarco_axa", db=db)

        workbook = load_workbook(io.BytesIO(uploaded["contents"]), data_only=True)
        self.assertEqual(result["exported"], 1)
        self.assertEqual(workbook["AARCO"]["A2"].value, "Mapfre")
        self.assertEqual(workbook["AARCO"]["D2"].value, "Cliente SQL")
        db.close()


if __name__ == "__main__":
    unittest.main()
