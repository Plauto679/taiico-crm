"""Scoped preparation and human review of insurance movements."""
from alembic import op
import sqlalchemy as sa
revision = '20261109_0024'
down_revision = '20261029_0023'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('mesa_cases',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('created_by', sa.String(320), nullable=False),
        sa.Column('agent_rfc', sa.String(20), nullable=False),
        sa.Column('promotoria', sa.String(100), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('documents', sa.JSON(), nullable=False),
        sa.Column('history', sa.JSON(), nullable=False),
        sa.Column('folder_id', sa.String(200)),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False))
    op.create_index('ix_mesa_cases_agent_rfc', 'mesa_cases', ['agent_rfc'])
    op.create_index('ix_mesa_cases_promotoria', 'mesa_cases', ['promotoria'])


def downgrade():
    op.drop_table('mesa_cases')
