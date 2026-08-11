import datetime
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobs.send_birthday_notifications import run, should_send
from services.birthday_notifications import (
    birthday_email_html,
    build_agent_birthday_notifications,
)


def directory_fixture() -> dict:
    return {
        "generated_on": "2026-08-11",
        "clients": [
            {
                "client_name": "ACUÑA ISLAS/RODRIGO//",
                "agent_rfc": "TLA180122DQ2",
                "agent_name": "T&M2, Life Advisors",
                "agent_label": "TLA180122DQ2 - T&M2, Life Advisors",
                "agent_email": "pamela.alfaro@taiico.com",
                "days_until_birthday": 0,
                "next_birthday": "2026-08-11",
                "policies": [{"branch": "VIDA", "policy_number": "8257708"}],
            },
            {
                "client_name": "Cliente Día Siete",
                "agent_rfc": "TLA180122DQ2",
                "agent_name": "T&M2, Life Advisors",
                "agent_label": "TLA180122DQ2 - T&M2, Life Advisors",
                "agent_email": "pamela.alfaro@taiico.com",
                "days_until_birthday": 7,
                "next_birthday": "2026-08-18",
                "policies": [],
            },
            {
                "client_name": "Fuera de ventana",
                "agent_rfc": "TLA180122DQ2",
                "agent_name": "T&M2, Life Advisors",
                "agent_label": "TLA180122DQ2 - T&M2, Life Advisors",
                "agent_email": "pamela.alfaro@taiico.com",
                "days_until_birthday": 8,
                "next_birthday": "2026-08-19",
                "policies": [],
            },
        ],
    }


class BirthdayNotificationTests(unittest.TestCase):
    def test_groups_today_through_day_seven_by_agent(self):
        result = build_agent_birthday_notifications(directory_fixture())

        self.assertEqual(len(result["notifications"]), 1)
        self.assertEqual(len(result["notifications"][0]["clients"]), 2)
        html = birthday_email_html(result["notifications"][0])
        self.assertIn("ACUÑA ISLAS RODRIGO", html)
        self.assertIn("En 7 días", html)
        self.assertNotIn("Fuera de ventana", html)
        self.assertNotIn("8257708", html)

    def test_schedule_starts_at_11_mexico_city(self):
        before = datetime.datetime(
            2026, 8, 11, 10, 59, tzinfo=ZoneInfo("America/Mexico_City")
        )
        due = before.replace(hour=11)
        with patch.dict(os.environ, {"BIRTHDAY_AUTOMATION_HOUR": "11"}):
            self.assertFalse(should_send(before, None))
            self.assertTrue(should_send(due, None))
            self.assertFalse(should_send(due, "2026-08-11"))

    def test_controlled_test_uses_alberto_and_does_not_change_state(self):
        with TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {"BIRTHDAY_AUTOMATION_STATE_FILE": f"{directory}/state.json"},
        ), patch(
            "jobs.send_birthday_notifications.load_birthday_directory",
            return_value=directory_fixture(),
        ), patch(
            "jobs.send_birthday_notifications.smtp_settings_for",
            return_value={"sender": "alberto.alfaro@taiico.com"},
        ), patch(
            "jobs.send_birthday_notifications.send_email_smtp"
        ) as send_email:
            self.assertEqual(
                run(
                    agent_rfc="TLA180122DQ2",
                    test_recipient="alberto.alfaro@taiico.com",
                ),
                0,
            )

            self.assertFalse(Path(directory, "state.json").exists())
            send_email.assert_called_once()
            call = send_email.call_args.kwargs
            self.assertEqual(call["recipients"], ["alberto.alfaro@taiico.com"])
            self.assertTrue(call["subject"].startswith("[PRUEBA]"))


if __name__ == "__main__":
    unittest.main()
