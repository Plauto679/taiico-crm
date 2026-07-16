"""add client RFC

Revision ID: 20260716_0004
Revises: 20260616_0003
Create Date: 2026-07-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260716_0004"
down_revision: Union[str, None] = "20260616_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("clients", sa.Column("rfc", sa.String(length=50), nullable=True))
    op.create_index("ix_clients_rfc", "clients", ["rfc"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_clients_rfc", table_name="clients")
    op.drop_column("clients", "rfc")
