import io
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import auth


def workbook_bytes(rows):
    output = io.BytesIO()
    pd.DataFrame(rows).to_excel(output, index=False)
    return output.getvalue()


class WorkbookAuthenticationTests(unittest.TestCase):
    def setUp(self):
        auth.clear_credentials_cache()

    def tearDown(self):
        auth.clear_credentials_cache()

    def test_validates_user_and_password_from_workbook(self):
        workbook = workbook_bytes([
            {"Usuario": "person@example.com", "Password": "local-secret"},
        ])
        environment = {
            auth.USERS_FILE_ID_ENV: "users-file-id",
            auth.USERS_CACHE_SECONDS_ENV: "300",
        }
        with patch.dict(os.environ, environment, clear=True), patch.object(
            auth, "_download_users_workbook", return_value=workbook
        ):
            self.assertTrue(auth.verify_credentials("person@example.com", "local-secret"))
            self.assertFalse(auth.verify_credentials("person@example.com", "wrong"))

    def test_username_is_case_insensitive_and_trimmed(self):
        workbook = workbook_bytes([
            {"Usuario": "Person@Example.com", "Password": "local-secret"},
        ])
        with patch.dict(
            os.environ, {auth.USERS_FILE_ID_ENV: "users-file-id"}, clear=True
        ), patch.object(auth, "_download_users_workbook", return_value=workbook):
            self.assertTrue(auth.verify_credentials(" person@example.COM ", "local-secret"))

    def test_cache_avoids_repeated_drive_downloads(self):
        workbook = workbook_bytes([
            {"Usuario": "person@example.com", "Password": "local-secret"},
        ])
        with patch.dict(
            os.environ, {auth.USERS_FILE_ID_ENV: "users-file-id"}, clear=True
        ), patch.object(
            auth, "_download_users_workbook", return_value=workbook
        ) as download:
            auth.verify_credentials("person@example.com", "local-secret")
            auth.verify_credentials("person@example.com", "local-secret")
            download.assert_called_once_with("users-file-id")

    def test_fails_closed_when_drive_is_unavailable(self):
        with patch.dict(
            os.environ, {auth.USERS_FILE_ID_ENV: "users-file-id"}, clear=True
        ), patch.object(
            auth, "_download_users_workbook", side_effect=RuntimeError("offline")
        ):
            self.assertFalse(auth.verify_credentials("person@example.com", "local-secret"))

    def test_fails_closed_when_required_columns_are_missing(self):
        workbook = workbook_bytes([{"Email": "person@example.com"}])
        with patch.dict(
            os.environ, {auth.USERS_FILE_ID_ENV: "users-file-id"}, clear=True
        ), patch.object(auth, "_download_users_workbook", return_value=workbook):
            self.assertFalse(auth.verify_credentials("person@example.com", "local-secret"))


if __name__ == "__main__":
    unittest.main()
