from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.agentes import scope_agent_directory
from services.auth import AccessProfile, PROMOTORIAS
from services.cumpleanos import birthday_clients
from services.cumpleanos_agentes import birthday_agents
from services.renovaciones import scope_renewal_rows


def profile(*promotorias: str) -> AccessProfile:
    return AccessProfile(
        username="scoped@example.com",
        role="admin",
        promotorias=tuple(promotorias),
        rfc="",
        aseguradoras=("METLIFE",),
        module_permissions={
            "agentes": "operacion",
            "cumpleanos": "lectura",
            "cumpleanos_agentes": "lectura",
            "renovaciones": "operacion",
        },
    )


class PromotoriaScopeTests(unittest.TestCase):
    def test_scoped_admin_only_sees_assigned_renewals(self):
        rows = [
            {"PROMOTORIA": "ABBONDANZA", "RFC": "A"},
            {"PROMOTORIA": "TAIICO", "RFC": "B"},
            {"PROMOTORIA": "", "RFC": "C"},
        ]
        self.assertEqual(
            [row["RFC"] for row in scope_renewal_rows(rows, profile("ABBONDANZA"))],
            ["A"],
        )
        self.assertEqual(len(scope_renewal_rows(rows, profile(*PROMOTORIAS))), 3)

    def test_agent_directory_catalogs_are_built_from_visible_rows(self):
        directory = {
            "agents": [
                {"promotoria": "ABBONDANZA", "clasificacion_comercial": "NUEVO", "estatus_met": "ACTIVO"},
                {"promotoria": "TAIICO", "clasificacion_comercial": "ELITE", "estatus_met": "ACTIVO"},
            ],
            "catalogs": {},
        }
        scoped = scope_agent_directory(directory, profile("ABBONDANZA"))
        self.assertEqual(len(scoped["agents"]), 1)
        self.assertEqual(scoped["catalogs"]["promotorias"], ["ABBONDANZA"])
        self.assertEqual(scoped["catalogs"]["clasificaciones"], ["NUEVO"])

    def test_client_birthdays_are_scoped_and_summary_is_recalculated(self):
        result = {
            "generated_on": "2026-09-01",
            "clients": [
                {"promotoria": "ABBONDANZA", "birth_date": "1990-09-02", "days_until_birthday": 1},
                {"promotoria": "TAIICO", "birth_date": "1991-10-15", "days_until_birthday": 44},
            ],
            "summary": {"total_clients": 2, "birthdays_this_month": 1, "birthdays_next_30_days": 1},
        }
        with patch("services.cumpleanos.load_birthday_directory", return_value=result):
            scoped = birthday_clients(profile("ABBONDANZA"))
        self.assertEqual(len(scoped["clients"]), 1)
        self.assertEqual(scoped["summary"]["total_clients"], 1)
        self.assertEqual(scoped["summary"]["birthdays_this_month"], 1)

    def test_agent_birthdays_accept_any_assigned_promotoria(self):
        result = {
            "generated_on": "2026-09-01",
            "agents": [
                {"promotorias": ["ABBONDANZA", "TAIICO"], "birth_date": "1990-09-02", "days_until_birthday": 1},
                {"promotorias": ["CELAVI"], "birth_date": "1991-10-15", "days_until_birthday": 44},
            ],
            "summary": {"total_agents": 2, "birthdays_this_month": 1, "birthdays_next_30_days": 1},
        }
        with patch("services.cumpleanos_agentes.load_agent_birthday_directory", return_value=result):
            scoped = birthday_agents(profile("ABBONDANZA"))
        self.assertEqual(len(scoped["agents"]), 1)
        self.assertEqual(scoped["summary"]["total_agents"], 1)


if __name__ == "__main__":
    unittest.main()
