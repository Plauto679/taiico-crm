import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.client_folders import FOLDER_MIME_TYPE
from services.client_registry import build_client_registry_audit


def folder(folder_id: str, name: str) -> dict:
    return {
        "id": folder_id,
        "name": name,
        "mimeType": FOLDER_MIME_TYPE,
        "webViewLink": f"https://drive.test/{folder_id}",
    }


class ClientRegistryAuditTests(unittest.TestCase):
    def test_reports_prospects_duplicates_and_safe_links(self):
        audit = build_client_registry_audit(
            [
                {"id": "1", "nombre": "Prospecto", "rfc": ""},
                {"id": "2", "nombre": "Alberto Alfaro Mendoza", "rfc": "AAMA950203I52"},
                {"id": "3", "nombre": "Axel Uno", "rfc": "VAAA9404077RU"},
                {"id": "4", "nombre": "Axel Dos", "rfc": "VAAA9404077RU"},
            ],
            [
                folder("folder-a", "AAMA950203I52 - Alberto Alfaro Mendoza"),
                folder("folder-v", "VAAA9404077RU - Axel Valverde"),
            ],
        )

        self.assertEqual(audit["summary"]["prospects_without_rfc"], 1)
        self.assertEqual(audit["summary"]["duplicate_client_rfcs"], 1)
        self.assertEqual(audit["summary"]["safe_links_available"], 1)
        self.assertEqual(audit["safe_link_updates"][0]["client"]["id"], "2")

    def test_never_links_when_drive_has_duplicate_rfc(self):
        audit = build_client_registry_audit(
            [{"id": "1", "nombre": "Cliente", "rfc": "AAMA950203I52"}],
            [
                folder("one", "AAMA950203I52 - Cliente"),
                folder("two", "AAMA950203I52 - Cliente (1)"),
            ],
        )

        self.assertEqual(audit["summary"]["duplicate_drive_rfcs"], 1)
        self.assertEqual(audit["summary"]["safe_links_available"], 0)
        self.assertEqual(audit["safe_link_updates"], [])

    def test_recognizes_existing_link(self):
        audit = build_client_registry_audit(
            [{
                "id": "1",
                "nombre": "Alberto Alfaro Mendoza",
                "rfc": "AAMA950203I52",
                "expediente_id": "folder-a",
            }],
            [folder("folder-a", "AAMA950203I52 - Alberto Alfaro Mendoza")],
        )

        self.assertEqual(audit["summary"]["linked_clients"], 1)
        self.assertEqual(audit["summary"]["safe_links_available"], 0)


if __name__ == "__main__":
    unittest.main()
