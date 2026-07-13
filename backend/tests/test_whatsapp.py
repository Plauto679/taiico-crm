import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.whatsapp import (
    RenewalWhatsAppRequest,
    configured_test_recipients,
    normalize_phone,
    renewal_message,
    send_test_renewal_whatsapp_to_configured_recipients,
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
            "WHATSAPP_TEST_RECIPIENTS": "525530741488",
            "WHATSAPP_TEST_MODE": "false",
        }
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaisesRegex(RuntimeError, "WHATSAPP_TEST_MODE"):
                whatsapp_settings()

    def test_configured_recipients_are_deduplicated(self):
        settings = {"test_recipients": "525530741488,+52 55 3905 4301,525530741488"}
        with patch.dict(
            os.environ,
            {"WHATSAPP_TEST_ALLOWLIST": "525530741488,525539054301"},
            clear=True,
        ):
            self.assertEqual(
                configured_test_recipients(settings),
                ["525530741488", "525539054301"],
            )

    def test_every_configured_recipient_must_be_allowlisted(self):
        settings = {"test_recipients": "525530741488,525522414586"}
        with patch.dict(
            os.environ,
            {"WHATSAPP_TEST_ALLOWLIST": "525530741488"},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "Every WhatsApp test recipient"):
                configured_test_recipients(settings)


class WhatsAppMultipleRecipientTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_attempts_each_configured_recipient(self):
        request = RenewalWhatsAppRequest(
            client_name="Cliente Prueba",
            policy_number="1330274",
            period_start=2026,
            period_end=2027,
            agent_name="Agente Taiico",
        )
        environment = {
            "WHATSAPP_ACCESS_TOKEN": "token",
            "WHATSAPP_PHONE_NUMBER_ID": "phone-id",
            "WHATSAPP_API_VERSION": "v25.0",
            "WHATSAPP_RENEWAL_TEMPLATE_NAME": "renewal_ready_test",
            "WHATSAPP_TEST_RECIPIENTS": "525530741488,525539054301",
            "WHATSAPP_TEST_ALLOWLIST": "525530741488,525539054301",
            "WHATSAPP_TEST_MODE": "true",
        }

        class FakeResponse:
            def __init__(self, message_id):
                self.message_id = message_id

            def json(self):
                return {"messages": [{"id": self.message_id}]}

            def raise_for_status(self):
                return None

        class FakeClient:
            def __init__(self, *args, **kwargs):
                self.posts = []

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

            async def post(self, url, headers, json):
                self.posts.append(json["to"])
                return FakeResponse(f"message-{len(self.posts)}")

        fake_client = FakeClient()
        with (
            patch.dict(os.environ, environment, clear=True),
            patch("services.whatsapp.httpx.AsyncClient", return_value=fake_client),
            patch("services.whatsapp.record_action") as record_action,
        ):
            result = await send_test_renewal_whatsapp_to_configured_recipients(request)

        self.assertEqual(fake_client.posts, ["525530741488", "525539054301"])
        self.assertEqual(result["sent_count"], 2)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(record_action.call_count, 2)


if __name__ == "__main__":
    unittest.main()
