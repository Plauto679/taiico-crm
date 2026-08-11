import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from adapters.metlife_gmm_old_portal import (
    canonical_policy_number,
    client_folder_name,
    policy_row_matches,
    portal_policy_number,
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


if __name__ == "__main__":
    unittest.main()
