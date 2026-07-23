import os
import sys
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.mail_configuration import decrypt_password, encrypt_password
from services.session_auth import create_session_token, read_session_token, session_idle_seconds


class MailConfigurationSecurityTests(unittest.TestCase):
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
