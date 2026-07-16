import io
import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.pendientes import PendingSource, parse_pending_workbook


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


if __name__ == "__main__":
    unittest.main()
