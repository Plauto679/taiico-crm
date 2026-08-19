"""enforce unique normalized client RFC

Revision ID: 20260819_0009
Revises: 20260819_0008
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260819_0009"
down_revision: Union[str, None] = "20260819_0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE UNIQUE INDEX uq_clients_normalized_rfc "
        "ON clients (UPPER(TRIM(rfc))) "
        "WHERE rfc IS NOT NULL AND TRIM(rfc) <> ''"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_clients_normalized_rfc")
