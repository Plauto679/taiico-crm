import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drive.scanner import FILE_METADATA_FIELDS, get_drive_file


class DriveScannerTests(unittest.TestCase):
    def test_get_drive_file_reads_canonical_file_metadata(self):
        service = MagicMock()
        request = service.files.return_value.get.return_value
        request.execute.return_value = {
            "id": "canonical-file-id",
            "name": "Source.xlsx",
        }

        result = get_drive_file(service, "canonical-file-id")

        service.files.return_value.get.assert_called_once_with(
            fileId="canonical-file-id",
            fields=FILE_METADATA_FIELDS,
            supportsAllDrives=True,
        )
        self.assertEqual(result["id"], "canonical-file-id")


if __name__ == "__main__":
    unittest.main()
