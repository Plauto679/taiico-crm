"""add campaign deliveries

Revision ID: 20260821_0011
Revises: 20260821_0010
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260821_0011"
down_revision: Union[str, None] = "20260821_0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaign_deliveries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("recipient_key", sa.String(length=500), nullable=False),
        sa.Column("policy_number", sa.String(length=100), nullable=True),
        sa.Column("rfc", sa.String(length=20), nullable=True),
        sa.Column("client_name", sa.String(length=500), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("rendered_subject", sa.String(length=500), nullable=True),
        sa.Column("rendered_body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "recipient_key", name="uq_campaign_delivery_recipient"),
    )
    for column in ("campaign_id", "policy_number", "rfc", "email", "status"):
        op.create_index(f"ix_campaign_deliveries_{column}", "campaign_deliveries", [column], unique=False)


def downgrade() -> None:
    for column in ("status", "email", "rfc", "policy_number", "campaign_id"):
        op.drop_index(f"ix_campaign_deliveries_{column}", table_name="campaign_deliveries")
    op.drop_table("campaign_deliveries")
