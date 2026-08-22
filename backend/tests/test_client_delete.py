import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base, Client, Insurer, Policy, Product, User
from services.clientes import DeleteClientRequest, delete_client


class ClientDeleteTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        db = self.Session()
        db.add(User(id="owner", name="Owner", email="owner@example.com", role="broker"))
        db.commit()
        db.close()

    def tearDown(self):
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_deletes_unlinked_prospect(self):
        db = self.Session()
        prospect = Client(full_name="Prospecto libre", responsible_user_id="owner")
        db.add(prospect)
        db.commit()
        prospect_id = prospect.id
        db.close()

        with patch("services.clientes.SessionLocal", self.Session):
            result = delete_client(DeleteClientRequest(client_id=prospect_id))

        self.assertEqual(result["result"], "deleted")
        db = self.Session()
        self.assertIsNone(db.query(Client).filter(Client.id == prospect_id).first())
        db.close()

    def test_archives_prospect_with_policy_history(self):
        db = self.Session()
        insurer = Insurer(id="metlife", name="MetLife")
        product = Product(id="product", insurer_id="metlife", name="GMM", branch="GMM")
        prospect = Client(full_name="Prospecto con historial", responsible_user_id="owner")
        db.add_all([insurer, product, prospect])
        db.flush()
        db.add(
            Policy(
                policy_number="POL-1",
                client_id=prospect.id,
                insurer_id=insurer.id,
                product_id=product.id,
                effective_start_date=date(2026, 1, 1),
                effective_end_date=date(2027, 1, 1),
                premium_amount=100,
                payment_frequency="annual",
                responsible_user_id="owner",
            )
        )
        db.commit()
        prospect_id = prospect.id
        db.close()

        with patch("services.clientes.SessionLocal", self.Session):
            result = delete_client(DeleteClientRequest(client_id=prospect_id))

        self.assertEqual(result["result"], "archived")
        self.assertEqual(result["linked_records"]["pólizas"], 1)
        db = self.Session()
        archived = db.query(Client).filter(Client.id == prospect_id).one()
        self.assertEqual(archived.status, "inactive")
        self.assertEqual(db.query(Policy).filter(Policy.client_id == prospect_id).count(), 1)
        db.close()


if __name__ == "__main__":
    unittest.main()
