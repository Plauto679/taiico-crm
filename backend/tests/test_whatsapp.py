import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.whatsapp import (
    RenewalWhatsAppRequest,
    normalize_phone,
    renewal_message,
    template_payload,
    whatsapp_settings,
)


class WhatsAppTestModeTests(unittest.TestCase):
    def request(self):
        return RenewalWhatsAppRequest(
            client_name="Cliente Prueba",
            policy_number="1330274",
            period_start=2026,
            period_end=2027,
            agent_name="Agente Taiico",
        )

    def test_normalize_phone_uses_e164_digits(self):
        self.assertEqual(normalize_phone("+52 55 3074 1488"), "525530741488")

    def test_preview_message_contains_no_document_link(self):
        message = renewal_message(self.request())
        self.assertIn("1330274", message)
        self.assertIn("2026–2027", message)
        self.assertIn("no compartimos documentos sensibles", message)
        self.assertNotIn("http", message)

    def test_template_payload_maps_five_parameters(self):
        payload = template_payload(self.request(), "525530741488", "renewal_ready_test")
        parameters = payload["template"]["components"][0]["parameters"]
        self.assertEqual(payload["to"], "525530741488")
        self.assertEqual([item["text"] for item in parameters], [
            "Cliente Prueba", "1330274", "2026", "2027", "Agente Taiico"
        ])

    def test_settings_require_test_mode(self):
        environment = {
            "WHATSAPP_ACCESS_TOKEN": "token",
            "WHATSAPP_PHONE_NUMBER_ID": "phone-id",
            "WHATSAPP_API_VERSION": "vXX.X",
            "WHATSAPP_RENEWAL_TEMPLATE_NAME": "renewal_ready_test",
            "WHATSAPP_TEST_RECIPIENT": "525530741488",
            "WHATSAPP_TEST_MODE": "false",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(RuntimeError, "WHATSAPP_TEST_MODE"):
                whatsapp_settings()


if __name__ == "__main__":
    unittest.main()
