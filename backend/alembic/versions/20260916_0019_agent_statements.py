"""Monthly prospectors' statements, manual adjustments and delivery history."""
from alembic import op
import sqlalchemy as sa
revision = '20260916_0019'
down_revision = '20260914_0018'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('agent_statements',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('period_id', sa.String(36), sa.ForeignKey('prospector_commission_periods.id'), nullable=False),
        sa.Column('prospector_id', sa.String(36), sa.ForeignKey('prospectors.id'), nullable=False),
        sa.Column('month', sa.Date(), nullable=False),
        sa.Column('currency', sa.String(10), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('recipient', sa.String(320), nullable=False),
        *[sa.Column(name, sa.JSON(), nullable=False) for name in ('lines','adjustments','carry','history')],
        sa.Column('own_amount', sa.Numeric(16,2), nullable=False),
        sa.Column('total_amount', sa.Numeric(16,2), nullable=False),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('delivery_state', sa.String(30), nullable=False),
        sa.Column('delivery_error', sa.Text()),
        sa.Column('sent_at', sa.DateTime()), sa.Column('paid_at', sa.DateTime()),
        sa.Column('created_by', sa.String(320), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('period_id','prospector_id', name='uq_agent_statement_period_prospector'))
    for name in ('period_id','prospector_id','month'):
        op.create_index('ix_agent_statements_'+name,'agent_statements',[name])


def downgrade():
    op.drop_table('agent_statements')
