import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.client_folders import (
    FOLDER_MIME_TYPE,
    build_client_folder_plan,
    normalize_client_name,
    normalize_rfc,
    safe_folder_component,
    valid_client_rfc,
)


class ClientFolderTests(unittest.TestCase):
    def test_accepts_person_and_company_rfc_and_rejects_invalid_values(self):
        self.assertTrue(valid_client_rfc("AAMA950203I52"))
        self.assertTrue(valid_client_rfc("ABC9502031A2"))
        self.assertFalse(valid_client_rfc("AAMA951332I52"))
        self.assertFalse(valid_client_rfc("SIN RFC"))

    def test_normalizes_rfc_and_folder_name(self):
        self.assertEqual(normalize_rfc(" aama 950203i52 "), "AAMA950203I52")
        self.assertEqual(normalize_rfc("cim-890330fi8"), "CIM890330FI8")
        self.assertEqual(
            safe_folder_component("  Cliente / Principal  "),
            "Cliente - Principal",
        )
        self.assertEqual(
            normalize_client_name("ALFARO MENDOZA-ALBERTO--", "AAMA950203I52"),
            "Alberto Alfaro Mendoza",
        )
        self.assertEqual(
            normalize_client_name("ALFARO ULLOA-COSME ALBERTO", "AAUC560927JU8"),
            "Cosme Alberto Alfaro Ulloa",
        )
        self.assertEqual(
            normalize_client_name("CATA#O-CLAUDIA", "CAPC6702157D4"),
            "Claudia Cataño",
        )

    def test_plan_deduplicates_by_rfc_and_selects_most_common_name(self):
        records = [
            {"rfc": "AAMA950203I52", "client_name": "Alberto Alfaro", "policy_number": "1", "product_branch": "GMM"},
            {"rfc": "aama950203i52", "client_name": "Alberto Alfaro Mendoza", "policy_number": "2", "product_branch": "VIDA"},
            {"rfc": "AAMA950203I52", "client_name": "Alberto Alfaro Mendoza", "policy_number": "2", "product_branch": "VIDA"},
        ]

        plan = build_client_folder_plan(records, [])

        self.assertEqual(plan["summary"]["valid_clients"], 1)
        self.assertEqual(plan["summary"]["clients_with_name_conflicts"], 1)
        candidate = plan["candidates"][0]
        self.assertEqual(candidate.client_name, "Alberto Alfaro Mendoza")
        self.assertEqual(candidate.folder_name, "AAMA950203I52 - Alberto Alfaro Mendoza")
        self.assertEqual(candidate.policy_count, 2)

    def test_plan_prefers_name_order_matching_person_rfc(self):
        records = [
            {"rfc": "AAAR570524S90", "client_name": "AVALOS AGUILAR ROBERTO"},
            {"rfc": "AAAR570524S90", "client_name": "ROBERTO AVALOS AGUILAR"},
        ]
        plan = build_client_folder_plan(records, [])
        self.assertEqual(plan["candidates"][0].client_name, "Roberto Avalos Aguilar")

    def test_plan_skips_existing_folder_by_rfc_prefix(self):
        records = [
            {"rfc": "AAMA950203I52", "client_name": "Nombre Nuevo", "policy_number": "1"},
        ]
        existing = [
            {
                "id": "folder-1",
                "name": "AAMA950203I52 - Nombre Existente",
                "mimeType": FOLDER_MIME_TYPE,
            },
        ]

        plan = build_client_folder_plan(records, existing)

        self.assertEqual(plan["candidates"], [])
        self.assertEqual(plan["summary"]["folders_already_present"], 1)
        self.assertEqual(plan["summary"]["folder_name_mismatches"], 1)
        self.assertEqual(
            plan["name_mismatches"][0]["expected_name"],
            "AAMA950203I52 - Nombre Nuevo",
        )

    def test_plan_reports_invalid_rfc_without_creating_candidate(self):
        plan = build_client_folder_plan(
            [{"rfc": "RFC INVALIDO", "client_name": "Cliente"}],
            [],
        )
        self.assertEqual(plan["summary"]["folders_to_create"], 0)
        self.assertEqual(plan["summary"]["invalid_rows"], 1)


if __name__ == "__main__":
    unittest.main()
