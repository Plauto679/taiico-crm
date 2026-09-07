import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import (
    Base,
    Client,
    CommercialOpportunity,
    CommercialOpportunityQuote,
    CommercialOpportunityTask,
    Insurer,
    Product,
    Task,
    User,
)
from services.auth import AccessProfile, PROMOTORIAS
from services import gestion_comercial


class CommercialManagementTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)
        self.session_patch = patch.object(gestion_comercial, "SessionLocal", self.Session)
        self.session_patch.start()
        db = self.Session()
        db.add_all([
            User(id="usr_admin", name="Admin", email="admin@taiico.com", role="management"),
            Insurer(id="metlife", name="MetLife"),
            Product(id="prod_met_gmm", insurer_id="metlife", name="Medicalife Familiar", branch="GMM"),
        ])
        client = Client(
            id="client-1", full_name="Cliente Uno", rfc="RFC010101AA1",
            responsible_user_id="usr_admin", status="active",
        )
        db.add(client)
        db.commit()
        db.close()
        self.profile = AccessProfile(
            username="admin@taiico.com", role="admin", promotorias=PROMOTORIAS,
            rfc="", aseguradoras=("METLIFE",),
            module_permissions={"gestion_comercial": "operacion", "pendientes": "operacion"},
        )

    def tearDown(self):
        self.session_patch.stop()

    def payload(self, stage_code="prospecting"):
        return gestion_comercial.OpportunityCreate(
            client_id="client-1", product_id="prod_met_gmm", product_name="Medicalife Familiar",
            business_line="GMM", owner_agent_rfc="AGENT010101AA1",
            owner_agent_name="Agente Uno", owner_promotoria="TAIICO",
            potential_premium=Decimal("100000"), currency="MXN",
            stage_code=stage_code, priority="high", source="Referido",
            estimated_close_date=date(2026, 10, 1),
        )

    def test_stage_task_blocks_progress_until_completed(self):
        db = self.Session()
        opportunity = gestion_comercial.create_opportunity_record(db, self.payload("solution_design"), self.profile.username)
        db.commit()
        links = db.query(CommercialOpportunityTask).filter_by(opportunity_id=opportunity.id).all()
        self.assertEqual(len(links), 1)
        task = db.query(Task).filter_by(id=links[0].task_id).one()
        self.assertTrue(task.metadata_json["blocks_stage_change"])
        target = next(stage for stage in db.query(gestion_comercial.CommercialStage).all() if stage.code == "presentation")
        with self.assertRaisesRegex(ValueError, "pendientes obligatorios"):
            gestion_comercial.move_opportunity_stage(db, opportunity, target, actor=self.profile.username)
        task.status = "completed"
        gestion_comercial.move_opportunity_stage(db, opportunity, target, actor=self.profile.username)
        db.commit()
        self.assertEqual(opportunity.stage.code, "presentation")
        self.assertEqual(db.query(CommercialOpportunityTask).filter_by(opportunity_id=opportunity.id).count(), 2)
        db.close()

    def test_quote_link_is_idempotent(self):
        quote = {
            "id": "COT-20260905-ABC123", "cliente": "Cliente Uno", "rfc": "RFC010101AA1",
            "producto": "Medicalife Familiar", "ramo": "GMM", "agente": "Agente Uno",
            "promotoria": "TAIICO", "clave_agente": "12345",
        }
        first = gestion_comercial.ensure_opportunity_for_quote(
            quote, actor=self.profile.username, agent_rfc="AGENT010101AA1", client_id="client-1",
        )
        second = gestion_comercial.ensure_opportunity_for_quote(
            quote, actor=self.profile.username, agent_rfc="AGENT010101AA1", client_id="client-1",
        )
        db = self.Session()
        self.assertEqual(first, second)
        self.assertEqual(db.query(CommercialOpportunity).count(), 1)
        self.assertEqual(db.query(CommercialOpportunityQuote).count(), 1)
        db.close()

    def test_quote_email_event_completes_prior_blocker_and_advances(self):
        quote = {
            "id": "COT-20260905-XYZ789", "cliente": "Cliente Uno", "rfc": "RFC010101AA1",
            "producto": "Medicalife Familiar", "ramo": "GMM", "agente": "Agente Uno",
            "promotoria": "TAIICO", "clave_agente": "12345",
        }
        opportunity_id = gestion_comercial.ensure_opportunity_for_quote(
            quote, actor=self.profile.username, agent_rfc="AGENT010101AA1", client_id="client-1",
        )
        gestion_comercial.advance_opportunity_for_quote(
            quote["id"], "presentation", actor=self.profile.username,
        )
        db = self.Session()
        opportunity = db.query(CommercialOpportunity).filter_by(id=opportunity_id).one()
        tasks = [task for task, _link in gestion_comercial._opportunity_tasks(db, opportunity_id)]
        self.assertEqual(opportunity.stage.code, "presentation")
        self.assertEqual(len(tasks), 2)
        self.assertEqual(sum(task.status == "completed" for task in tasks), 1)
        self.assertEqual(sum(task.status == "pending" for task in tasks), 1)
        db.close()

    def test_commercial_pending_is_visible_in_existing_pending_module(self):
        db = self.Session()
        gestion_comercial.create_opportunity_record(db, self.payload("solution_design"), self.profile.username)
        db.commit()
        db.close()
        response = gestion_comercial.list_commercial_pending(self.profile)
        self.assertEqual(len(response["rows"]), 1)
        self.assertEqual(response["rows"][0]["client_name"], "Cliente Uno")
        self.assertTrue(response["rows"][0]["blocks_stage_change"])


if __name__ == "__main__":
    unittest.main()
