from __future__ import annotations

import io
import unittest
from unittest.mock import patch

import pandas as pd

from services import metlife_agent_directory


def workbook_bytes(rows: list[dict[str, str]]) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="Datos", index=False)
    return output.getvalue()


class MetlifeAgentDirectoryTests(unittest.TestCase):
    def tearDown(self) -> None:
        metlife_agent_directory._cache = None

    def test_indexes_promotoria_by_definitive_or_start_key(self):
        payload = workbook_bytes(
            [
                {"Promotoria": "TAIICO", "CLAVE_DEFINITIVA": "73640", "CLAVE_ARRANQUE": "111"},
                {"Promotoria": "SOCIOS", "CLAVE_DEFINITIVA": "", "CLAVE_ARRANQUE": "0016200"},
            ]
        )
        with patch.object(metlife_agent_directory, "download_drive_file_bytes", return_value=payload):
            indexed = metlife_agent_directory.promotoria_by_agent_key()

        self.assertEqual(indexed["73640"], "TAIICO")
        self.assertEqual(indexed["0016200"], "SOCIOS")

    def test_does_not_guess_when_key_belongs_to_multiple_promoterias(self):
        payload = workbook_bytes(
            [
                {"Promotoria": "UNO", "CLAVE_DEFINITIVA": "70151", "CLAVE_ARRANQUE": ""},
                {"Promotoria": "DOS", "CLAVE_DEFINITIVA": "70151", "CLAVE_ARRANQUE": ""},
            ]
        )
        with patch.object(metlife_agent_directory, "download_drive_file_bytes", return_value=payload):
            indexed = metlife_agent_directory.promotoria_by_agent_key()

        self.assertNotIn("70151", indexed)

    def test_resolves_contact_by_definitive_or_start_key(self):
        payload = workbook_bytes(
            [
                {
                    "Promotoria": "SOCIOS",
                    "CLAVE_DEFINITIVA": "70151",
                    "CLAVE_ARRANQUE": "30151",
                    "Nombre_s": "ANA",
                    "Apellido_Paterno": "PEREZ",
                    "Apellido_Materno": "LOPEZ",
                    "Correo_Personal": "ana@example.com",
                }
            ]
        )
        with patch.object(
            metlife_agent_directory,
            "download_drive_file_bytes",
            return_value=payload,
        ):
            definitive = metlife_agent_directory.resolve_agent_contact("70151")
            metlife_agent_directory.clear_agent_directory_cache()
            start = metlife_agent_directory.resolve_agent_contact("30151")

        self.assertEqual(definitive["email"], "ana@example.com")
        self.assertEqual(definitive["name"], "ANA PEREZ LOPEZ")
        self.assertEqual(start["email"], "ana@example.com")

    def test_rejects_missing_ambiguous_or_invalid_agent_contact(self):
        payload = workbook_bytes(
            [
                {
                    "Promotoria": "UNO",
                    "CLAVE_DEFINITIVA": "70151",
                    "CLAVE_ARRANQUE": "",
                    "Correo_Personal": "invalid-email",
                },
                {
                    "Promotoria": "DOS",
                    "CLAVE_DEFINITIVA": "88888",
                    "CLAVE_ARRANQUE": "70151",
                    "Correo_Personal": "dos@example.com",
                },
            ]
        )
        with patch.object(
            metlife_agent_directory,
            "download_drive_file_bytes",
            return_value=payload,
        ):
            with self.assertRaisesRegex(
                metlife_agent_directory.AgentContactResolutionError,
                "duplicada o ambigua",
            ):
                metlife_agent_directory.resolve_agent_contact("70151")
            with self.assertRaisesRegex(
                metlife_agent_directory.AgentContactResolutionError,
                "no encontrada",
            ):
                metlife_agent_directory.resolve_agent_contact("99999")

        invalid_payload = workbook_bytes(
            [
                {
                    "Promotoria": "UNO",
                    "CLAVE_DEFINITIVA": "70151",
                    "CLAVE_ARRANQUE": "",
                    "Correo_Personal": "invalid-email",
                }
            ]
        )
        metlife_agent_directory.clear_agent_directory_cache()
        with patch.object(
            metlife_agent_directory,
            "download_drive_file_bytes",
            return_value=invalid_payload,
        ):
            with self.assertRaisesRegex(
                metlife_agent_directory.AgentContactResolutionError,
                "Correo_Personal válido",
            ):
                metlife_agent_directory.resolve_agent_contact("70151")


if __name__ == "__main__":
    unittest.main()
