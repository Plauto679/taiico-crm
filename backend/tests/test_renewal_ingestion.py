import datetime
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import renewal_ingestion


def parsed_row(policy_number, deadline):
    return SimpleNamespace(normalized_payload={
        "policy_number": policy_number,
        "renewal_deadline": deadline,
    })


class CanonicalRenewalIngestionTests(unittest.TestCase):
    def test_summary_separates_matches_unmatched_and_invalid_rows(self):
        rows = [
            parsed_row("MATCHED", datetime.date(2026, 7, 1)),
            parsed_row("MISSING", datetime.date(2026, 8, 1)),
            parsed_row(None, datetime.date(2026, 9, 1)),
        ]

        with patch.object(
            renewal_ingestion,
            "find_policy",
            side_effect=lambda _db, number: object() if number == "MATCHED" else None,
        ):
            summary = renewal_ingestion.summarize_rows(object(), rows)

        self.assertEqual(summary["rows_read"], 3)
        self.assertEqual(summary["unique_renewals"], 2)
        self.assertEqual(summary["matched_policy_rows"], 1)
        self.assertEqual(summary["unmatched_policy_rows"], 1)
        self.assertEqual(summary["invalid_rows"], 1)

    def test_only_sources_with_validated_parsers_are_supported(self):
        self.assertIn("renovaciones.metlife_gmm", renewal_ingestion.SUPPORTED_SOURCES)
        self.assertIn("renovaciones.metlife_vida", renewal_ingestion.SUPPORTED_SOURCES)
        self.assertNotIn("renovaciones.sura", renewal_ingestion.SUPPORTED_SOURCES)


if __name__ == "__main__":
    unittest.main()
