import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobs.send_pending_report import configured_recipients, should_send


class PendingReportJobTests(unittest.TestCase):
    def test_default_recipients_match_operational_distribution(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PENDING_REPORT_AUTOMATION_RECIPIENTS", None)
            self.assertEqual(
                configured_recipients(),
                [
                    "pamela.alfaro@taiico.com",
                    "veronica.alfaro@taiico.com",
                    "alberto.alfaro@taiico.com",
                    "florgabriela.flores@taiico.com",
                    "juan.ibarraran@taiico.com",
                ],
            )

    def test_job_runs_once_after_19_mexico_city(self):
        now = datetime(2026, 7, 27, 19, 5, tzinfo=ZoneInfo("America/Mexico_City"))
        with patch.dict(
            os.environ,
            {"PENDING_REPORT_AUTOMATION_HOUR": "19"},
        ):
            self.assertTrue(should_send(now, None))
            self.assertFalse(should_send(now, "2026-07-27"))

    def test_job_does_not_run_before_19(self):
        now = datetime(2026, 7, 27, 18, 59, tzinfo=ZoneInfo("America/Mexico_City"))
        with patch.dict(
            os.environ,
            {"PENDING_REPORT_AUTOMATION_HOUR": "19"},
        ):
            self.assertFalse(should_send(now, None))


if __name__ == "__main__":
    unittest.main()
