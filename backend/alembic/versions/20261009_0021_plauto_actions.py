"""Store user-owned Plauto proposals and their confirmation state."""
from alembic import op
import sqlalchemy as sa

revision = '20261009_0021'
down_revision = '20261005_0020'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('plauto_actions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('username', sa.String(320), nullable=False),
        sa.Column('client_id', sa.String(36), sa.ForeignKey('clients.id'), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_plauto_actions_username', 'plauto_actions', ['username'])


def downgrade():
    op.drop_index('ix_plauto_actions_username', table_name='plauto_actions')
    op.drop_table('plauto_actions')
