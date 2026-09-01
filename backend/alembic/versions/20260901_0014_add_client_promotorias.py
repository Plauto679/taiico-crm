"""Add the client to promotoria relationship.

Revision ID: 20260901_0014
Revises: 20260828_0013
"""

from alembic import op
import sqlalchemy as sa


revision = "20260901_0014"
down_revision = "20260828_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_promotorias",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=36), nullable=False),
        sa.Column("promotoria", sa.String(length=100), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("client_id", "promotoria", name="uq_client_promotoria"),
    )
    op.create_index("ix_client_promotorias_client_id", "client_promotorias", ["client_id"], unique=False)
    op.create_index("ix_client_promotorias_promotoria", "client_promotorias", ["promotoria"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_client_promotorias_promotoria", table_name="client_promotorias")
    op.drop_index("ix_client_promotorias_client_id", table_name="client_promotorias")
    op.drop_table("client_promotorias")
