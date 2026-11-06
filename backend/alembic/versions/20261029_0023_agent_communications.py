"""Agent communication preferences independent of workbook reloads."""
from alembic import op
import sqlalchemy as sa
revision = '20261029_0023'
down_revision = '20261019_0022'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('agent_communication_preferences',
        sa.Column('agent_key',sa.String(160),primary_key=True),
        sa.Column('agent_name',sa.String(500),nullable=False),
        sa.Column('emails',sa.JSON(),nullable=False),
        sa.Column('enabled',sa.Boolean(),nullable=False),
        sa.Column('history',sa.JSON(),nullable=False),
        sa.Column('updated_at',sa.DateTime(),nullable=False))

def downgrade():
    op.drop_table('agent_communication_preferences')
