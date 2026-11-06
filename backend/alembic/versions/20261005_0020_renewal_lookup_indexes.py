"""Index repeated lookups during canonical renewal ingestion."""

from alembic import op
import sqlalchemy as sa

revision = "20261005_0020"
down_revision = "20260916_0019"
branch_labels = None
depends_on = None


def upgrade():
    # The existing partial unique RFC index cannot serve lookups without its
    # non-empty predicate. Keep its uniqueness rule and add a full lookup index.
    op.create_index("ix_clients_rfc_lookup", "clients", [sa.text("upper(trim(rfc))")])
    op.create_index("ix_renewals_policy_deadline", "renewals", ["original_policy_id", "renewal_deadline"])


def downgrade():
    op.drop_index("ix_renewals_policy_deadline", table_name="renewals")
    op.drop_index("ix_clients_rfc_lookup", table_name="clients")
