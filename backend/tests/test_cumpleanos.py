import datetime
import io
import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.cumpleanos import (
    AgentRecord,
    build_birthday_directory,
    parse_agent_lookup,
    parse_birth_date_from_rfc,
)


class BirthdayDirectoryTests(unittest.TestCase):
    def test_derives_birth_date_from_person_rfc(self):
        self.assertEqual(
            parse_birth_date_from_rfc(
                "AAMA950203I52",
                today=datetime.date(2026, 7, 29),
            ),
            datetime.date(1995, 2, 3),
        )

    def test_rejects_company_and_invalid_dates(self):
        today = datetime.date(2026, 7, 29)
        self.assertIsNone(parse_birth_date_from_rfc("ABC950203I52", today=today))
        self.assertIsNone(parse_birth_date_from_rfc("AAMA951332I52", today=today))

    def test_resolves_current_century_for_recent_birth_year(self):
        self.assertEqual(
            parse_birth_date_from_rfc(
                "AAMA100203I52",
                today=datetime.date(2026, 7, 29),
            ),
            datetime.date(2010, 2, 3),
        )

    def test_agent_lookup_uses_clave_definitiva(self):
        output = io.BytesIO()
        pd.DataFrame([
            {
                "CLAVE_DEFINITIVA": "00123",
                "RFC": "AAMA950203I52",
                "Nombres": "Alberto",
                "Apellido_Paterno": "Alfaro",
                "Apellido_Materno": "Mendoza",
                "Promotoria": "TAIICO",
            }
        ]).to_excel(output, sheet_name="Datos", index=False)

        agents = parse_agent_lookup(output.getvalue())

        self.assertEqual(
            agents["00123"].label,
            "AAMA950203I52 - Alberto Alfaro Mendoza",
        )

    def test_groups_policies_and_crosses_canonical_agent(self):
        records = [
            {
                "client_name": "Cliente Uno",
                "rfc": "AAMA950203I52",
                "policy_number": "123",
                "product_branch": "GMM",
                "agent_code": "00123",
                "agent_name": "Nombre anterior",
                "promotoria": "OTRA",
            },
            {
                "client_name": "Cliente Uno",
                "rfc": "AAMA950203I52",
                "policy_number": "456",
                "product_branch": "VIDA",
                "agent_code": "00123",
            },
        ]
        agents = {
            "00123": AgentRecord(
                rfc="AGEX900101AA1",
                name="Agente Canónico",
                promotoria="TAIICO",
            )
        }

        result = build_birthday_directory(
            records,
            agents,
            today=datetime.date(2026, 1, 30),
        )

        self.assertEqual(result["summary"]["total_clients"], 1)
        client = result["clients"][0]
        self.assertEqual(client["agent_label"], "AGEX900101AA1 - Agente Canónico")
        self.assertEqual(client["promotoria"], "TAIICO")
        self.assertEqual(client["days_until_birthday"], 4)
        self.assertEqual(
            client["policies"],
            [
                {"branch": "GMM", "policy_number": "123"},
                {"branch": "VIDA", "policy_number": "456"},
            ],
        )
