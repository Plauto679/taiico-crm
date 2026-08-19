"""add client registry identity and Drive fields

Revision ID: 20260819_0008
Revises: 20260813_0007
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260819_0008"
down_revision: Union[str, None] = "20260813_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column("identity_status", sa.String(length=30), nullable=False, server_default="prospect"),
    )
    op.add_column("clients", sa.Column("drive_folder_id", sa.String(length=255), nullable=True))
    op.add_column("clients", sa.Column("drive_folder_url", sa.String(length=1000), nullable=True))
    op.add_column("clients", sa.Column("drive_folder_name", sa.String(length=500), nullable=True))
    op.add_column("clients", sa.Column("drive_verified_at", sa.DateTime(), nullable=True))
    op.execute(
        "UPDATE clients SET identity_status = 'identified' "
        "WHERE rfc IS NOT NULL AND TRIM(rfc) <> ''"
    )
    op.create_index("ix_clients_identity_status", "clients", ["identity_status"], unique=False)
    op.create_index("ix_clients_drive_folder_id", "clients", ["drive_folder_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_clients_drive_folder_id", table_name="clients")
    op.drop_index("ix_clients_identity_status", table_name="clients")
    op.drop_column("clients", "drive_verified_at")
    op.drop_column("clients", "drive_folder_name")
    op.drop_column("clients", "drive_folder_url")
    op.drop_column("clients", "drive_folder_id")
    op.drop_column("clients", "identity_status")
