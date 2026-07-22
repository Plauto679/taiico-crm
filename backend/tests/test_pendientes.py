import io
import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.pendientes import (
    GMM_REQUEST_OPTIONS,
    VIDA_REQUEST_OPTIONS,
    PendingSource,
    append_pending_record,
    parse_pending_workbook,
)
from services.pending_document_requirements import (
    GMM_DOCUMENT_REQUIREMENTS,
    VIDA_DOCUMENT_REQUIREMENTS,
    requirements_for,
)


def workbook_bytes(sheet_name, headers, rows):
    output = io.BytesIO()
    with pd.ExcelWriter(output) as writer:
        pd.DataFrame(rows, columns=headers).to_excel(
            writer,
            sheet_name=sheet_name,
            index=False,
        )
    return output.getvalue()


class PendingWorkbookTests(unittest.TestCase):
    def test_summary_uses_core_columns_and_latest_update(self):
        source = PendingSource("test", "Test", "TEST_ID", "file", "Base", 2)
        result = parse_pending_workbook(
            workbook_bytes(
                "Base",
                ["Folio", "Cliente", "15-jul", "16-jul"],
                [["123", "Cliente Uno", "Primer avance", "Último avance"]],
            ),
            source,
        )
        row = result["rows"][0]
        self.assertEqual(row["summary"], {"Folio": "123", "Cliente": "Cliente Uno"})
        self.assertEqual(row["latest_update"], {"date": "16-jul", "update": "Último avance"})
        self.assertEqual(len(row["history"]), 2)

    def test_empty_history_cells_are_not_shown_in_detail(self):
        source = PendingSource("test", "Test", "TEST_ID", "file", "Base", 1)
        result = parse_pending_workbook(
            workbook_bytes("Base", ["Folio", "15-jul", "16-jul"], [["123", "", "Avance"]]),
            source,
        )
        self.assertEqual(
            result["rows"][0]["history"],
            [{"date": "16-jul", "update": "Avance"}],
        )

    def test_append_pending_record_only_sets_requested_columns(self):
        source = PendingSource("test", "Test", "TEST_ID", "file", "Base", 3)
        original = workbook_bytes(
            "Base",
            ["Asegurado", "Póliza", "Casificacion", "16-jul"],
            [["Anterior", "123", "Vida", "Seguimiento"]],
        )
        updated, source_row = append_pending_record(original, source, {
            "Asegurado": "Nueva Persona",
            "Póliza": "456",
            "Casificacion": "GMM",
        })
        parsed = parse_pending_workbook(updated, source)
        self.assertEqual(source_row, 3)
        self.assertEqual(parsed["rows"][-1]["summary"], {
            "Asegurado": "Nueva Persona",
            "Póliza": "456",
            "Casificacion": "GMM",
        })
        self.assertEqual(parsed["rows"][-1]["latest_update"]["update"], "")

    def test_request_options_are_classification_specific(self):
        self.assertIn("Reembolso GMM", GMM_REQUEST_OPTIONS)
        self.assertNotIn("Reembolso GMM", VIDA_REQUEST_OPTIONS)
        self.assertIn("Rescate total / parcial VIDA", VIDA_REQUEST_OPTIONS)

    def test_rfc_is_preserved_as_core_column(self):
        source = PendingSource("test", "Test", "TEST_ID", "file", "Base", 3)
        result = parse_pending_workbook(
            workbook_bytes(
                "Base",
                ["Asegurado", "RFC", "Póliza", "22-jul"],
                [["Cliente", "AAMA950203I52", "123", "Registrado"]],
            ),
            source,
        )
        self.assertEqual(result["rows"][0]["summary"]["RFC"], "AAMA950203I52")

    def test_document_requirements_follow_classification_and_request(self):
        gmm = requirements_for("GMM", "Reembolso GMM")
        vida = requirements_for("Vida", "Rescate total / parcial VIDA")
        self.assertIn("Informe medico", gmm)
        self.assertIn("Estado de cuenta", vida)
        self.assertEqual(requirements_for("GMM", "Solicitud desconocida"), [])
        self.assertEqual(set(GMM_DOCUMENT_REQUIREMENTS), GMM_REQUEST_OPTIONS)
        self.assertEqual(set(VIDA_DOCUMENT_REQUIREMENTS), VIDA_REQUEST_OPTIONS)


if __name__ == "__main__":
    unittest.main()
