import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.client_identity_matching import build_identity_candidates, normalized_name_signature


class ClientIdentityMatchingTests(unittest.TestCase):
    def test_normalizes_legal_suffixes_and_name_order(self):
        self.assertEqual(
            normalized_name_signature("T&M2, Life Advisors Agente de Seguros, S.A. de C.V."),
            normalized_name_signature("T&M2 LIFE ADVISORS AGENTE DE SEGUROS"),
        )

    def test_groups_name_variants_without_merging_them(self):
        groups = build_identity_candidates(
            [
                {"id": "master", "name": "T&M2 LIFE ADVISORS AGENTE DE SEGUROS SA DE CV", "rfc": "TLA180122DQ2", "status": "active"},
                {"id": "prospect", "name": "T&M2, LIFE ADVISORS AGENTE DE SEGUROS", "rfc": None, "status": "active"},
                {"id": "other", "name": "PERSONA DIFERENTE", "rfc": None, "status": "active"},
            ],
            {"pólizas": {"prospect": 3}},
        )

        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["confidence"], "media")
        self.assertEqual(groups[0]["canonical_options"], ["master"])
        prospect = next(member for member in groups[0]["members"] if member["id"] == "prospect")
        self.assertEqual(prospect["relaciones"]["pólizas"], 3)

    def test_excludes_clients_with_different_rfcs_even_when_names_match(self):
        groups = build_identity_candidates(
            [
                {"id": "one", "name": "MISMO NOMBRE", "rfc": "AAMA950203I52", "status": "active"},
                {"id": "two", "name": "NOMBRE MISMO", "rfc": "VAAA9404077RU", "status": "active"},
            ],
            {},
        )

        self.assertEqual(groups, [])

    def test_keeps_clients_with_the_same_rfc_as_candidates(self):
        groups = build_identity_candidates(
            [
                {"id": "one", "name": "MISMO NOMBRE", "rfc": "AAMA950203I52", "status": "active"},
                {"id": "two", "name": "NOMBRE MISMO", "rfc": "AAMA950203I52", "status": "active"},
            ],
            {},
        )

        self.assertEqual(len(groups), 1)
        self.assertFalse(groups[0]["conflicting_rfcs"])
        self.assertEqual(groups[0]["canonical_options"], ["one", "two"])


if __name__ == "__main__":
    unittest.main()
