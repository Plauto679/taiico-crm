import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.table import Table

from services.base_loads import build_preview, replace_canonical_workbook


HEADERS = [
    "CONTRATANTE", "RFC", "RAMSUBRAMO", "PRODUCTO", "NPOLIZA", "POLORIG",
    "FINIVIG", "FFINVIG", "NESQFPAGO", "NOMBREL", "ESTATUS", "CONDCOB",
    "PROMOTORIA", "AGENTE", "NOMBRE", "PRIMA", "PRIMA", "RECARGO",
    "GTOSEXP", "IVA", "MONEDA", "PAGADOHASTA", "DEDUCIBLE", "COASEGURO",
]


def business_row(policy, agent, end_date, client="CLIENTE", status=4):
    return [
        client, "RFC", 6001, "GMM", policy, policy, 20260101, end_date, 1,
        "ANUAL", status, "AGENTE", 119, agent, "AGENTE NOMBRE", 100, 100, 0,
        0, 16, "PESOS", 0, 10000, 10,
    ]


class BaseLoadsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.agents = root / "agents.xlsx"
        self.incoming = root / "incoming.xlsx"
        self.canonical = root / "canonical.xlsx"

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Datos"
        sheet.append(["CLAVE_DEFINITIVA", "Nombre"])
        sheet.append([73640, "Agente válido"])
        workbook.save(self.agents)

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Reporte"
        sheet.append(HEADERS)
        sheet.append(business_row(100, 73640, 20270101, "ANTERIOR"))
        sheet.append(business_row(100, 73640, 20280101, "RECIENTE"))
        sheet.append(business_row(100, 73640, 20280101, "RECIENTE"))
        sheet.append(business_row(200, 99999, 20280101, "NO AUTORIZADO"))
        sheet.append(business_row(300, 73640, 20280201, "NUEVO"))
        workbook.save(self.incoming)

        workbook = Workbook()
        workbook.active.title = "Taiico OS Notes"
        sheet = workbook.create_sheet("GMM")
        full_headers = HEADERS + ["ESTATUS_DE_RENOVACION", "EXPEDIENTE", "Email"]
        sheet.append(full_headers)
        sheet.append(business_row(100, 73640, 20280101, "VIEJO") + ["En proceso", "drive://100", "cliente@example.com"])
        sheet.append(business_row(400, 73640, 20260101, "AUSENTE") + ["Comentario", "drive://400", None])
        sheet.add_table(Table(displayName="GMMTable", ref="A1:AA3"))
        workbook.save(self.canonical)

    def tearDown(self):
        self.temp.cleanup()

    def test_preview_reports_filter_dedup_and_preservation(self):
        preview = build_preview(self.incoming, self.canonical, self.agents)
        self.assertEqual(preview["source_rows"], 5)
        self.assertEqual(preview["rows_after_agent_filter"], 4)
        self.assertEqual(preview["duplicate_a_x_rows"], 1)
        self.assertEqual(preview["unique_incoming_policies"], 2)
        self.assertEqual(preview["unique_policy_periods"], 3)
        self.assertEqual(preview["existing_policies_updated"], 1)
        self.assertEqual(preview["new_policies_added"], 1)
        self.assertEqual(preview["current_policies_preserved_as_exceptions"], 1)
        self.assertEqual(preview["final_policy_count"], 3)
        self.assertEqual(preview["final_row_count"], 4)

    @patch("services.base_loads.upload_history_backup")
    def test_apply_keeps_all_periods_and_preserves_matching_y_plus(self, upload_backup):
        upload_backup.return_value = {
            "backup_file_id": "backup-id",
            "backup_name": "canonical antes de carga.xlsx",
            "backup_url": "https://drive.google.com/file/d/backup-id/view",
            "backup_folder_id": "history-folder-id",
        }
        result = replace_canonical_workbook(self.incoming, self.canonical, self.agents)
        upload_backup.assert_called_once()
        self.assertEqual(result["backup_file_id"], "backup-id")
        workbook = load_workbook(self.canonical, data_only=True)
        try:
            sheet = workbook["GMM"]
            rows = list(sheet.iter_rows(min_row=2, values_only=True))
            policy_100 = [row for row in rows if str(row[4]) == "100"]
            self.assertEqual(len(policy_100), 2)
            self.assertEqual({row[7] for row in policy_100}, {20270101, 20280101})
            recent = next(row for row in policy_100 if row[7] == 20280101)
            self.assertEqual(recent[0], "RECIENTE")
            old = next(row for row in policy_100 if row[7] == 20270101)
            self.assertEqual(old[24:], (None, None, None))
            policy_300 = next(row for row in rows if str(row[4]) == "300")
            self.assertEqual(policy_300[24:], (None, None, None))
            policy_400 = next(row for row in rows if str(row[4]) == "400")
            self.assertEqual(policy_400[0], "AUSENTE")
            self.assertEqual(sheet.tables["GMMTable"].ref, "A1:AA5")
        finally:
            workbook.close()

    @patch("services.base_loads.upload_history_backup")
    def test_apply_aborts_before_replacement_when_backup_fails(self, upload_backup):
        original = self.canonical.read_bytes()
        upload_backup.side_effect = RuntimeError("Drive no disponible")

        with self.assertRaisesRegex(RuntimeError, "Drive no disponible"):
            replace_canonical_workbook(self.incoming, self.canonical, self.agents)

        self.assertEqual(self.canonical.read_bytes(), original)
