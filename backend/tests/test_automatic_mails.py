from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.automatic_mails import (  # noqa: E402
    AutomaticMailUpdate,
    all_automation_configs,
    automation_config,
    save_automation_config,
    schedule_matches,
    schedule_period_key,
)


class AutomaticMailConfigurationTests(unittest.TestCase):
    def test_inventory_contains_real_jobs_and_excludes_pamela_from_renewals(self):
        with TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "AUTOMATIC_MAILS_CONFIG_FILE": f"{directory}/config.json",
                "RENEWAL_AGENT_AUTOMATION_RECIPIENTS": "",
                "RENEWAL_EMAIL_CC_RECIPIENTS": "",
                "RENEWAL_AGENT_AUTOMATION_HOUR": "7",
            },
        ):
            items = {item["id"]: item for item in all_automation_configs()}

        self.assertEqual(
            set(items),
            {
                "client_birthdays",
                "pending_daily",
                "pending_promotoria_abbondanza",
                "pending_promotoria_ekilibra",
                "pending_promotoria_fenix_prevision",
                "pending_weekly_reminder",
                "agent_license_expiration",
                "renewal_agent",
            },
        )
        self.assertNotIn(
            "pamela.alfaro@taiico.com",
            items["renewal_agent"]["recipients"],
        )
        self.assertNotIn(
            "pamela.alfaro@taiico.com",
            items["renewal_agent"]["cc_recipients"],
        )
        self.assertEqual(items["renewal_agent"]["hour"], 7)
        self.assertEqual(
            items["pending_promotoria_abbondanza"]["recipients"],
            ["19eryk@gmail.com"],
        )
        self.assertEqual(
            items["pending_promotoria_ekilibra"]["promotoria"],
            "EKILIBRA",
        )
        self.assertEqual(
            items["pending_promotoria_fenix_prevision"]["recipients"],
            ["vic.villanueva@hotmail.com"],
        )

    def test_saved_configuration_is_read_by_jobs(self):
        with TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {"AUTOMATIC_MAILS_CONFIG_FILE": f"{directory}/config.json"},
        ):
            saved = save_automation_config(
                "renewal_agent",
                AutomaticMailUpdate(
                    enabled=False,
                    cadence="weekly",
                    hour=8,
                    minute=30,
                    timezone="America/Mexico_City",
                    day_of_week=2,
                    day_of_month=None,
                    sender="clientes@taiico.com",
                    recipients=["operacion@taiico.com"],
                    cc_recipients=["auditoria@taiico.com"],
                ),
            )
            loaded = automation_config("renewal_agent")

        self.assertEqual(saved, loaded)
        self.assertFalse(loaded["enabled"])
        self.assertEqual(loaded["recipients"], ["operacion@taiico.com"])

    def test_schedule_honors_cadence_time_and_enabled_state(self):
        now = datetime(2026, 9, 2, 8, 30, tzinfo=ZoneInfo("America/Mexico_City"))
        config = {
            "enabled": True,
            "cadence": "weekly",
            "hour": 8,
            "minute": 30,
            "day_of_week": 2,
            "day_of_month": None,
        }
        self.assertTrue(schedule_matches(config, now))
        self.assertFalse(schedule_matches(config, now.replace(minute=29)))
        self.assertFalse(schedule_matches({**config, "enabled": False}, now))
        self.assertEqual(schedule_period_key(config, now), "2026-W36")
        self.assertEqual(
            schedule_period_key({**config, "cadence": "daily"}, now),
            "2026-09-02",
        )


if __name__ == "__main__":
    unittest.main()
