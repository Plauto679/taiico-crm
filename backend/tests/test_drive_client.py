import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drive import client


class DriveClientTests(unittest.TestCase):
    def test_builds_an_independent_service_per_operation(self):
        services = [object(), object()]
        with patch("google.auth.default", return_value=(object(), None)), patch(
            "googleapiclient.discovery.build", side_effect=services
        ) as build:
            first = client.build_drive_service()
            second = client.build_drive_service()

        self.assertIs(first, services[0])
        self.assertIs(second, services[1])
        self.assertEqual(build.call_count, 2)

    def test_download_bytes_uses_authorized_requests_transport(self):
        response = Mock()
        response.content = b"xlsx-content"
        session = Mock()
        session.get.return_value = response

        with patch("google.auth.default", return_value=(object(), None)), patch(
            "google.auth.transport.requests.AuthorizedSession",
            return_value=session,
        ):
            result = client.download_drive_file_bytes("drive-file")

        self.assertEqual(result, b"xlsx-content")
        response.raise_for_status.assert_called_once_with()
        session.get.assert_called_once_with(
            "https://www.googleapis.com/drive/v3/files/drive-file",
            params={"alt": "media", "supportsAllDrives": "true"},
            timeout=120,
        )
        session.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
