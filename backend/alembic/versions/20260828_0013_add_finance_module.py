"""add finance module

Revision ID: 20260828_0013
Revises: 20260827_0012
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260828_0013"
down_revision: Union[str, None] = "20260827_0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("finance_source_states",
        sa.Column("key", sa.String(50), primary_key=True), sa.Column("company", sa.String(20), nullable=False),
        sa.Column("bank", sa.String(50), nullable=False), sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=False), sa.Column("content_hash", sa.String(64)),
        sa.Column("row_count", sa.Integer(), nullable=False), sa.Column("last_modified_at", sa.DateTime()),
        sa.Column("last_synced_at", sa.DateTime()), sa.Column("last_error", sa.Text()))
    op.create_index("ix_finance_source_states_company", "finance_source_states", ["company"])
    op.create_table("finance_movements",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("source_key", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False), sa.Column("company", sa.String(20), nullable=False),
        sa.Column("bank", sa.String(50), nullable=False), sa.Column("account_type", sa.String(100)),
        sa.Column("account_nature", sa.String(50)), sa.Column("account", sa.String(100)), sa.Column("clabe", sa.String(40)),
        sa.Column("currency", sa.String(10), nullable=False), sa.Column("operation_date", sa.Date(), nullable=False),
        sa.Column("settlement_date", sa.Date()), sa.Column("original_description", sa.Text(), nullable=False),
        sa.Column("reference", sa.String(500)), sa.Column("counterparty", sa.String(500)),
        sa.Column("debit", sa.Numeric(16, 2), nullable=False), sa.Column("credit", sa.Numeric(16, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(16, 2), nullable=False), sa.Column("balance", sa.Numeric(16, 2)),
        sa.Column("holder", sa.String(500)), sa.Column("source_category", sa.String(255)), sa.Column("source_subcategory", sa.String(255)),
        sa.Column("category_override", sa.String(255)), sa.Column("subcategory_override", sa.String(255)),
        sa.Column("recurring", sa.Boolean(), nullable=False), sa.Column("tax", sa.Boolean(), nullable=False),
        sa.Column("payroll", sa.Boolean(), nullable=False), sa.Column("requires_invoice", sa.Boolean(), nullable=False),
        sa.Column("invoice_uuid", sa.String(64)), sa.Column("invoice_reconciliation_status", sa.String(50)),
        sa.Column("review_status", sa.String(50)), sa.Column("statement_period", sa.String(20)),
        sa.Column("source_filename", sa.String(500)), sa.Column("source_page", sa.Integer()), sa.Column("source_hash", sa.String(64)),
        sa.Column("enrichment_updated_by", sa.String(320)), sa.Column("enrichment_updated_at", sa.DateTime()),
        sa.Column("indexed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_key"], ["finance_source_states.key"], ondelete="CASCADE"),
        sa.UniqueConstraint("source_key", "external_id", name="uq_finance_movement_source_external"))
    for column in ("source_key", "external_id", "company", "bank", "operation_date", "net_amount", "category_override", "invoice_uuid", "invoice_reconciliation_status", "review_status", "statement_period", "source_hash"):
        op.create_index(f"ix_finance_movements_{column}", "finance_movements", [column])
    op.create_table("finance_recurring_decisions",
        sa.Column("fingerprint", sa.String(64), primary_key=True), sa.Column("company", sa.String(20), nullable=False),
        sa.Column("label", sa.String(500), nullable=False), sa.Column("status", sa.String(30), nullable=False),
        sa.Column("note", sa.Text()), sa.Column("decided_by", sa.String(320), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_finance_recurring_decisions_company", "finance_recurring_decisions", ["company"])
    op.create_index("ix_finance_recurring_decisions_status", "finance_recurring_decisions", ["status"])
    op.create_table("finance_invoices",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("file_path", sa.Text(), nullable=False, unique=True),
        sa.Column("file_hash", sa.String(64), nullable=False), sa.Column("file_type", sa.String(10), nullable=False),
        sa.Column("uuid", sa.String(64)), sa.Column("issuer_rfc", sa.String(20)), sa.Column("receiver_rfc", sa.String(20)),
        sa.Column("issued_at", sa.DateTime()), sa.Column("total", sa.Numeric(16, 2)), sa.Column("currency", sa.String(10)),
        sa.Column("payment_method", sa.String(50)), sa.Column("status", sa.String(40), nullable=False),
        sa.Column("parse_error", sa.Text()), sa.Column("indexed_at", sa.DateTime(), nullable=False))
    for column in ("file_hash", "uuid", "issuer_rfc", "receiver_rfc", "issued_at", "status"):
        op.create_index(f"ix_finance_invoices_{column}", "finance_invoices", [column])
    op.create_table("finance_invoice_matches",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("invoice_id", sa.String(36), nullable=False),
        sa.Column("movement_id", sa.String(36), nullable=False), sa.Column("confidence", sa.Numeric(5, 2)),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("rationale", sa.Text()),
        sa.Column("confirmed_by", sa.String(320)), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["finance_invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["movement_id"], ["finance_movements.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("invoice_id", "movement_id", name="uq_finance_invoice_movement"))
    for column in ("invoice_id", "movement_id", "status"): op.create_index(f"ix_finance_invoice_matches_{column}", "finance_invoice_matches", [column])
    op.create_table("finance_projections",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("company", sa.String(20), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False), sa.Column("concept", sa.String(500), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False), sa.Column("scenario", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("source", sa.String(50), nullable=False),
        sa.Column("created_by", sa.String(320), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False))
    for column in ("company", "due_date", "scenario", "status"): op.create_index(f"ix_finance_projections_{column}", "finance_projections", [column])
    op.create_table("finance_classification_rules",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False), sa.Column("field", sa.String(50), nullable=False),
        sa.Column("operator", sa.String(30), nullable=False), sa.Column("value", sa.String(500), nullable=False),
        sa.Column("company", sa.String(20)), sa.Column("category", sa.String(255), nullable=False),
        sa.Column("subcategory", sa.String(255)), sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("exclusion", sa.Boolean(), nullable=False), sa.Column("created_by", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False))
    for column in ("priority", "company", "enabled"): op.create_index(f"ix_finance_classification_rules_{column}", "finance_classification_rules", [column])
    op.create_table("finance_rule_applications",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("rule_id", sa.String(36), nullable=False), sa.Column("movement_id", sa.String(36), nullable=False),
        sa.Column("before_category", sa.String(255)), sa.Column("before_subcategory", sa.String(255)),
        sa.Column("before_review_status", sa.String(50)), sa.Column("applied_by", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("reverted_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["rule_id"], ["finance_classification_rules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["movement_id"], ["finance_movements.id"], ondelete="CASCADE"))
    for column in ("run_id", "rule_id", "movement_id"): op.create_index(f"ix_finance_rule_applications_{column}", "finance_rule_applications", [column])
    op.create_table("finance_budget_items",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("company", sa.String(20), nullable=False),
        sa.Column("month", sa.Date(), nullable=False), sa.Column("category", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False), sa.Column("created_by", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("company", "month", "category", name="uq_finance_budget_company_month_category"))
    for column in ("company", "month", "category"): op.create_index(f"ix_finance_budget_items_{column}", "finance_budget_items", [column])
    op.create_table("finance_ingestions",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("source_key", sa.String(50), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False), sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("new_rows", sa.Integer(), nullable=False), sa.Column("duplicate_rows", sa.Integer(), nullable=False),
        sa.Column("error_detail", sa.Text()), sa.Column("staging_path", sa.Text()), sa.Column("backup_path", sa.Text()),
        sa.Column("created_by", sa.String(320), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime()), sa.Column("reverted_at", sa.DateTime()))
    for column in ("source_key", "file_hash", "status"): op.create_index(f"ix_finance_ingestions_{column}", "finance_ingestions", [column])


def downgrade() -> None:
    for table in ("finance_ingestions", "finance_budget_items", "finance_rule_applications", "finance_classification_rules", "finance_projections", "finance_invoice_matches", "finance_invoices", "finance_recurring_decisions", "finance_movements", "finance_source_states"):
        op.drop_table(table)
