import sys
import unittest
from pathlib import Path

from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.clientes import _drive_folder_id


class ClientDriveLinkTests(unittest.TestCase):
    def test_accepts_open_link(self):
        self.assertEqual(
            _drive_folder_id(
                "https://drive.google.com/open?id=1br26xTLotswG9BtstGhjUqS25zo0mqK_&usp=drive_fs"
            ),
            "1br26xTLotswG9BtstGhjUqS25zo0mqK_",
        )

    def test_accepts_folder_link(self):
        self.assertEqual(
            _drive_folder_id(
                "https://drive.google.com/drive/folders/1br26xTLotswG9BtstGhjUqS25zo0mqK_"
            ),
            "1br26xTLotswG9BtstGhjUqS25zo0mqK_",
        )

    def test_rejects_non_drive_link(self):
        with self.assertRaises(HTTPException) as context:
            _drive_folder_id("https://example.com/folders/1br26xTLotswG9BtstGhjUqS25zo0mqK_")
        self.assertEqual(context.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
