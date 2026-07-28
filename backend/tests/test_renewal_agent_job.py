import json
import os
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobs.run_renewal_agent import (
    WHATSAPP_ENABLED,
    renewal_cutoff,
    run,
    should_run,
)


class RenewalAgentJobTests(unittest.TestCase):
    def test_job_runs_once_after_09_mexico_city(self):
        now = datetime(
            2026,
            7,
            28,
            9,
            5,
            tzinfo=ZoneInfo("America/Mexico_City"),
        )
        with patch.dict(
            os.environ,
            {"RENEWAL_AGENT_AUTOMATION_HOUR": "9"},
        ):
            self.assertTrue(should_run(now, None))
            self.assertFalse(should_run(now, "2026-07-28"))

    def test_job_does_not_run_before_09(self):
        now = datetime(
            2026,
            7,
            28,
            8,
            59,
            tzinfo=ZoneInfo("America/Mexico_City"),
        )
        with patch.dict(
            os.environ,
            {"RENEWAL_AGENT_AUTOMATION_HOUR": "9"},
        ):
            self.assertFalse(should_run(now, None))

    def test_cutoff_is_dynamic_thirty_day_window(self):
        now = datetime(
            2026,
            7,
            28,
            9,
            0,
            tzinfo=ZoneInfo("America/Mexico_City"),
        )
        with patch.dict(
            os.environ,
            {"RENEWAL_AGENT_AUTOMATION_WINDOW_DAYS": "30"},
        ):
            self.assertEqual(renewal_cutoff(now), date(2026, 8, 27))

    def test_whatsapp_is_disabled_in_daily_job(self):
        self.assertFalse(WHATSAPP_ENABLED)

    def test_started_date_is_written_before_batch_and_prevents_second_run(self):
        now = datetime(
            2026,
            7,
            28,
            9,
            5,
            tzinfo=ZoneInfo("America/Mexico_City"),
        )
        with TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "RENEWAL_AGENT_AUTOMATION_STATE_FILE": (
                    f"{directory}/state.json"
                )
            },
        ), patch(
            "jobs.run_renewal_agent.local_now",
            return_value=now,
        ), patch(
            "jobs.run_renewal_agent.execute_batch",
            return_value={
                "run_id": "run-1",
                "status": "completed",
                "selected": 1,
                "succeeded": 1,
                "failed": 0,
                "aborted": False,
            },
        ) as execute:
            self.assertEqual(run(), 0)
            self.assertEqual(run(), 0)
            state = json.loads(Path(directory, "state.json").read_text())

        execute.assert_called_once()
        self.assertEqual(state["last_started_date"], "2026-07-28")
        self.assertFalse(state["whatsapp_enabled"])


if __name__ == "__main__":
    unittest.main()
