from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import call, patch
from zoneinfo import ZoneInfo


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobs.send_agent_birthday_report import AUTOMATION_IDS, due_reports, run  # noqa: E402


def config(automation_id: str) -> dict:
    promotoria = None
    if "abbondanza" in automation_id:
        promotoria = "ABBONDANZA"
    elif "ekilibra" in automation_id:
        promotoria = "EKILIBRA"
    elif "fenix" in automation_id:
        promotoria = "FENIX PRE-VISION"
    return {
        "id": automation_id,
        "enabled": True,
        "cadence": "weekly",
        "hour": 8,
        "minute": 0,
        "timezone": "America/Mexico_City",
        "day_of_week": 0,
        "day_of_month": None,
        "sender": "alberto.alfaro@taiico.com",
        "recipients": [f"{automation_id}@example.com"],
        "promotoria": promotoria,
    }


class AgentBirthdayReportJobTests(unittest.TestCase):
    def test_due_only_on_monday_after_eight_and_once_per_week(self):
        monday = datetime(2026, 9, 14, 8, 0, tzinfo=ZoneInfo("America/Mexico_City"))
        with patch("jobs.send_agent_birthday_report.automation_config", side_effect=config), patch(
            "jobs.send_agent_birthday_report.local_now_for", return_value=monday
        ):
            self.assertEqual(len(due_reports({})), len(AUTOMATION_IDS))
            state = {
                "reports": {
                    automation_id: {"period_key": "2026-W38"}
                    for automation_id in AUTOMATION_IDS
                }
            }
            self.assertEqual(due_reports(state), [])
            self.assertEqual(due_reports({}, force=True)[0][3], "2026-W38")

        with patch("jobs.send_agent_birthday_report.automation_config", side_effect=config), patch(
            "jobs.send_agent_birthday_report.local_now_for", return_value=monday.replace(hour=7, minute=59)
        ):
            self.assertEqual(due_reports({}), [])

    def test_run_records_each_success_and_does_not_repeat(self):
        monday = datetime(2026, 9, 14, 8, 5, tzinfo=ZoneInfo("America/Mexico_City"))
        with TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {"AGENT_BIRTHDAY_AUTOMATION_STATE_FILE": f"{directory}/state.json"},
        ), patch(
            "jobs.send_agent_birthday_report.automation_config", side_effect=config
        ), patch(
            "jobs.send_agent_birthday_report.local_now_for", return_value=monday
        ), patch(
            "jobs.send_agent_birthday_report.load_agent_birthday_directory",
            return_value={"generated_on": "2026-09-14", "agents": []},
        ), patch(
            "jobs.send_agent_birthday_report.deliver_agent_birthday_report",
            side_effect=lambda directory, recipients, **kwargs: {
                "generated_on": directory["generated_on"],
                "count": 0,
                "recipients": recipients,
                "promotoria": kwargs.get("promotoria"),
            },
        ) as delivery:
            self.assertEqual(run(), 0)
            self.assertEqual(run(), 0)

        self.assertEqual(delivery.call_count, 4)
        self.assertEqual(
            delivery.call_args_list[0],
            call(
                {"generated_on": "2026-09-14", "agents": []},
                ["agent_birthdays_weekly@example.com"],
                sender_username="alberto.alfaro@taiico.com",
                promotoria=None,
                window_days=15,
            ),
        )


if __name__ == "__main__":
    unittest.main()
