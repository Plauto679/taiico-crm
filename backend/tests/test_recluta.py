import io
import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.recluta import (
    ReclutaCreateRequest,
    append_prospect_to_workbook,
    document_name_for,
    folder_name_for,
    parse_recluta_workbook,
    prospect_id,
)


def workbook_bytes(rows):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="Reclutamiento", index=False)
    return output.getvalue()


class ReclutaTests(unittest.TestCase):
    def test_empty_source_preserves_all_columns(self):
        columns, prospects = parse_recluta_workbook(workbook_bytes([{
            "Nombre": "",
            "Telefono": "",
            "Correo": "",
            "RFC": "",
            "Fase": "",
            "Estatus": "",
        }]))
        self.assertEqual(
            columns,
            ["Nombre", "Telefono", "Correo", "RFC", "Fase", "Estatus"],
        )
        self.assertEqual(prospects, [])

    def test_prospect_exposes_phase_status_and_raw_columns(self):
        columns, prospects = parse_recluta_workbook(workbook_bytes([{
            "Nombre": "  Ana   López ",
            "Telefono": "+52 55 1234 5678",
            "Correo": "ana@example.com",
            "RFC": "lope900101ab1",
            "Fase": "Entrevista",
            "Estatus": "Contactada",
        }]))
        self.assertEqual(columns[-2:], ["Fase", "Estatus"])
        self.assertEqual(prospects[0]["nombre"], "Ana López")
        self.assertEqual(prospects[0]["rfc"], "LOPE900101AB1")
        self.assertEqual(prospects[0]["fase"], "Entrevista")
        self.assertEqual(prospects[0]["estatus"], "Contactada")
        self.assertEqual(prospects[0]["raw"]["Correo"], "ana@example.com")

    def test_duplicate_names_use_rfc_in_folder_name(self):
        prospects = [
            {"id": "first", "nombre": "Ana López", "rfc": "LOPE900101AB1"},
            {"id": "second", "nombre": "Ana López", "rfc": "LOPE920202CD2"},
        ]
        self.assertEqual(
            folder_name_for(prospects[0], prospects),
            "Ana López - LOPE900101AB1",
        )

    def test_prospect_id_does_not_change_when_row_moves(self):
        identity = {
            "nombre": "Ana López",
            "telefono": "+52 55 1234 5678",
            "correo": "ana@example.com",
            "rfc": "LOPE900101AB1",
        }
        self.assertEqual(prospect_id(identity, 2), prospect_id(identity, 20))

    def test_append_prospect_preserves_columns_and_adds_record(self):
        original = workbook_bytes([{
            "Nombre": "",
            "Telefono": "",
            "Correo": "",
            "RFC": "",
            "Fase": "",
            "Estatus": "",
            "Notas": "",
        }])
        updated = append_prospect_to_workbook(original, ReclutaCreateRequest(
            nombre="Ana López",
            telefono="+52 55 1234 5678",
            correo="ANA@EXAMPLE.COM",
            rfc="lope900101ab1",
            fase="Contacto inicial",
            estatus="Activa",
        ))
        columns, prospects = parse_recluta_workbook(updated)
        self.assertEqual(columns[-1], "Notas")
        self.assertEqual(len(prospects), 1)
        self.assertEqual(prospects[0]["rfc"], "LOPE900101AB1")
        self.assertEqual(prospects[0]["correo"], "ana@example.com")

    def test_append_rejects_duplicate_rfc(self):
        original = workbook_bytes([{
            "Nombre": "Ana López",
            "Telefono": "",
            "Correo": "",
            "RFC": "LOPE900101AB1",
            "Fase": "Contacto inicial",
            "Estatus": "Activa",
        }])
        with self.assertRaisesRegex(ValueError, "Ya existe un recluta"):
            append_prospect_to_workbook(original, ReclutaCreateRequest(
                nombre="Otra persona",
                rfc="lope900101ab1",
            ))

    def test_document_name_preserves_original_extension(self):
        self.assertEqual(
            document_name_for("Cédula de agente", "scan.PDF"),
            "Cédula de agente.pdf",
        )
        self.assertEqual(
            document_name_for("Identificación.png", "scan.png"),
            "Identificación.png",
        )


if __name__ == "__main__":
    unittest.main()
