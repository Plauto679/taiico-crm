"""Add an internal explanatory description to finance movements.

Revision ID: 20260914_0018
Revises: 20260914_0017
"""

from alembic import op
import sqlalchemy as sa


revision = "20260914_0018"
down_revision = "20260914_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("finance_movements", sa.Column("description_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("finance_movements", "description_note")
