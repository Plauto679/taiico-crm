import unittest

from pydantic import ValidationError

from backend.services.auth import AccessProfile
from backend.services.cotizaciones import QuoteCreate, QuoteUpdate, assigned_agent, parse_agent_directory
from unittest.mock import patch
from openpyxl import Workbook
import io


class QuoteCreateTests(unittest.TestCase):
    def test_accepts_existing_client_with_matching_product(self):
        payload = QuoteCreate(client_id="client-1", ramo="GMM", producto="Primordial")
        self.assertEqual(payload.ramo, "GMM")

    def test_accepts_prospect_without_rfc(self):
        payload = QuoteCreate(prospect_name="Prospecto Uno", ramo="Vida", producto="Flexilife")
        self.assertEqual(payload.prospect_name, "Prospecto Uno")

    def test_rejects_product_from_other_branch(self):
        with self.assertRaises(ValidationError):
            QuoteCreate(prospect_name="Prospecto", ramo="GMM", producto="Totalife")

    def test_requires_exactly_one_client_source(self):
        with self.assertRaises(ValidationError):
            QuoteCreate(ramo="Vida", producto="Metalife")

    def test_update_allows_empty_rfc(self):
        payload = QuoteUpdate(
            cliente="Cliente sin RFC", rfc="", ramo="GMM", producto="Primordial"
        )
        self.assertEqual(payload.rfc, "")

    def test_agent_key_prefers_definitive_and_falls_back_to_start(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Datos"
        sheet.append([
            "RFC", "Promotoria", "CLAVE_DEFINITIVA", "CLAVE_ARRANQUE",
            "Nombres", "Apellido_Paterno", "Apellido_Materno",
        ])
        sheet.append(["RFC1", "TAIICO", "73640", "34548", "VERONICA", "ALFARO", "MENDOZA"])
        sheet.append(["RFC2", "TAIICO", "", "37172", "KARLA", "PEÑA", "RUIZ"])
        output = io.BytesIO()
        workbook.save(output)
        agents = parse_agent_directory(output.getvalue())
        self.assertEqual(agents[0]["key"], "37172")
        self.assertEqual(agents[0]["key_source"], "CLAVE_ARRANQUE")
        self.assertEqual(agents[1]["key"], "73640")
        self.assertEqual(agents[1]["key_source"], "CLAVE_DEFINITIVA")

    def test_agent_user_is_assigned_from_profile_rfc(self):
        profile = AccessProfile(
            username="agent@example.com", role="agente", promotorias=("TAIICO",),
            rfc="RFC1", aseguradoras=("METLIFE",), module_permissions={"cotizaciones": "lectura"},
        )
        options = [{"rfc": "RFC1", "name": "Agente Uno", "promotoria": "TAIICO", "key": "123", "key_source": "CLAVE_DEFINITIVA"}]
        with patch("backend.services.cotizaciones.load_agent_directory", return_value=options):
            self.assertEqual(assigned_agent(profile, None)["key"], "123")


if __name__ == "__main__":
    unittest.main()
