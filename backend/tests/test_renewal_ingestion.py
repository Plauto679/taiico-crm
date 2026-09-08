import datetime
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base, Client, User
from services import renewal_ingestion


def parsed_row(policy_number, deadline):
    return SimpleNamespace(normalized_payload={
        "policy_number": policy_number,
        "renewal_deadline": deadline,
    })


class CanonicalRenewalIngestionTests(unittest.TestCase):
    def test_summary_separates_matches_unmatched_and_invalid_rows(self):
        rows = [
            parsed_row("MATCHED", datetime.date(2026, 7, 1)),
            parsed_row("MISSING", datetime.date(2026, 8, 1)),
            parsed_row(None, datetime.date(2026, 9, 1)),
        ]

        with patch.object(
            renewal_ingestion,
            "find_policy",
            side_effect=lambda _db, number: object() if number == "MATCHED" else None,
        ):
            summary = renewal_ingestion.summarize_rows(object(), rows)

        self.assertEqual(summary["rows_read"], 3)
        self.assertEqual(summary["unique_renewals"], 2)
        self.assertEqual(summary["matched_policy_rows"], 1)
        self.assertEqual(summary["unmatched_policy_rows"], 1)
        self.assertEqual(summary["invalid_rows"], 1)

    def test_only_sources_with_validated_parsers_are_supported(self):
        self.assertIn("renovaciones.metlife_gmm", renewal_ingestion.SUPPORTED_SOURCES)
        self.assertIn("renovaciones.metlife_vida", renewal_ingestion.SUPPORTED_SOURCES)
        self.assertNotIn("renovaciones.sura", renewal_ingestion.SUPPORTED_SOURCES)


class RenewalClientIdentityTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.db.add(User(id="usr_pamela", name="Pamela", email="pamela@example.com", role="admin"))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    @patch.object(renewal_ingestion, "lookup_client_email", return_value=None)
    def test_finds_existing_client_by_rfc_before_name(self, _lookup):
        existing = Client(
            id="existing",
            full_name="CHECK POINT SOFTWARE TECHNOLOGIES MEXICO, S.A. DE C.V",
            rfc="CPS000928FC9",
            responsible_user_id="usr_pamela",
            status="active",
        )
        self.db.add(existing)
        self.db.commit()

        found = renewal_ingestion.find_or_create_client(
            self.db,
            {
                "client_name": "CHECK POINT SOFTWARE TECHNOLOGIES MEXICO SA DE CV",
                "rfc": "CPS000928FC9",
            },
        )

        self.assertEqual(found.id, "existing")
        self.assertEqual(self.db.query(Client).count(), 1)

    @patch.object(renewal_ingestion, "lookup_client_email", return_value=None)
    def test_same_name_with_different_rfc_creates_distinct_client(self, _lookup):
        self.db.add(Client(
            id="first",
            full_name="CLIENTE CON DOS REGISTROS",
            rfc="AAAA800101AA1",
            responsible_user_id="usr_pamela",
            status="active",
        ))
        self.db.commit()

        second = renewal_ingestion.find_or_create_client(
            self.db,
            {
                "client_name": "CLIENTE CON DOS REGISTROS",
                "rfc": "BBBB800101BB2",
            },
        )

        self.assertNotEqual(second.id, "first")
        self.assertEqual(second.rfc, "BBBB800101BB2")
        self.assertEqual(self.db.query(Client).count(), 2)


if __name__ == "__main__":
    unittest.main()
