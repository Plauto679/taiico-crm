"""Persist each user's selected home module widgets.

Revision ID: 20260914_0017
Revises: 20260911_0016
"""

from alembic import op
import sqlalchemy as sa


revision = "20260914_0017"
down_revision = "20260911_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "home_widget_preferences",
        sa.Column("username", sa.String(length=320), primary_key=True),
        sa.Column("module_keys", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("home_widget_preferences")
