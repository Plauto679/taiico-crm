"""Add prospectors and prospectator commission foundation.

Revision ID: 20260911_0016
Revises: 20260905_0015
"""

from alembic import op
import sqlalchemy as sa


revision = "20260911_0016"
down_revision = "20260905_0015"
branch_labels = None
depends_on = None


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        "prospectors",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("rfc", sa.String(20), unique=True),
        sa.Column("email", sa.String(320)),
        sa.Column("additional_emails", sa.JSON(), nullable=False),
        sa.Column("payment_scheme", sa.String(30), nullable=False),
        sa.Column("invoice_required", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("linked_username", sa.String(320)),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(320), nullable=False),
        *_timestamps(),
    )
    for column in ("name", "normalized_name", "rfc", "email", "payment_scheme", "is_active", "linked_username"):
        op.create_index(f"ix_prospectors_{column}", "prospectors", [column])

    op.create_table(
        "policy_prospector_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("policy_id", sa.String(36), nullable=False),
        sa.Column("prospector_id", sa.String(36), nullable=False),
        sa.Column("commission_rate", sa.Numeric(9, 6), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(320), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prospector_id"], ["prospectors.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("policy_id", "prospector_id", "effective_from", "source", name="uq_policy_prospector_assignment_source"),
    )
    for column in ("policy_id", "prospector_id", "effective_from", "effective_to", "source", "is_active"):
        op.create_index(f"ix_policy_prospector_assignments_{column}", "policy_prospector_assignments", [column])

    op.create_table(
        "prospector_commission_periods",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("month", sa.Date(), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("utility_coefficient", sa.Numeric(9, 6), nullable=False),
        sa.Column("vat_rate", sa.Numeric(9, 6), nullable=False),
        sa.Column("created_by", sa.String(320), nullable=False),
        sa.Column("closed_by", sa.String(320)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_prospector_commission_periods_month", "prospector_commission_periods", ["month"])
    op.create_index("ix_prospector_commission_periods_status", "prospector_commission_periods", ["status"])

    op.create_table(
        "prospector_opening_balances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("period_id", sa.String(36), nullable=False),
        sa.Column("prospector_id", sa.String(36), nullable=False),
        sa.Column("amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_by", sa.String(320), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["period_id"], ["prospector_commission_periods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prospector_id"], ["prospectors.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("period_id", "prospector_id", name="uq_prospector_opening_balance"),
    )
    op.create_index("ix_prospector_opening_balances_period_id", "prospector_opening_balances", ["period_id"])
    op.create_index("ix_prospector_opening_balances_prospector_id", "prospector_opening_balances", ["prospector_id"])

    op.create_table(
        "prospector_commission_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("period_id", sa.String(36), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("raw_row_count", sa.Integer(), nullable=False),
        sa.Column("consolidated_row_count", sa.Integer(), nullable=False),
        sa.Column("exception_count", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["period_id"], ["prospector_commission_periods.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("period_id", "source", "file_hash", name="uq_prospector_commission_batch_file"),
    )
    for column in ("period_id", "source", "file_hash", "status"):
        op.create_index(f"ix_prospector_commission_batches_{column}", "prospector_commission_batches", [column])

    op.create_table(
        "prospector_commission_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("source_key", sa.String(255), nullable=False),
        sa.Column("policy_id", sa.String(36)),
        sa.Column("policy_number", sa.String(100), nullable=False),
        sa.Column("receipt_number", sa.String(100)),
        sa.Column("insurer_id", sa.String(50), nullable=False),
        sa.Column("branch", sa.String(50)),
        sa.Column("movement_date", sa.Date()),
        sa.Column("source_commission", sa.Numeric(16, 4), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("exception_reason", sa.Text()),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["prospector_commission_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"]),
        sa.UniqueConstraint("batch_id", "source_key", name="uq_prospector_commission_line_source"),
    )
    for column in ("batch_id", "policy_id", "policy_number", "receipt_number", "insurer_id", "branch", "movement_date", "status"):
        op.create_index(f"ix_prospector_commission_lines_{column}", "prospector_commission_lines", [column])

    op.create_table(
        "prospector_commission_allocations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("line_id", sa.String(36), nullable=False),
        sa.Column("prospector_id", sa.String(36), nullable=False),
        sa.Column("assignment_id", sa.String(36)),
        sa.Column("commission_rate", sa.Numeric(9, 6), nullable=False),
        sa.Column("utility_coefficient", sa.Numeric(9, 6), nullable=False),
        sa.Column("vat_rate", sa.Numeric(9, 6), nullable=False),
        sa.Column("life_divisor", sa.Numeric(9, 6), nullable=False),
        sa.Column("commission_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("vat_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(16, 2), nullable=False),
        sa.Column("calculation", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["line_id"], ["prospector_commission_lines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prospector_id"], ["prospectors.id"]),
        sa.ForeignKeyConstraint(["assignment_id"], ["policy_prospector_assignments.id"]),
        sa.UniqueConstraint("line_id", "prospector_id", name="uq_prospector_commission_allocation"),
    )
    for column in ("line_id", "prospector_id", "assignment_id"):
        op.create_index(f"ix_prospector_commission_allocations_{column}", "prospector_commission_allocations", [column])


def downgrade() -> None:
    op.drop_table("prospector_commission_allocations")
    op.drop_table("prospector_commission_lines")
    op.drop_table("prospector_commission_batches")
    op.drop_table("prospector_opening_balances")
    op.drop_table("prospector_commission_periods")
    op.drop_table("policy_prospector_assignments")
    op.drop_table("prospectors")
