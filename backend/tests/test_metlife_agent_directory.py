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


if __name__ == "__main__":
    unittest.main()
