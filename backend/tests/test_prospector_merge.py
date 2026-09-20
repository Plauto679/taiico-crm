import datetime
import sys
import unittest
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import (
    Base,
    Client,
    Insurer,
    Policy,
    PolicyProspectorAssignment,
    Product,
    Prospector,
    ProspectorCommissionPeriod,
    ProspectorOpeningBalance,
    User,
)
from services.prospector_merge import merge_prospectors, reassign_policy_to_named_prospector


class ProspectorMergeTests(unittest.TestCase):
    def test_blank_cartera_start_is_retroactive_and_has_no_expiration(self):
        from services.cobranza_prospectadores import _matching_assignments
        self.assignment.effective_from = datetime.date(2026, 9, 15)
        self.assignment.effective_to = datetime.date(2027, 9, 15)
        self.db.flush()
        for movement in (datetime.date(2020, 1, 1), datetime.date(2040, 1, 1)):
            rows, expired = _matching_assignments(self.db, self.policy.id, movement)
            self.assertEqual([row.id for row in rows], [self.assignment.id])
            self.assertFalse(expired)

    def test_explicit_cartera_start_and_expiration_are_respected(self):
        from services.cobranza_prospectadores import _matching_assignments
        self.policy.metadata_json = {"payment_start_date": "2026-08-01"}
        self.db.flush()
        self.assertEqual(_matching_assignments(self.db, self.policy.id, datetime.date(2026, 7, 31)), ([], False))
        self.assertFalse(_matching_assignments(self.db, self.policy.id, datetime.date(2026, 8, 3))[1])
        self.assertTrue(_matching_assignments(self.db, self.policy.id, datetime.date(2027, 8, 1))[1])

    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.db.add_all([
            User(id="user", name="User", email="user@example.com", role="admin"),
            Insurer(id="sura", name="SURA"),
            Product(id="product", insurer_id="sura", name="SURA Daños", branch="DANOS"),
        ])
        self.client = Client(id="client", full_name="Cliente", responsible_user_id="user")
        self.source = Prospector(
            id="source", name="Alberto Alfaro", normalized_name="ALBERTO ALFARO",
            payment_scheme="factura", invoice_required=True, is_active=True, created_by="user",
        )
        self.target = Prospector(
            id="target", name="ALBERTO ALFARO MENDOZA", normalized_name="ALBERTO ALFARO MENDOZA",
            payment_scheme="factura", invoice_required=True, is_active=True, created_by="user",
        )
        self.policy = Policy(
            id="policy", policy_number="19696", client_id="client", insurer_id="sura",
            product_id="product", effective_start_date=datetime.date(2026, 1, 1),
            effective_end_date=datetime.date(2027, 1, 1), premium_amount=100,
            payment_frequency="annual", responsible_user_id="user",
            metadata_json={"prospector": "Alberto Alfaro"},
        )
        self.db.add_all([self.client, self.source, self.target, self.policy])
        self.assignment = PolicyProspectorAssignment(
            id="assignment", policy_id="policy", prospector_id="source", commission_rate=Decimal("0.8"),
            effective_from=datetime.date(2026, 1, 1), source="cartera_migration", created_by="user",
        )
        self.period = ProspectorCommissionPeriod(
            id="period", month=datetime.date(2026, 8, 1), currency="MXN",
            utility_coefficient=Decimal("0.91"), vat_rate=Decimal("0.16"), created_by="user",
        )
        self.balance = ProspectorOpeningBalance(
            period_id="period", prospector_id="source", amount=Decimal("250.00"), created_by="user",
        )
        self.db.add_all([self.assignment, self.period, self.balance])
        self.db.commit()

    def test_migration_count_recognizes_all_active_assignment_sources(self):
        from services.prospectadores import migration_preview
        for source in ('cartera_edit', 'manual', 'cartera_migration'):
            self.assignment.source = source
            self.db.flush()
            self.assertEqual(migration_preview(self.db)['policies_pending'], 0)
        self.assignment.is_active = False
        self.db.flush()
        self.assertEqual(migration_preview(self.db)['policies_pending'], 1)

    def test_migration_count_detects_missing_member_of_split(self):
        from services.prospectadores import migration_preview
        self.policy.metadata_json = {'prospector': '50% Alberto Alfaro, 50% Alberto Alfaro Mendoza'}
        self.db.flush()
        self.assertEqual(migration_preview(self.db)['policies_pending'], 1)
        self.db.add(PolicyProspectorAssignment(
            policy_id=self.policy.id, prospector_id=self.target.id,
            commission_rate=Decimal('0.5'), effective_from=datetime.date(2026, 1, 1),
            source='cartera_edit', created_by='user',
        ))
        self.db.flush()
        self.assertEqual(migration_preview(self.db)['policies_pending'], 0)

    def test_zero_cartera_rate_overrides_old_migration_rate(self):
        from services.cobranza_prospectadores import analyze_import_lines
        self.policy.commission_percentage = Decimal('0')
        self.db.flush()
        item=analyze_import_lines(self.db,[{'policy_number':'19696','movement_date':'2026-08-07',
            'source_commission':'1315.16','currency':'MXN','branch':'GMM'}],self.period)[0]
        self.assertEqual(Decimal(item['allocations'][0]['commission_rate']),Decimal('0'))
        self.assertEqual(Decimal(item['allocations'][0]['calculation']['total_amount']),Decimal('0'))
        reassign_policy_to_named_prospector(self.db,self.policy,self.source.name)
        self.assertEqual(self.assignment.commission_rate,Decimal('0'))

    def tearDown(self):
        self.db.close()

    def test_merge_moves_assignments_balance_and_policy_label(self):
        result = merge_prospectors(
            self.db, source_id="source", target_id="target", actor="admin@example.com"
        )
        self.db.commit()

        self.assertEqual(result["moved_assignments"], 1)
        self.assertIsNone(self.db.get(Prospector, "source"))
        self.assertEqual(self.db.get(PolicyProspectorAssignment, "assignment").prospector_id, "target")
        self.assertEqual(self.db.query(ProspectorOpeningBalance).one().prospector_id, "target")
        self.assertEqual(self.db.get(Policy, "policy").metadata_json["prospector"], "ALBERTO ALFARO MENDOZA")
        self.assertIn("Alberto Alfaro", self.db.get(Prospector, "target").metadata_json["name_aliases"])

    def test_cartera_name_change_reassigns_single_policy_to_existing_master(self):
        changed = reassign_policy_to_named_prospector(
            self.db, self.policy, "ALBERTO ALFARO MENDOZA"
        )
        self.db.commit()

        self.assertTrue(changed)
        self.assertEqual(self.db.get(PolicyProspectorAssignment, "assignment").prospector_id, "target")


if __name__ == "__main__":
    unittest.main()
