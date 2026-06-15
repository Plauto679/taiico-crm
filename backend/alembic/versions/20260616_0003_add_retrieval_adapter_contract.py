"""add retrieval adapter contract tables

Revision ID: 20260616_0003
Revises: 20260613_0002
Create Date: 2026-06-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260616_0003"
down_revision: Union[str, None] = "20260613_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "policy_document_retrieval_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("adapter_name", sa.String(length=100), nullable=False),
        sa.Column("insurer_id", sa.String(length=50), nullable=True),
        sa.Column("product_branch", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("queued_at_start", sa.Integer(), nullable=False),
        sa.Column("selected_count", sa.Integer(), nullable=False),
        sa.Column("processed_count", sa.Integer(), nullable=False),
        sa.Column("succeeded_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("escalated_count", sa.Integer(), nullable=False),
        sa.Column("summary_email_to", sa.String(length=255), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "idx_policy_document_retrieval_runs_status",
        "policy_document_retrieval_runs",
        ["status", "started_at"],
    )

    op.create_table(
        "policy_document_retrieval_steps",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("step_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["policy_document_retrieval_runs.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["policy_document_retrieval_tasks.id"]),
    )
    op.create_index(
        "idx_policy_document_retrieval_steps_run_task",
        "policy_document_retrieval_steps",
        ["run_id", "task_id", "step_name"],
    )


def downgrade() -> None:
    op.drop_index("idx_policy_document_retrieval_steps_run_task", table_name="policy_document_retrieval_steps")
    op.drop_table("policy_document_retrieval_steps")
    op.drop_index("idx_policy_document_retrieval_runs_status", table_name="policy_document_retrieval_runs")
    op.drop_table("policy_document_retrieval_runs")
