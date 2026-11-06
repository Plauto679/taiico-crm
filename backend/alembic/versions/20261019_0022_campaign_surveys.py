"""Individual campaign survey links and responses."""
from alembic import op
import sqlalchemy as sa
revision = '20261019_0022'
down_revision = '20261009_0021'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('campaign_survey_responses',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('campaign_id', sa.String(36), sa.ForeignKey('campaigns.id'), nullable=False),
        sa.Column('recipient_key', sa.String(500), nullable=False),
        sa.Column('recipient_name', sa.String(500), nullable=False),
        sa.Column('is_test', sa.Boolean(), nullable=False),
        sa.Column('questionnaire', sa.JSON(), nullable=False),
        sa.Column('answers', sa.JSON(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('campaign_id', 'recipient_key', name='uq_survey_recipient'))
    op.create_index('ix_campaign_survey_responses_campaign_id','campaign_survey_responses',['campaign_id'])

def downgrade():
    op.drop_table('campaign_survey_responses')
