import io
import os
import sys
import unittest
from pathlib import Path

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.client_email_directory import normalize_client_name, parse_email_directory
from services.renovaciones import build_metlife_gmm_renewal_email_body, renewal_email_recipients


def workbook_bytes(rows):
    output = io.BytesIO()
    pd.DataFrame(rows).to_excel(output, index=False)
    return output.getvalue()


class ClientEmailDirectoryTests(unittest.TestCase):
    def test_name_matching_ignores_accents_case_and_repeated_spaces(self):
        self.assertEqual(
            normalize_client_name("  DÁNTE   Morales Nájera "),
            normalize_client_name("dante morales najera"),
        )

    def test_ambiguous_names_are_not_automatically_selected(self):
        directory, ambiguous = parse_email_directory(workbook_bytes([
            {"Clientes": "Cliente Duplicado", "Mail": "one@example.com"},
            {"Clientes": "Cliente Duplicado", "Mail": "two@example.com"},
            {"Clientes": "Cliente Único", "Mail": "unique@example.com"},
        ]))
        self.assertIn(normalize_client_name("Cliente Duplicado"), ambiguous)
        self.assertNotIn(normalize_client_name("Cliente Duplicado"), directory)
        self.assertEqual(directory[normalize_client_name("Cliente Unico")], "unique@example.com")

    def test_metlife_gmm_internal_template_displays_intended_client_email(self):
        body = build_metlife_gmm_renewal_email_body(
            "Dante Morales Najera",
            "dante.morales@example.com",
            "1357138",
            "2026-07-13",
        )
        self.assertIn("Hola Dante Morales Najera, (dante.morales@example.com)", body)
        self.assertIn("periodo 2026 - 2027", body)
        self.assertIn("únicamente al equipo interno", body)

    def test_internal_only_mode_never_uses_client_as_actual_recipient(self):
        from unittest.mock import patch

        with patch.dict(os.environ, {
            "RENEWAL_EMAIL_INTERNAL_ONLY": "true",
            "RENEWAL_EMAIL_INTERNAL_RECIPIENTS": "operations@example.com",
        }, clear=False):
            self.assertEqual(
                renewal_email_recipients("client@example.com"),
                ["operations@example.com"],
            )


if __name__ == "__main__":
    unittest.main()
