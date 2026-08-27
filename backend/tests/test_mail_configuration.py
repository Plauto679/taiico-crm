import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from cryptography.fernet import Fernet

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.mail_configuration import decrypt_password, encrypt_password, smtp_settings_for_email_address
from services.session_auth import create_session_token, read_session_token, session_idle_seconds


class MailConfigurationSecurityTests(unittest.TestCase):
    def test_settings_can_be_resolved_by_actual_sender_address(self):
        key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"MAIL_CREDENTIALS_ENCRYPTION_KEY": key}):
            item = type(
                "MailConfig",
                (),
                {
                    "smtp_host": "smtp.gmail.com",
                    "smtp_port": 587,
                    "email_address": "clientes@taiico.com",
                    "encrypted_password": encrypt_password("app-password"),
                    "use_starttls": True,
                },
            )()
            query = MagicMock()
            query.filter.return_value.first.return_value = item
            db = MagicMock()
            db.query.return_value = query
            with patch("services.mail_configuration.SessionLocal", return_value=db):
                settings = smtp_settings_for_email_address(" CLIENTES@TAIICO.COM ")

        self.assertEqual(settings["sender"], "clientes@taiico.com")
        self.assertEqual(settings["user"], "clientes@taiico.com")
        self.assertEqual(settings["password"], "app-password")

    def test_mail_password_is_encrypted_and_can_be_decrypted(self):
        key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"MAIL_CREDENTIALS_ENCRYPTION_KEY": key}):
            encrypted = encrypt_password("abcd efgh ijkl mnop")
            self.assertNotIn("abcdefghijklmnop", encrypted)
            self.assertEqual(decrypt_password(encrypted), "abcdefghijklmnop")

    def test_signed_session_preserves_normalized_username(self):
        with patch.dict(os.environ, {"AUTH_SESSION_SECRET": "test-secret-that-is-not-used-in-production"}):
            token = create_session_token(" User@TAIICO.COM ")
            self.assertEqual(read_session_token(token), "user@taiico.com")

    def test_tampered_session_is_rejected(self):
        with patch.dict(os.environ, {"AUTH_SESSION_SECRET": "test-secret-that-is-not-used-in-production"}):
            token = create_session_token("user@taiico.com")
            with self.assertRaises(Exception):
                read_session_token(token + "x")

    def test_session_idle_timeout_defaults_to_one_hour(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AUTH_SESSION_IDLE_SECONDS", None)
            self.assertEqual(session_idle_seconds(), 3600)

    def test_session_idle_timeout_is_bounded(self):
        with patch.dict(os.environ, {"AUTH_SESSION_IDLE_SECONDS": "30"}):
            self.assertEqual(session_idle_seconds(), 300)


if __name__ == "__main__":
    unittest.main()
