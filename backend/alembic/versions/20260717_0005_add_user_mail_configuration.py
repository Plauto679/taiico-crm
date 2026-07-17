"""add per-user mail configuration

Revision ID: 20260717_0005
Revises: 20260716_0004
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260717_0005"
down_revision: Union[str, None] = "20260716_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_mail_configurations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("email_address", sa.String(length=255), nullable=False),
        sa.Column("smtp_host", sa.String(length=255), nullable=False),
        sa.Column("smtp_port", sa.Integer(), nullable=False),
        sa.Column("use_starttls", sa.Boolean(), nullable=False),
        sa.Column("encrypted_password", sa.Text(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_user_mail_configurations_username", "user_mail_configurations", ["username"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_user_mail_configurations_username", table_name="user_mail_configurations")
    op.drop_table("user_mail_configurations")
