"""add renewal paid until

Revision ID: 20260827_0012
Revises: 20260821_0011
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260827_0012"
down_revision: Union[str, None] = "20260821_0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "renewals",
        sa.Column("paid_until", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("renewals", "paid_until")
