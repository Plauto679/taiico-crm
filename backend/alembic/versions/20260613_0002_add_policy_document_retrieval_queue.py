"""add policy document retrieval queue

Revision ID: 20260613_0002
Revises: 20260527_0001
Create Date: 2026-06-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260613_0002"
down_revision: Union[str, None] = "20260527_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "policy_document_retrieval_tasks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("insurer_id", sa.String(length=50), nullable=False),
        sa.Column("product_branch", sa.String(length=50), nullable=False),
        sa.Column("policy_number", sa.String(length=100), nullable=False),
        sa.Column("original_policy_number", sa.String(length=100), nullable=True),
        sa.Column("client_name", sa.String(length=255), nullable=True),
        sa.Column("rfc", sa.String(length=50), nullable=True),
        sa.Column("renewal_deadline", sa.Date(), nullable=False),
        sa.Column("days_until_renewal", sa.Integer(), nullable=True),
        sa.Column("risk_level", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("document_status", sa.String(length=50), nullable=False),
        sa.Column("expediente_link", sa.String(length=1000), nullable=True),
        sa.Column("target_drive_folder_id", sa.String(length=255), nullable=True),
        sa.Column("target_drive_folder_path", sa.String(length=1000), nullable=True),
        sa.Column("source_name", sa.String(length=100), nullable=False),
        sa.Column("source_path", sa.String(length=1000), nullable=True),
        sa.Column("source_sheet_name", sa.String(length=100), nullable=True),
        sa.Column("source_row_number", sa.Integer(), nullable=True),
        sa.Column("source_row_hash", sa.String(length=64), nullable=False),
        sa.Column("source_payload", sa.JSON(), nullable=False),
        sa.Column("normalized_payload", sa.JSON(), nullable=True),
        sa.Column("retrieval_adapter", sa.String(length=100), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("queued_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "insurer_id",
            "product_branch",
            "policy_number",
            "renewal_deadline",
            name="uq_policy_document_retrieval_identity",
        ),
    )
    op.create_index(
        "idx_policy_document_retrieval_status_priority",
        "policy_document_retrieval_tasks",
        ["status", "priority", "renewal_deadline"],
    )
    op.create_index(
        "idx_policy_document_retrieval_source_row",
        "policy_document_retrieval_tasks",
        ["source_name", "source_sheet_name", "source_row_number"],
    )


def downgrade() -> None:
    op.drop_index("idx_policy_document_retrieval_source_row", table_name="policy_document_retrieval_tasks")
    op.drop_index("idx_policy_document_retrieval_status_priority", table_name="policy_document_retrieval_tasks")
    op.drop_table("policy_document_retrieval_tasks")
