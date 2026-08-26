import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobs.send_pending_report import configured_recipients, run, should_send, should_send_reminder


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
                    "gilberto.gonzalez@taiico.com",
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

    def test_reminder_runs_monday_once_after_10(self):
        monday = datetime(2026, 7, 27, 10, 0, tzinfo=ZoneInfo("America/Mexico_City"))
        with patch.dict(os.environ, {"PENDING_REMINDER_AUTOMATION_HOUR": "10"}):
            self.assertTrue(should_send_reminder(monday, None))
            self.assertFalse(should_send_reminder(monday, "2026-07-27"))
            self.assertFalse(should_send_reminder(monday.replace(hour=9), None))
            self.assertFalse(should_send_reminder(monday.replace(day=28), None))

    def test_job_sends_only_the_daily_pending_report(self):
        with TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {"PENDING_REPORT_AUTOMATION_STATE_FILE": f"{directory}/state.json"},
        ), patch(
            "jobs.send_pending_report.deliver_pending_report",
            return_value={
                "recipients": configured_recipients(),
                "generated_on": "2026-07-28",
            },
        ) as daily_delivery:
            self.assertEqual(run(force=True), 0)

        daily_delivery.assert_called_once_with(
            configured_recipients(),
            sender_username="alberto.alfaro@taiico.com",
        )


if __name__ == "__main__":
    unittest.main()
