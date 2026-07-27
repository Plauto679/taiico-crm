import io
import os
import sys
import unittest
import zipfile
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

    def test_updates_only_registered_users_password_and_preserves_other_sheets(self):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            pd.DataFrame([
                {"Usuario": "person@example.com", "Password": "old-secret", "Rol": "Admin"},
                {"Usuario": "other@example.com", "Password": "untouched", "Rol": "User"},
            ]).to_excel(writer, sheet_name="Usuarios", index=False)
            pd.DataFrame([{"Dato": "preservado"}]).to_excel(
                writer,
                sheet_name="Configuracion",
                index=False,
            )

        uploaded = {}
        with patch.dict(
            os.environ,
            {auth.USERS_FILE_ID_ENV: "users-file-id"},
            clear=True,
        ), patch.object(
            auth,
            "_download_users_workbook",
            return_value=output.getvalue(),
        ), patch.object(
            auth,
            "_upload_users_workbook",
            side_effect=lambda file_id, content: uploaded.update(
                {"file_id": file_id, "content": content}
            ),
        ):
            auth.update_password("PERSON@example.com", "new-secret")

        self.assertEqual(uploaded["file_id"], "users-file-id")
        sheets = pd.read_excel(
            io.BytesIO(uploaded["content"]),
            sheet_name=None,
            dtype=str,
            keep_default_na=False,
        )
        self.assertEqual(sheets["Usuarios"].iloc[0]["Password"], "new-secret")
        self.assertEqual(sheets["Usuarios"].iloc[1]["Password"], "untouched")
        self.assertEqual(sheets["Configuracion"].iloc[0]["Dato"], "preservado")

    def test_password_update_preserves_all_non_target_ooxml_bytes(self):
        original = workbook_bytes([
            {"Usuario": "person@example.com", "Password": "old-secret"},
            {"Usuario": "other@example.com", "Password": "untouched"},
        ])

        updated = auth._replace_password_in_xlsx(
            original,
            "person@example.com",
            "new-&-secret",
        )

        with zipfile.ZipFile(io.BytesIO(original)) as original_archive, zipfile.ZipFile(
            io.BytesIO(updated)
        ) as updated_archive:
            self.assertEqual(
                original_archive.namelist(),
                updated_archive.namelist(),
            )
            for name in original_archive.namelist():
                if name != "xl/worksheets/sheet1.xml":
                    self.assertEqual(
                        original_archive.read(name),
                        updated_archive.read(name),
                        name,
                    )

            original_sheet = original_archive.read("xl/worksheets/sheet1.xml")
            updated_sheet = updated_archive.read("xl/worksheets/sheet1.xml")
            self.assertEqual(
                original_sheet.split(b"<sheetData", 1)[0],
                updated_sheet.split(b"<sheetData", 1)[0],
            )
            self.assertNotIn(b"<ns0:", updated_sheet)
            self.assertNotIn(b"<s:", updated_sheet)

        credentials = auth._read_credentials(updated)
        self.assertEqual(credentials["person@example.com"], "new-&-secret")
        self.assertEqual(credentials["other@example.com"], "untouched")

    def test_update_rejects_unregistered_user_without_upload(self):
        workbook = workbook_bytes([
            {"Usuario": "person@example.com", "Password": "local-secret"},
        ])
        with patch.dict(
            os.environ,
            {auth.USERS_FILE_ID_ENV: "users-file-id"},
            clear=True,
        ), patch.object(
            auth,
            "_download_users_workbook",
            return_value=workbook,
        ), patch.object(auth, "_upload_users_workbook") as upload:
            with self.assertRaises(KeyError):
                auth.update_password("missing@example.com", "new-secret")
        upload.assert_not_called()


if __name__ == "__main__":
    unittest.main()
