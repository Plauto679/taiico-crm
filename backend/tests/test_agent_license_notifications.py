from __future__ import annotations

import os
import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobs.send_agent_license_expiration_report import run, should_send
from services.agent_license_notifications import (
    agent_license_email_html,
    build_agent_license_expiration_report,
)


def agent(name: str, expiration: str, **overrides) -> dict:
    return {
        "nombre": name,
        "rfc": overrides.get("rfc", "RFC010101ABC"),
        "clave_arranque": overrides.get("clave_arranque", "123"),
        "clave_definitiva": overrides.get("clave_definitiva", "456"),
        "promotoria": overrides.get("promotoria", "TAIICO"),
        "correo_personal": overrides.get("correo_personal", "agente@example.com"),
        "telefono_particular": overrides.get("telefono_particular", "5512345678"),
        "estatus_met": overrides.get("estatus_met", "Activa"),
        "fin_vigencia_cedula": expiration,
    }


class AgentLicenseNotificationTests(unittest.TestCase):
    def test_report_includes_only_expirations_in_next_three_calendar_months(self):
        directory = {
            "agents": [
                agent("INICIO", "2026-09-01"),
                agent("DENTRO", "2026-11-30"),
                agent("LIMITE", "2026-12-01"),
                agent("VENCIDO", "2026-08-31"),
                agent("FUERA", "2026-12-02"),
                agent("SIN FECHA", ""),
            ]
        }
        report = build_agent_license_expiration_report(
            directory,
            generated_on=date(2026, 9, 1),
        )
        self.assertEqual(report["window_end"], "2026-12-01")
        self.assertEqual(
            [item["nombre"] for item in report["agents"]],
            ["INICIO", "DENTRO", "LIMITE"],
        )
        self.assertEqual(report["agents"][0]["dias_restantes"], 0)

    def test_html_escapes_source_values_and_lists_contact_data(self):
        report = build_agent_license_expiration_report(
            {"agents": [agent("ANA <SCRIPT>", "2026-10-01")]},
            generated_on=date(2026, 9, 1),
        )
        html = agent_license_email_html(report)
        self.assertIn("ANA &lt;SCRIPT&gt;", html)
        self.assertNotIn("ANA <SCRIPT>", html)
        self.assertIn("agente@example.com", html)
        self.assertIn("5512345678", html)

    def test_schedule_runs_only_on_first_day_once_after_configured_hour(self):
        first = datetime(2026, 9, 1, 10, 0, tzinfo=ZoneInfo("America/Mexico_City"))
        with patch.dict(os.environ, {"AGENT_LICENSE_AUTOMATION_HOUR": "10"}):
            self.assertTrue(should_send(first, None))
            self.assertFalse(should_send(first, "2026-09"))
            self.assertFalse(should_send(first.replace(hour=9), None))
            self.assertFalse(should_send(first.replace(day=2), None))

    def test_job_reuses_pending_recipients_and_records_month(self):
        now = datetime(2026, 9, 1, 10, 5, tzinfo=ZoneInfo("America/Mexico_City"))
        recipients = ["equipo@example.com", "operacion@example.com"]
        with TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "AGENT_LICENSE_AUTOMATION_STATE_FILE": f"{directory}/state.json",
                "AGENT_LICENSE_AUTOMATION_SENDER_USERNAME": "",
                "PENDING_REPORT_AUTOMATION_SENDER_USERNAME": "operacion@taiico.com",
            },
        ), patch(
            "jobs.send_agent_license_expiration_report.local_now",
            return_value=now,
        ), patch(
            "jobs.send_agent_license_expiration_report.configured_recipients",
            return_value=recipients,
        ), patch(
            "jobs.send_agent_license_expiration_report.deliver_agent_license_expiration_report",
            return_value={
                "recipients": recipients,
                "generated_on": "2026-09-01",
                "window_end": "2026-12-01",
                "count": 4,
            },
        ) as delivery:
            self.assertEqual(run(), 0)
            self.assertEqual(run(), 0)
            state = Path(directory, "state.json").read_text()

        delivery.assert_called_once_with(
            recipients,
            sender_username="operacion@taiico.com",
            generated_on=date(2026, 9, 1),
            months_ahead=3,
        )
        self.assertIn('"last_sent_month": "2026-09"', state)


if __name__ == "__main__":
    unittest.main()
