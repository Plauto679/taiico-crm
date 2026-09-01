import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import Base, Client, ClientPromotoria, User
from services.auth import AccessProfile
from services.client_promotorias import (
    assign_profile_promotorias,
    scope_client_query,
    sync_client_promotorias,
)


def profile(*promotorias: str) -> AccessProfile:
    return AccessProfile(
        username="scoped@example.com",
        role="admin",
        promotorias=promotorias,
        rfc="",
        aseguradoras=(),
        module_permissions={"clientes": "operacion"},
    )


class ClientPromotoriaTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add(User(id="owner", name="Owner", email="owner@example.com", role="admin"))
        self.db.add_all([
            Client(
                id="abbondanza",
                full_name="Cliente Abbondanza",
                rfc="AAA010101AAA",
                responsible_user_id="owner",
                metadata_json={"prospectador": "AGENTE UNO"},
            ),
            Client(
                id="taiico",
                full_name="Cliente Taiico",
                rfc="BBB010101BBB",
                responsible_user_id="owner",
                metadata_json={},
            ),
        ])
        self.db.flush()
        self.db.add(ClientPromotoria(client_id="taiico", promotoria="TAIICO", sources_json=[]))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_scoped_query_only_returns_allowed_promotoria(self):
        self.db.add(ClientPromotoria(client_id="abbondanza", promotoria="ABBONDANZA", sources_json=[]))
        self.db.commit()

        visible = scope_client_query(self.db.query(Client), profile("ABBONDANZA")).all()

        self.assertEqual([client.id for client in visible], ["abbondanza"])

    def test_sync_uses_unique_agent_name_as_high_confidence_evidence(self):
        agents = [{
            "nombre": "Agente Uno",
            "promotoria": "ABBONDANZA",
            "clave_arranque": "123",
            "clave_definitiva": "456",
        }]
        with patch(
            "services.client_promotorias.METLIFE_PATHS",
            {"RENOVACIONES_GMM": "/missing/gmm.xlsx", "RENOVACIONES_VIDA": "/missing/vida.xlsx"},
        ):
            result = sync_client_promotorias(self.db, agents=agents)
        self.db.commit()

        row = self.db.query(ClientPromotoria).filter_by(
            client_id="abbondanza", promotoria="ABBONDANZA"
        ).one()
        self.assertEqual(result["created"], 1)
        self.assertEqual(row.sources_json[0]["source"], "client_metadata.prospectador")

    def test_new_client_inherits_non_central_user_scope(self):
        client = Client(full_name="Nuevo", responsible_user_id="owner")
        assign_profile_promotorias(client, profile("ABBONDANZA"))

        self.assertEqual([row.promotoria for row in client.promotorias], ["ABBONDANZA"])


if __name__ == "__main__":
    unittest.main()
