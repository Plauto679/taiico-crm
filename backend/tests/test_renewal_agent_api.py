import os
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main
from database import AgentAction, Base, PolicyDocumentRetrievalTask
from services import renewal_agent_api


class RenewalAgentApiTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        self.session_patch = patch.object(
            renewal_agent_api, "SessionLocal", self.Session
        )
        self.session_patch.start()
        self.env_patch = patch.dict(
            os.environ, {"RENEWAL_AGENT_API_TOKEN": "test-service-token"}
        )
        self.env_patch.start()
        self.date_patch = patch.object(
            renewal_agent_api,
            "_process_date",
            return_value=date(2026, 8, 6),
        )
        self.date_patch.start()
        self.client = TestClient(main.app)
        self.headers = {"Authorization": "Bearer test-service-token"}

    def tearDown(self):
        self.date_patch.stop()
        self.env_patch.stop()
        self.session_patch.stop()

    def add_task(
        self,
        *,
        agent_code: str,
        policy_number: str,
        deadline: date = date(2026, 8, 20),
    ) -> str:
        db = self.Session()
        task = PolicyDocumentRetrievalTask(
            insurer_id="metlife",
            product_branch="GMM",
            policy_number=policy_number,
            client_name="Cliente Prueba",
            renewal_deadline=deadline,
            status="queued",
            document_status="missing",
            source_name="test.xlsx",
            source_row_hash=f"hash-{policy_number}",
            source_payload={"AGENTE": agent_code},
            normalized_payload={
                "agent_code": agent_code,
                "agent_name": "Agente Prueba",
                "promotoria": "TAIICO" if agent_code == "16200" else "OTRA",
                "effective_start_date": "2025-08-20",
            },
        )
        db.add(task)
        db.commit()
        task_id = task.id
        db.close()
        return task_id

    def test_service_token_is_required(self):
        response = self.client.get("/renewal-agent/candidates")
        self.assertEqual(response.status_code, 401)

    def test_candidates_are_limited_to_taiico_agents_and_thirty_days(self):
        self.add_task(agent_code="16200", policy_number="TAIICO-1")
        self.add_task(agent_code="99999", policy_number="OTHER-1")
        self.add_task(
            agent_code="18412",
            policy_number="FUTURE-1",
            deadline=date(2026, 9, 20),
        )

        response = self.client.get(
            "/renewal-agent/candidates", headers=self.headers
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["tasks"][0]["policy_number"], "TAIICO-1")

    def test_non_taiico_task_cannot_be_claimed_by_id(self):
        task_id = self.add_task(agent_code="99999", policy_number="OTHER-1")
        response = self.client.post(
            f"/renewal-agent/tasks/{task_id}/claim",
            headers=self.headers,
            json={"worker_id": "codex-mac"},
        )
        self.assertEqual(response.status_code, 403)

    def test_claim_collection_and_approval_are_separate_transitions(self):
        task_id = self.add_task(agent_code="73640", policy_number="TAIICO-2")

        claimed = self.client.post(
            f"/renewal-agent/tasks/{task_id}/claim",
            headers=self.headers,
            json={"worker_id": "codex-mac"},
        )
        self.assertEqual(claimed.status_code, 200)
        self.assertEqual(claimed.json()["task"]["status"], "claimed")

        checked = self.client.post(
            f"/renewal-agent/tasks/{task_id}/collection-check",
            headers=self.headers,
            json={
                "paid_until": "2026-08-20",
                "payment_status": "Pagado",
                "evidence": "MetLife Clientes > Cobranza",
            },
        )
        self.assertEqual(checked.status_code, 200)
        self.assertTrue(checked.json()["collection"]["eligible"])
        self.assertEqual(checked.json()["task"]["status"], "collection_approved")

        approved = self.client.post(
            f"/renewal-agent/tasks/{task_id}/approve",
            headers=self.headers,
            json={"reviewed_by": "alberto.alfaro@taiico.com"},
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["task"]["status"], "approved")

        db = self.Session()
        actions = db.query(AgentAction).order_by(AgentAction.created_at).all()
        self.assertEqual(
            [action.action_type for action in actions],
            [
                "renewal_claim",
                "renewal_collection_check",
                "renewal_human_approval",
            ],
        )
        db.close()

    def test_collection_before_ffinvig_blocks_approval(self):
        task_id = self.add_task(agent_code="18412", policy_number="TAIICO-3")
        self.client.post(
            f"/renewal-agent/tasks/{task_id}/claim",
            headers=self.headers,
            json={"worker_id": "codex-mac"},
        )
        checked = self.client.post(
            f"/renewal-agent/tasks/{task_id}/collection-check",
            headers=self.headers,
            json={"paid_until": "2026-08-19", "payment_status": "Pagado"},
        )
        self.assertFalse(checked.json()["collection"]["eligible"])
        self.assertEqual(checked.json()["task"]["status"], "collection_blocked")

        approved = self.client.post(
            f"/renewal-agent/tasks/{task_id}/approve",
            headers=self.headers,
            json={"reviewed_by": "alberto.alfaro@taiico.com"},
        )
        self.assertEqual(approved.status_code, 409)


if __name__ == "__main__":
    unittest.main()
