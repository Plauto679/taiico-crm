import datetime
import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base, Client, Insurer, Policy, Product, User
from services.client_merge import merge_duplicate_client


class ClientMergeTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        user = User(id="user", name="User", email="user@example.com", role="admin")
        insurer = Insurer(id="insurer", name="Insurer")
        product = Product(id="product", insurer_id="insurer", name="Product", branch="GMM")
        self.db.add_all([user, insurer, product])
        self.canonical = Client(
            id="canonical",
            full_name="AXEL VALVERDE ANDALON",
            rfc="VAAA9404077RU",
            responsible_user_id="user",
            metadata_json={"source": "canonical"},
        )
        self.duplicate = Client(
            id="duplicate",
            full_name="VALVERDE ANDALON AXEL",
            rfc="VAAA9404077RU",
            email="axel@example.com",
            responsible_user_id="user",
            metadata_json={"prospectador": "ALBERTO"},
        )
        self.db.add_all([self.canonical, self.duplicate])
        policy = Policy(
            id="policy",
            policy_number="P1",
            client_id="duplicate",
            insurer_id="insurer",
            product_id="product",
            effective_start_date=datetime.date(2026, 1, 1),
            effective_end_date=datetime.date(2027, 1, 1),
            premium_amount=100,
            payment_frequency="annual",
            responsible_user_id="user",
        )
        self.db.add(policy)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_merges_fields_and_reassigns_references(self):
        result = merge_duplicate_client(
            self.db,
            canonical_id="canonical",
            duplicate_id="duplicate",
        )
        self.db.commit()

        self.assertEqual(result["reassigned_references"], {"policies": 1})
        self.assertIsNone(self.db.query(Client).filter(Client.id == "duplicate").first())
        canonical = self.db.query(Client).filter(Client.id == "canonical").one()
        self.assertEqual(canonical.email, "axel@example.com")
        self.assertEqual(canonical.metadata_json["prospectador"], "ALBERTO")
        self.assertEqual(
            self.db.query(Policy).filter(Policy.id == "policy").one().client_id,
            "canonical",
        )

    def test_rejects_different_rfcs(self):
        self.duplicate.rfc = "AAMA950203I52"
        self.db.commit()
        with self.assertRaisesRegex(ValueError, "mismo RFC"):
            merge_duplicate_client(
                self.db,
                canonical_id="canonical",
                duplicate_id="duplicate",
            )


if __name__ == "__main__":
    unittest.main()
