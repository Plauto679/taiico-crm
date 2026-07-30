import datetime
import io
import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.cumpleanos_agentes import build_agent_birthday_directory


def workbook_bytes(rows):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="Datos", index=False)
    return output.getvalue()


class AgentBirthdayDirectoryTests(unittest.TestCase):
    def test_builds_directory_and_aggregates_duplicate_rfc(self):
        workbook = workbook_bytes([
            {
                "RFC": "AAMA950203I52",
                "Nombres": "ALBERTO",
                "Apellido_Paterno": "ALFARO",
                "Apellido_Materno": "MENDOZA",
                "CLAVE_DEFINITIVA": "12345",
                "Promotoria": "TAIICO",
                "Correo_Personal": "alberto@example.com",
                "Estado": "ACTIVO",
            },
            {
                "RFC": "AAMA950203I52",
                "Nombres": "ALBERTO",
                "Apellido_Paterno": "ALFARO",
                "Apellido_Materno": "MENDOZA",
                "CLAVE_DEFINITIVA": "67890",
                "Promotoria": "TAIICO",
                "Correo_Personal": "alberto@example.com",
                "Estado": "ACTIVO",
            },
            {
                "RFC": "RFC-INVALIDO",
                "Nombres": "PERSONA",
                "CLAVE_DEFINITIVA": "99999",
                "Promotoria": "TAIICO",
            },
            {
                "RFC": "",
                "Nombres": "SIN RFC",
                "CLAVE_DEFINITIVA": "11111",
                "Promotoria": "TAIICO",
            },
        ])

        result = build_agent_birthday_directory(
            workbook,
            today=datetime.date(2026, 1, 30),
        )

        self.assertEqual(result["summary"]["total_agents"], 1)
        self.assertEqual(result["summary"]["birthdays_next_30_days"], 1)
        self.assertEqual(result["summary"]["invalid_rfc_rows"], 1)
        self.assertEqual(result["summary"]["missing_rfc_rows"], 1)
        self.assertEqual(result["summary"]["duplicate_rows"], 1)
        agent = result["agents"][0]
        self.assertEqual(agent["agent_name"], "Alberto Alfaro Mendoza")
        self.assertEqual(agent["birth_date"], "1995-02-03")
        self.assertEqual(agent["days_until_birthday"], 4)
        self.assertEqual(agent["definitive_keys"], ["12345", "67890"])
        self.assertEqual(agent["promotorias"], ["TAIICO"])

    def test_rejects_workbook_without_required_columns(self):
        workbook = workbook_bytes([{"RFC": "AAMA950203I52"}])

        with self.assertRaisesRegex(ValueError, "Promotoria"):
            build_agent_birthday_directory(workbook)


if __name__ == "__main__":
    unittest.main()
