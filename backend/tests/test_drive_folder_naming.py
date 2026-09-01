from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.drive_folder_naming import (
    is_process_folder_for,
    process_folder_descriptor,
    process_folder_name,
)


class DriveFolderNamingTests(unittest.TestCase):
    def test_process_folder_has_date_hour_and_minute(self):
        self.assertEqual(
            process_folder_name(
                "Renovacion póliza 123 2026 - 2027",
                occurred_at=dt.datetime(2026, 8, 29, 7, 5),
            ),
            "2026-08-29 07-05 Renovacion póliza 123 2026 - 2027",
        )

    def test_historical_and_timestamped_names_match_same_process(self):
        descriptor = "Renovacion póliza 123 2026 - 2027"
        self.assertTrue(is_process_folder_for(descriptor, descriptor))
        self.assertTrue(
            is_process_folder_for(
                "2026-08-29 07-05 Renovacion póliza 123 2026 - 2027",
                descriptor,
            )
        )
        self.assertEqual(
            process_folder_descriptor("2026-08-29 Pendiente - Complemento"),
            "Pendiente - Complemento",
        )

    def test_unique_client_folder_is_not_modified(self):
        name = "SABM7809274J4 - Jose Miguel Sanchez Bautista"
        self.assertEqual(process_folder_descriptor(name), name)


if __name__ == "__main__":
    unittest.main()
