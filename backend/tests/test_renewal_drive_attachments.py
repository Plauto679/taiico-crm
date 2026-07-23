import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.renovaciones import (
    DRIVE_FOLDER_MIME_TYPE,
    DriveAttachmentError,
    SmtpDeliveryUncertainError,
    drive_file_id_from_url,
    drive_folder_attachments,
    send_email_smtp,
)


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeDriveFiles:
    def __init__(self, items):
        self.items = items

    def get(self, **_kwargs):
        return FakeRequest({"id": "folder-id", "name": "Expediente", "mimeType": DRIVE_FOLDER_MIME_TYPE})

    def list(self, **_kwargs):
        return FakeRequest({"files": self.items})


class FakeDriveService:
    def __init__(self, items):
        self.resource = FakeDriveFiles(items)

    def files(self):
        return self.resource


class FakeSmtp:
    sent_message = None

    def __init__(self, _host, _port, timeout=None):
        self.timeout = timeout
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def starttls(self, context=None):
        pass

    def ehlo(self):
        pass

    def login(self, _user, _password):
        pass

    def send_message(self, message):
        type(self).sent_message = message


class RenewalDriveAttachmentTests(unittest.TestCase):
    def test_drive_folder_id_is_parsed_from_supported_urls(self):
        self.assertEqual(
            drive_file_id_from_url("https://drive.google.com/open?id=folder_123-ABC&usp=drive_fs"),
            "folder_123-ABC",
        )
        self.assertEqual(
            drive_file_id_from_url("https://drive.google.com/drive/folders/folder_123-ABC"),
            "folder_123-ABC",
        )
        self.assertIsNone(drive_file_id_from_url("https://example.com/open?id=folder_123-ABC"))

    def test_every_direct_file_is_returned_as_an_attachment(self):
        items = [
            {"id": "one", "name": "Carátula.pdf", "mimeType": "application/pdf", "size": "4"},
            {"id": "two", "name": "Aviso.xml", "mimeType": "application/xml", "size": "5"},
        ]
        service = FakeDriveService(items)
        with patch(
            "services.renovaciones._drive_attachment_content",
            side_effect=[
                (b"pdf!", "Carátula.pdf", "application/pdf"),
                (b"xml!!", "Aviso.xml", "application/xml"),
            ],
        ):
            attachments = drive_folder_attachments(
                "https://drive.google.com/open?id=folder-id",
                service=service,
                max_bytes=100,
                max_count=10,
            )
        self.assertEqual([item["name"] for item in attachments], ["Carátula.pdf", "Aviso.xml"])
        self.assertEqual(sum(len(item["content"]) for item in attachments), 9)

    def test_nested_folders_stop_email_instead_of_silently_omitting_files(self):
        service = FakeDriveService([
            {"id": "nested", "name": "Subcarpeta", "mimeType": DRIVE_FOLDER_MIME_TYPE},
        ])
        with self.assertRaisesRegex(DriveAttachmentError, "subcarpetas"):
            drive_folder_attachments(
                "https://drive.google.com/open?id=folder-id",
                service=service,
                max_bytes=100,
                max_count=10,
            )

    def test_known_attachment_size_is_checked_before_download(self):
        service = FakeDriveService([
            {"id": "large", "name": "Grande.pdf", "mimeType": "application/pdf", "size": "101"},
        ])
        with patch("services.renovaciones._drive_attachment_content") as download:
            with self.assertRaisesRegex(DriveAttachmentError, "límite seguro"):
                drive_folder_attachments(
                    "https://drive.google.com/open?id=folder-id",
                    service=service,
                    max_bytes=100,
                    max_count=10,
                )
            download.assert_not_called()

    def test_zero_byte_drive_files_are_still_attached(self):
        FakeSmtp.sent_message = None
        with patch("services.renovaciones.smtplib.SMTP", FakeSmtp):
            send_email_smtp(
                "Renovación",
                "Contenido",
                ["cliente@example.com"],
                [{"name": "vacio.pdf", "content": b"", "mime_type": "application/pdf"}],
                cc_recipients=[
                    "alberto.alfaro@taiico.com",
                    "veronica.alfaro@taiico.com",
                    "pamela.alfaro@taiico.com",
                ],
                settings={
                    "host": "smtp.example.com",
                    "port": 587,
                    "user": "user",
                    "password": "secret",
                    "sender": "sender@example.com",
                    "use_starttls": True,
                },
            )
        attachments = list(FakeSmtp.sent_message.iter_attachments())
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get_filename(), "vacio.pdf")
        self.assertEqual(attachments[0].get_payload(decode=True), b"")
        self.assertEqual(FakeSmtp.sent_message["To"], "cliente@example.com")
        self.assertEqual(
            FakeSmtp.sent_message["Cc"],
            "alberto.alfaro@taiico.com, veronica.alfaro@taiico.com, pamela.alfaro@taiico.com",
        )

    def test_broken_pipe_is_reported_as_uncertain_without_retry(self):
        class BrokenSmtp(FakeSmtp):
            attempts = 0

            def starttls(self, context=None):
                pass

            def send_message(self, _message):
                type(self).attempts += 1
                raise BrokenPipeError(32, "Broken pipe")

        BrokenSmtp.attempts = 0
        with patch("services.renovaciones.smtplib.SMTP", BrokenSmtp):
            with self.assertRaisesRegex(SmtpDeliveryUncertainError, "Enviados"):
                send_email_smtp(
                    "Renovación",
                    "Contenido",
                    ["cliente@example.com"],
                    settings={
                        "host": "smtp.gmail.com",
                        "port": 587,
                        "user": "user",
                        "password": "secret",
                        "sender": "sender@example.com",
                        "use_starttls": True,
                    },
                )
        self.assertEqual(BrokenSmtp.attempts, 1)


if __name__ == "__main__":
    unittest.main()
