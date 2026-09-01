from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.pendientes import _filter_source_by_promotoria  # noqa: E402


class PendingPromotoriaReportTests(unittest.TestCase):
    def test_filter_keeps_only_rows_from_requested_promotoria(self):
        source = {
            "source": "emision-servicios",
            "rows": [
                {"source_row": 2, "summary": {"Promotoria": "ABBONDANZA"}},
                {"source_row": 3, "summary": {"Promotoria": " Ekilibra "}},
                {"source_row": 4, "summary": {"Promotoria": "FENIX PRE-VISION"}},
                {"source_row": 5, "summary": {}},
            ],
        }

        filtered = _filter_source_by_promotoria(source, "EKILIBRA")

        self.assertEqual(
            [row["source_row"] for row in filtered["rows"]],
            [3],
        )
        self.assertEqual(len(source["rows"]), 4)


if __name__ == "__main__":
    unittest.main()
