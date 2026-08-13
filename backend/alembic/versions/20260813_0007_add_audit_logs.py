"""add audit logs

Revision ID: 20260813_0007
Revises: 20260723_0006
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260813_0007"
down_revision: Union[str, None] = "20260723_0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("module", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=True),
        sa.Column("entity_id", sa.String(length=255), nullable=True),
        sa.Column("http_method", sa.String(length=10), nullable=False),
        sa.Column("endpoint", sa.String(length=500), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=100), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("drive_snapshot", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("occurred_at", "username", "module", "action", "entity_id", "outcome"):
        op.create_index(f"ix_audit_logs_{column}", "audit_logs", [column], unique=False)


def downgrade() -> None:
    for column in ("outcome", "entity_id", "action", "module", "username", "occurred_at"):
        op.drop_index(f"ix_audit_logs_{column}", table_name="audit_logs")
    op.drop_table("audit_logs")
