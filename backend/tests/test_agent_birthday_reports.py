from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.agent_birthday_reports import (  # noqa: E402
    agent_birthday_report_html,
    deliver_agent_birthday_report,
    upcoming_agent_birthdays,
)


DIRECTORY = {
    "generated_on": "2026-09-14",
    "agents": [
        {
            "agent_name": "Ana Uno",
            "rfc": "AUA900919AA1",
            "next_birthday": "2026-09-19",
            "days_until_birthday": 5,
            "promotorias": ["ABBONDANZA"],
            "definitive_keys": ["100"],
            "email": "ana@example.com",
        },
        {
            "agent_name": "Bea Dos",
            "rfc": "BED900929BB2",
            "next_birthday": "2026-09-29",
            "days_until_birthday": 15,
            "promotorias": ["EKILIBRA"],
            "definitive_keys": ["200"],
            "email": "bea@example.com",
        },
        {
            "agent_name": "Caro Tres",
            "rfc": "CAT901001CC3",
            "next_birthday": "2026-10-01",
            "days_until_birthday": 17,
            "promotorias": ["ABBONDANZA"],
            "definitive_keys": ["300"],
            "email": "caro@example.com",
        },
    ],
}


class AgentBirthdayReportTests(unittest.TestCase):
    def test_filters_15_day_window_and_promotoria(self):
        general = upcoming_agent_birthdays(DIRECTORY)
        abbondanza = upcoming_agent_birthdays(DIRECTORY, promotoria="abbondanza")

        self.assertEqual([agent["agent_name"] for agent in general], ["Ana Uno", "Bea Dos"])
        self.assertEqual([agent["agent_name"] for agent in abbondanza], ["Ana Uno"])

    def test_html_keeps_report_columns(self):
        html = agent_birthday_report_html(
            upcoming_agent_birthdays(DIRECTORY),
            generated_on="2026-09-14",
        )

        for label in ("Agente", "Cumpleaños", "Cuándo", "Promotoría", "Clave definitiva", "Correo"):
            self.assertIn(label, html)
        self.assertIn("Ana Uno", html)

    @patch("services.agent_birthday_reports.smtp_settings_for", return_value=object())
    @patch("services.agent_birthday_reports.send_email_smtp")
    def test_delivery_uses_requested_distribution(self, send_email, smtp_settings):
        result = deliver_agent_birthday_report(
            DIRECTORY,
            ["equipo@taiico.com"],
            sender_username="alberto.alfaro@taiico.com",
            promotoria="ABBONDANZA",
        )

        self.assertEqual(result["count"], 1)
        smtp_settings.assert_called_once_with("alberto.alfaro@taiico.com")
        self.assertEqual(send_email.call_args.kwargs["recipients"], ["equipo@taiico.com"])
        self.assertIn("ABBONDANZA", send_email.call_args.kwargs["subject"])


if __name__ == "__main__":
    unittest.main()
