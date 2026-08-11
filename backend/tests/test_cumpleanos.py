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
    filter_future_policy_records,
    parse_agent_lookup,
    parse_birth_date_from_rfc,
)


class BirthdayDirectoryTests(unittest.TestCase):
    def test_filters_policies_to_strictly_future_end_dates(self):
        today = datetime.date(2026, 8, 11)
        records = [
            {"policy_number": "future", "renewal_deadline": datetime.date(2026, 8, 12)},
            {"policy_number": "today", "renewal_deadline": "2026-08-11"},
            {"policy_number": "expired", "renewal_deadline": datetime.datetime(2026, 8, 10, 23, 59)},
            {"policy_number": "missing", "renewal_deadline": None},
            {"policy_number": "invalid", "renewal_deadline": "sin fecha"},
        ]

        future, summary = filter_future_policy_records(records, today=today)

        self.assertEqual([record["policy_number"] for record in future], ["future"])
        self.assertEqual(summary["policy_rows_total"], 5)
        self.assertEqual(summary["policy_rows_future"], 1)
        self.assertEqual(summary["policy_rows_expired_or_today"], 2)
        self.assertEqual(summary["policy_rows_missing_or_invalid_end_date"], 2)

    def test_birthday_directory_keeps_only_future_policies_and_clients(self):
        today = datetime.date(2026, 8, 11)
        records = [
            {
                "client_name": "Cliente Mixto",
                "rfc": "AAMA950203I52",
                "policy_number": "vigente",
                "product_branch": "GMM",
                "renewal_deadline": datetime.date(2027, 1, 1),
            },
            {
                "client_name": "Cliente Mixto",
                "rfc": "AAMA950203I52",
                "policy_number": "vencida",
                "product_branch": "VIDA",
                "renewal_deadline": datetime.date(2026, 1, 1),
            },
            {
                "client_name": "Cliente Vencido",
                "rfc": "GARC900101AA1",
                "policy_number": "expirada",
                "product_branch": "GMM",
                "renewal_deadline": datetime.date(2025, 1, 1),
            },
        ]

        future, _ = filter_future_policy_records(records, today=today)
        result = build_birthday_directory(future, {}, today=today)

        self.assertEqual(result["summary"]["total_clients"], 1)
        self.assertEqual(result["clients"][0]["client_name"], "Cliente Mixto")
        self.assertEqual(
            result["clients"][0]["policies"],
            [{"branch": "GMM", "policy_number": "vigente"}],
        )

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
                "Correo_Personal": "ALBERTO.ALFARO@TAIICO.COM",
            }
        ]).to_excel(output, sheet_name="Datos", index=False)

        agents = parse_agent_lookup(output.getvalue())

        self.assertEqual(
            agents["00123"].label,
            "AAMA950203I52 - Alberto Alfaro Mendoza",
        )
        self.assertEqual(agents["00123"].email, "alberto.alfaro@taiico.com")

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
