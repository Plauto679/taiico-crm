import io
import sys
import unittest
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.worksheet.table import Table, TableStyleInfo


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.pendientes import (
    GMM_REQUEST_OPTIONS,
    VIDA_REQUEST_OPTIONS,
    PendingSource,
    add_pending_follow_up,
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


def workbook_with_table(sheet_name, headers, rows):
    document = Workbook()
    sheet = document.active
    sheet.title = sheet_name
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    table = Table(displayName="Pendientes", ref=f"A1:{chr(64 + len(headers))}{len(rows) + 1}")
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    sheet.add_table(table)
    output = io.BytesIO()
    document.save(output)
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

    def test_latest_update_is_last_non_empty_comment_for_each_row(self):
        source = PendingSource("test", "Test", "TEST_ID", "file", "Base", 1)
        result = parse_pending_workbook(
            workbook_bytes(
                "Base",
                ["Folio", "15-jul-26", "20-jul-26", "22-jul-26"],
                [
                    ["1", "En espera de aseguradora", "", ""],
                    ["2", "", "En espera de firma del cliente", ""],
                ],
            ),
            source,
        )
        self.assertEqual(result["rows"][0]["latest_update"], {"date": "15-jul-26", "update": "En espera de aseguradora"})
        self.assertEqual(result["rows"][1]["latest_update"], {"date": "20-jul-26", "update": "En espera de firma del cliente"})

    def test_follow_up_adds_one_date_column_and_updates_target_row(self):
        source = PendingSource("emision-servicios", "Test", "TEST_ID", "file", "Base", 1)
        original = workbook_bytes(
            "Base",
            ["Folio", "20-jul-26"],
            [["1", "Anterior"], ["2", ""]],
        )
        updated, header = add_pending_follow_up(
            original,
            source,
            3,
            "En espera de firma",
            date(2026, 7, 22),
        )
        parsed = parse_pending_workbook(updated, source)
        self.assertEqual(header, "22-jul-26")
        self.assertEqual(parsed["rows"][1]["latest_update"], {"date": header, "update": "En espera de firma"})

        with zipfile.ZipFile(io.BytesIO(original)) as before, zipfile.ZipFile(io.BytesIO(updated)) as after:
            changed = [name for name in before.namelist() if before.read(name) != after.read(name)]
        self.assertEqual(changed, ["xl/worksheets/sheet1.xml"])

    def test_second_follow_up_same_day_reuses_column(self):
        source = PendingSource("siniestros", "Test", "TEST_ID", "file", "Base", 1)
        original = workbook_bytes("Base", ["Folio", "21/07/2026"], [["1", ""]])
        first, header = add_pending_follow_up(original, source, 2, "Primer comentario", date(2026, 7, 22))
        second, second_header = add_pending_follow_up(first, source, 2, "Segundo comentario", date(2026, 7, 22))
        table = pd.read_excel(io.BytesIO(second), sheet_name="Base", dtype=str, keep_default_na=False)
        self.assertEqual(header, "22/07/2026")
        self.assertEqual(second_header, header)
        self.assertEqual(list(table.columns).count(header), 1)
        self.assertEqual(table.iloc[0][header], "Primer comentario | Segundo comentario")

    def test_follow_up_extends_native_excel_table(self):
        source = PendingSource("emision-servicios", "Test", "TEST_ID", "file", "Base", 1)
        original = workbook_with_table("Base", ["Folio", "21-jul-26"], [["1", "Anterior"]])
        updated, header = add_pending_follow_up(original, source, 2, "Nuevo", date(2026, 7, 22))
        with zipfile.ZipFile(io.BytesIO(updated)) as archive:
            table_xml = archive.read("xl/tables/table1.xml").decode()
        self.assertIn('ref="A1:C2"', table_xml)
        self.assertIn('count="3"', table_xml)
        self.assertIn(f'name="{header}"', table_xml)

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
