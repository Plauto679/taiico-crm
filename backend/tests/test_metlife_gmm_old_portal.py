import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.metlife_gmm_old_portal import (
    MetLifeGmmOldPortalAdapter,
    canonical_policy_number,
    client_folder_name,
    policy_row_matches,
    portal_policy_number,
    renewal_folder_name,
)
from adapters.metlife_gmm_portal import MetLifeGmmPortalTask


class MetLifeGmmOldPortalTests(unittest.TestCase):
    def task(self, **overrides):
        values = {
            "id": "task-1",
            "policy_number": "1353851",
            "original_policy_number": "1066235",
            "rfc": "SABM7809274J4",
            "client_name": "JOSE MIGUEL SANCHEZ BAUTISTA",
            "renewal_deadline": "2026-08-31",
        }
        values.update(overrides)
        return MetLifeGmmPortalTask(**values)

    def test_uses_original_policy_number_for_legacy_portal(self):
        task = self.task()
        self.assertEqual(portal_policy_number(task), "1066235")
        self.assertTrue(
            policy_row_matches(
                "0001066235 SABM7809274J4 JOSE MIGUEL SANCHEZ BAUTISTA",
                task,
            )
        )
        self.assertFalse(policy_row_matches("0001353851 SABM7809274J4", task))

    def test_falls_back_to_current_policy_when_original_is_missing(self):
        task = self.task(original_policy_number=None)
        self.assertEqual(portal_policy_number(task), "1353851")

    def test_policy_comparison_ignores_zero_padding_but_not_partial_matches(self):
        self.assertEqual(canonical_policy_number("0001066235"), "1066235")
        task = self.task()
        self.assertFalse(policy_row_matches("Poliza 9910662358", task))

    def test_builds_canonical_client_folder_name(self):
        self.assertEqual(
            client_folder_name(self.task()),
            "SABM7809274J4 - Jose Miguel Sanchez Bautista",
        )

    def test_builds_renewal_folder_name_under_client_folder(self):
        self.assertEqual(
            renewal_folder_name(
                self.task(policy_number="1344950"),
                created_at=datetime(2026, 8, 29, 9, 7),
            ),
            "2026-08-29 09-07 Renovacion póliza 1344950 2026 - 2027",
        )

    def test_search_falls_back_from_rfc_to_policy_and_name(self):
        adapter = MetLifeGmmOldPortalAdapter(
            username="operator",
            password="secret",
        )
        calls = []
        adapter.search_rfc = lambda _page, value: calls.append(("rfc", value))
        adapter.search_policy = lambda _page, value: calls.append(("policy", value))
        adapter.search_name = lambda _page, value: calls.append(("name", value))
        matched_row = MagicMock()
        adapter.wait_for_matching_policy_rows = MagicMock(
            side_effect=[[], [], [(matched_row, "SABM7809274J4")]]
        )

        adapter.search_with_fallbacks(
            SimpleNamespace(url="https://servicios.metlife.com.mx/search"),
            self.task(),
            stop_after=None,
        )

        self.assertEqual(
            calls,
            [
                ("rfc", "SABM7809274J4"),
                ("policy", "1066235"),
                ("name", "JOSE MIGUEL SANCHEZ BAUTISTA"),
            ],
        )
        self.assertEqual(
            [step.status for step in adapter.steps],
            ["failed", "failed", "completed"],
        )


if __name__ == "__main__":
    unittest.main()
