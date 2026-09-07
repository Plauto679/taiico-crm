"""Add commercial management foundation.

Revision ID: 20260905_0015
Revises: 20260901_0014
"""

from alembic import op
import sqlalchemy as sa


revision = "20260905_0015"
down_revision = "20260901_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("metadata", sa.JSON(), nullable=True))
    op.create_table(
        "client_contacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("position", sa.String(length=255)),
        sa.Column("area", sa.String(length=255)),
        sa.Column("phone", sa.String(length=50)),
        sa.Column("whatsapp", sa.String(length=50)),
        sa.Column("email", sa.String(length=320)),
        sa.Column("decision_role", sa.String(length=50), nullable=False, server_default="contact"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_economic_decision_maker", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_client_contacts_client_id", "client_contacts", ["client_id"])

    op.create_table(
        "commercial_stages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("base_conversion_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("metadata", sa.JSON()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_commercial_stages_code", "commercial_stages", ["code"])

    op.create_table(
        "commercial_opportunities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("client_id", sa.String(length=36)),
        sa.Column("client_name", sa.String(length=255), nullable=False),
        sa.Column("product_id", sa.String(length=36)),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("business_line", sa.String(length=80)),
        sa.Column("owner_agent_rfc", sa.String(length=50), nullable=False),
        sa.Column("owner_agent_name", sa.String(length=255), nullable=False),
        sa.Column("owner_promotoria", sa.String(length=100), nullable=False),
        sa.Column("potential_premium", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="MXN"),
        sa.Column("stage_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("source", sa.String(length=100)),
        sa.Column("referred_by", sa.String(length=255)),
        sa.Column("estimated_close_date", sa.Date()),
        sa.Column("detected_need", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("competition", sa.String(length=255)),
        sa.Column("decision_maker_access", sa.Boolean()),
        sa.Column("financial_statements_available", sa.Boolean()),
        sa.Column("economic_capacity", sa.String(length=50)),
        sa.Column("relationship_level", sa.String(length=50)),
        sa.Column("closed_premium", sa.Numeric(14, 2)),
        sa.Column("issued_premium", sa.Numeric(14, 2)),
        sa.Column("paid_premium", sa.Numeric(14, 2)),
        sa.Column("policy_id", sa.String(length=36)),
        sa.Column("lost_reason", sa.String(length=100)),
        sa.Column("close_comment", sa.Text()),
        sa.Column("next_activity_at", sa.DateTime()),
        sa.Column("created_by", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["stage_id"], ["commercial_stages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("client_id", "product_id", "owner_agent_rfc", "owner_promotoria", "stage_id", "status", "priority", "policy_id", "next_activity_at"):
        op.create_index(f"ix_commercial_opportunities_{column}", "commercial_opportunities", [column])

    op.create_table(
        "commercial_opportunity_quotes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("opportunity_id", sa.String(length=36), nullable=False),
        sa.Column("quote_id", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["commercial_opportunities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quote_id", name="uq_commercial_opportunity_quote_id"),
    )
    op.create_index("ix_commercial_opportunity_quotes_opportunity_id", "commercial_opportunity_quotes", ["opportunity_id"])
    op.create_index("ix_commercial_opportunity_quotes_quote_id", "commercial_opportunity_quotes", ["quote_id"])

    op.create_table(
        "commercial_opportunity_stage_history",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("opportunity_id", sa.String(length=36), nullable=False),
        sa.Column("stage_id", sa.String(length=36), nullable=False),
        sa.Column("entered_at", sa.DateTime(), nullable=False),
        sa.Column("exited_at", sa.DateTime()),
        sa.Column("changed_by", sa.String(length=320), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("metadata", sa.JSON()),
        sa.ForeignKeyConstraint(["opportunity_id"], ["commercial_opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stage_id"], ["commercial_stages.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_commercial_opportunity_stage_history_opportunity_id", "commercial_opportunity_stage_history", ["opportunity_id"])
    op.create_index("ix_commercial_opportunity_stage_history_stage_id", "commercial_opportunity_stage_history", ["stage_id"])

    op.create_table(
        "commercial_stage_task_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("stage_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("responsible_role", sa.String(length=100)),
        sa.Column("assigned_user_id", sa.String(length=36)),
        sa.Column("sla_business_days", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("blocks_stage_change", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["stage_id"], ["commercial_stages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_commercial_stage_task_rules_stage_id", "commercial_stage_task_rules", ["stage_id"])
    op.create_index("ix_commercial_stage_task_rules_assigned_user_id", "commercial_stage_task_rules", ["assigned_user_id"])

    op.create_table(
        "commercial_opportunity_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("opportunity_id", sa.String(length=36), nullable=False),
        sa.Column("stage_history_id", sa.String(length=36), nullable=False),
        sa.Column("rule_id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["opportunity_id"], ["commercial_opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["commercial_stage_task_rules.id"]),
        sa.ForeignKeyConstraint(["stage_history_id"], ["commercial_opportunity_stage_history.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stage_history_id", "rule_id", name="uq_commercial_stage_task_once"),
        sa.UniqueConstraint("task_id"),
    )
    for column in ("opportunity_id", "stage_history_id", "rule_id", "task_id"):
        op.create_index(f"ix_commercial_opportunity_tasks_{column}", "commercial_opportunity_tasks", [column])

    op.create_table(
        "commercial_activities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("opportunity_id", sa.String(length=36), nullable=False),
        sa.Column("activity_type", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("responsible_user_id", sa.String(length=36)),
        sa.Column("contact_id", sa.String(length=36)),
        sa.Column("reminder_at", sa.DateTime()),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_by", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["client_contacts.id"]),
        sa.ForeignKeyConstraint(["opportunity_id"], ["commercial_opportunities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["responsible_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("opportunity_id", "scheduled_at", "responsible_user_id", "contact_id", "status"):
        op.create_index(f"ix_commercial_activities_{column}", "commercial_activities", [column])


def downgrade() -> None:
    op.drop_table("commercial_activities")
    op.drop_table("commercial_opportunity_tasks")
    op.drop_table("commercial_stage_task_rules")
    op.drop_table("commercial_opportunity_stage_history")
    op.drop_table("commercial_opportunity_quotes")
    op.drop_table("commercial_opportunities")
    op.drop_table("commercial_stages")
    op.drop_table("client_contacts")
    op.drop_column("tasks", "metadata")
