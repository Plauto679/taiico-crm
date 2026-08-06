import json
import os
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobs.run_renewal_agent import (
    WHATSAPP_ENABLED,
    execute_batch,
    max_consecutive_portal_failures,
    renewal_cutoff,
    run,
    should_run,
    task_processing_order,
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

    def test_default_abort_threshold_is_seven_consecutive_failures(self):
        with patch.dict(os.environ):
            os.environ.pop(
                "RENEWAL_AGENT_MAX_CONSECUTIVE_PORTAL_FAILURES",
                None,
            )
            self.assertEqual(max_consecutive_portal_failures(), 7)

    def test_overdue_tasks_are_processed_after_current_window_tasks(self):
        class Task:
            def __init__(self, deadline, policy_number):
                self.renewal_deadline = deadline
                self.policy_number = policy_number
                self.attempt_count = 0

        process_date = date(2026, 7, 31)
        tasks = [
            Task(date(2026, 7, 20), "OVERDUE"),
            Task(date(2026, 8, 5), "UPCOMING"),
            Task(date(2026, 7, 31), "TODAY"),
        ]

        ordered = sorted(
            tasks,
            key=lambda task: task_processing_order(task, process_date),
        )

        self.assertEqual(
            [task.policy_number for task in ordered],
            ["TODAY", "UPCOMING", "OVERDUE"],
        )

    def test_batch_aborts_on_seventh_consecutive_portal_failure(self):
        now = datetime(
            2026,
            7,
            31,
            9,
            0,
            tzinfo=ZoneInfo("America/Mexico_City"),
        )
        tasks = [
            SimpleNamespace(
                id=f"task-{index}",
                policy_number=f"policy-{index}",
                renewal_deadline=date(2026, 8, 1),
                client_name=f"Cliente {index}",
                rfc=f"RFC{index}",
            )
            for index in range(8)
        ]
        failure = (
            {
                "status": "failed",
                "detail": "No se encontró la renovación en el portal",
            },
            True,
        )
        completed = {
            "run_id": "run-1",
            "status": "failed",
            "selected": 8,
            "succeeded": 0,
            "failed": 7,
            "aborted": True,
        }

        with patch.dict(
            os.environ,
            {"RENEWAL_AGENT_MAX_CONSECUTIVE_PORTAL_FAILURES": "7"},
        ), patch(
            "jobs.run_renewal_agent.selected_tasks",
            return_value=tasks,
        ), patch(
            "jobs.run_renewal_agent.create_run",
            return_value="run-1",
        ), patch(
            "jobs.run_renewal_agent.send_email_smtp",
        ), patch(
            "jobs.run_renewal_agent.process_one",
            return_value=failure,
        ) as process_one, patch(
            "jobs.run_renewal_agent.finish_run",
            return_value=completed,
        ) as finish_run:
            result = execute_batch(now)

        self.assertEqual(process_one.call_count, 7)
        finish_run.assert_called_once_with(
            "run-1",
            [failure[0]] * 7,
            aborted=True,
            process_date=now.date(),
        )
        self.assertEqual(result, completed)

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
