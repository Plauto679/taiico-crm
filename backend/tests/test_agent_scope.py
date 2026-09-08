from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.agent_scope import (
    profile_allows_agent_key,
    profile_allows_insurer,
    resolve_agent_scope,
)
from services.auth import AccessProfile
from services.renovaciones import scope_renewal_rows


def agent_profile(*, permission: str = "lectura") -> AccessProfile:
    return AccessProfile(
        username="ana@example.com",
        role="agente",
        promotorias=("TAIICO",),
        rfc="BEOA8712265F1",
        aseguradoras=("METLIFE",),
        module_permissions={"renovaciones": permission, "finanzas": "operacion"},
    )


DIRECTORY = [
    {
        "rfc": "BEOA8712265F1",
        "name": "ANA VICTORIA BECERRA OCAMPO",
        "promotoria": "TAIICO",
        "start_key": "001234",
        "definitive_key": "014883",
    }
]


class AgentScopeTests(unittest.TestCase):
    @patch("services.agent_scope.load_agent_directory", return_value=DIRECTORY)
    def test_resolves_both_start_and_definitive_keys(self, _load):
        scope = resolve_agent_scope(agent_profile())
        self.assertEqual(scope.keys, frozenset({"1234", "14883"}))
        self.assertTrue(profile_allows_agent_key(agent_profile(), "000014883"))
        self.assertTrue(profile_allows_agent_key(agent_profile(), "1234"))
        self.assertFalse(profile_allows_agent_key(agent_profile(), "99999"))

    @patch("services.agent_scope.load_agent_directory", return_value=[])
    def test_missing_link_fails_closed(self, _load):
        self.assertFalse(profile_allows_agent_key(agent_profile(), "14883"))

    @patch(
        "services.agent_scope.load_agent_directory",
        return_value=[{**DIRECTORY[0], "status": "Inactiva"}],
    )
    def test_inactive_agent_fails_closed(self, _load):
        scope = resolve_agent_scope(agent_profile())
        self.assertEqual(scope.keys, frozenset())
        self.assertFalse(profile_allows_agent_key(agent_profile(), "14883"))

    @patch("services.agent_scope.load_agent_directory", return_value=DIRECTORY)
    def test_renewals_only_include_linked_key(self, _load):
        rows = [
            {"AGENTE": "14883", "PROMOTORIA": "TAIICO", "POLIZA": "OWN"},
            {"AGENTE": "99999", "PROMOTORIA": "TAIICO", "POLIZA": "OTHER"},
            {"AGENTE": "", "PROMOTORIA": "TAIICO", "POLIZA": "UNASSIGNED"},
        ]
        self.assertEqual(
            [row["POLIZA"] for row in scope_renewal_rows(rows, agent_profile())],
            ["OWN"],
        )

    def test_insurer_selection_is_enforced(self):
        self.assertTrue(profile_allows_insurer(agent_profile(), "metlife"))
        self.assertFalse(profile_allows_insurer(agent_profile(), "sura"))

    def test_operation_is_enabled_only_for_secured_agent_modules(self):
        self.assertTrue(agent_profile(permission="operacion").can_operate("renovaciones"))
        self.assertFalse(agent_profile().can_operate("renovaciones"))
        self.assertFalse(agent_profile().can_operate("finanzas"))


if __name__ == "__main__":
    unittest.main()
