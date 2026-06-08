"""add ingestion provenance tables

Revision ID: 20260527_0001
Revises:
Create Date: 2026-05-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260527_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_documents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("storage_provider", sa.String(length=50), nullable=False),
        sa.Column("google_drive_file_id", sa.String(length=255), nullable=True),
        sa.Column("google_drive_parent_id", sa.String(length=255), nullable=True),
        sa.Column("shared_drive_id", sa.String(length=255), nullable=True),
        sa.Column("source_uri", sa.String(length=1000), nullable=False),
        sa.Column("web_view_link", sa.String(length=1000), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("source_category", sa.String(length=100), nullable=False),
        sa.Column("insurer_id", sa.String(length=50), nullable=True),
        sa.Column("product_branch", sa.String(length=50), nullable=True),
        sa.Column("source_period_start", sa.Date(), nullable=True),
        sa.Column("source_period_end", sa.Date(), nullable=True),
        sa.Column("drive_created_at", sa.DateTime(), nullable=True),
        sa.Column("drive_modified_at", sa.DateTime(), nullable=True),
        sa.Column("detected_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.UniqueConstraint("google_drive_file_id", name="uq_source_documents_google_drive_file_id"),
        sa.UniqueConstraint("source_uri", name="uq_source_documents_source_uri"),
    )
    op.create_index(
        "idx_source_documents_category_insurer",
        "source_documents",
        ["source_category", "insurer_id", "drive_modified_at"],
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("parser_name", sa.String(length=100), nullable=False),
        sa.Column("parser_version", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("rows_read", sa.Integer(), nullable=False),
        sa.Column("rows_imported", sa.Integer(), nullable=False),
        sa.Column("rows_updated", sa.Integer(), nullable=False),
        sa.Column("rows_skipped", sa.Integer(), nullable=False),
        sa.Column("rows_failed", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
    )

    op.create_table(
        "ingestion_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("ingestion_run_id", sa.String(length=36), nullable=False),
        sa.Column("source_document_id", sa.String(length=36), nullable=False),
        sa.Column("sheet_name", sa.String(length=100), nullable=True),
        sa.Column("row_number", sa.Integer(), nullable=True),
        sa.Column("row_hash", sa.String(length=64), nullable=False),
        sa.Column("source_payload", sa.JSON(), nullable=False),
        sa.Column("normalized_payload", sa.JSON(), nullable=True),
        sa.Column("related_object_type", sa.String(length=50), nullable=True),
        sa.Column("related_object_id", sa.String(length=36), nullable=True),
        sa.Column("reconciliation_status", sa.String(length=50), nullable=False),
        sa.Column("reconciliation_confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("issue_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"]),
        sa.ForeignKeyConstraint(["source_document_id"], ["source_documents.id"]),
        sa.UniqueConstraint(
            "source_document_id",
            "sheet_name",
            "row_number",
            "row_hash",
            name="uq_ingestion_record_row_identity",
        ),
    )
    op.create_index(
        "idx_ingestion_records_run_sheet_row",
        "ingestion_records",
        ["ingestion_run_id", "sheet_name", "row_number"],
    )

    op.create_table(
        "payment_evidence_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("ingestion_record_id", sa.String(length=36), nullable=False),
        sa.Column("payment_id", sa.String(length=36), nullable=True),
        sa.Column("policy_id", sa.String(length=36), nullable=True),
        sa.Column("client_id", sa.String(length=36), nullable=True),
        sa.Column("insurer_id", sa.String(length=50), nullable=True),
        sa.Column("product_branch", sa.String(length=50), nullable=True),
        sa.Column("policy_number", sa.String(length=100), nullable=True),
        sa.Column("client_name", sa.String(length=255), nullable=True),
        sa.Column("evidence_type", sa.String(length=50), nullable=False),
        sa.Column("evidence_date", sa.Date(), nullable=True),
        sa.Column("expected_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("paid_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("gross_commission_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("net_commission_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("tax_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("receipt_number", sa.String(length=100), nullable=True),
        sa.Column("insurer_reference", sa.String(length=255), nullable=True),
        sa.Column("receipt_status", sa.String(length=100), nullable=True),
        sa.Column("policy_status_source", sa.String(length=100), nullable=True),
        sa.Column("collection_channel", sa.String(length=255), nullable=True),
        sa.Column("commission_type", sa.String(length=255), nullable=True),
        sa.Column("payment_application_status", sa.String(length=100), nullable=True),
        sa.Column("reconciliation_status", sa.String(length=50), nullable=False),
        sa.Column("reconciliation_confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"]),
        sa.ForeignKeyConstraint(["ingestion_record_id"], ["ingestion_records.id"]),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"]),
    )
    op.create_index(
        "idx_payment_evidence_policy_date",
        "payment_evidence_records",
        ["policy_number", "evidence_date"],
    )
    op.create_index(
        "idx_payment_evidence_insurer_branch",
        "payment_evidence_records",
        ["insurer_id", "product_branch", "evidence_date"],
    )

    op.create_table(
        "reconciliation_matches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("ingestion_record_id", sa.String(length=36), nullable=False),
        sa.Column("matched_object_type", sa.String(length=50), nullable=False),
        sa.Column("matched_object_id", sa.String(length=36), nullable=True),
        sa.Column("match_basis", sa.String(length=100), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_record_id"], ["ingestion_records.id"]),
    )

    op.create_table(
        "data_quality_issues",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("ingestion_run_id", sa.String(length=36), nullable=True),
        sa.Column("ingestion_record_id", sa.String(length=36), nullable=True),
        sa.Column("related_object_type", sa.String(length=50), nullable=True),
        sa.Column("related_object_id", sa.String(length=36), nullable=True),
        sa.Column("severity", sa.String(length=50), nullable=False),
        sa.Column("issue_type", sa.String(length=100), nullable=False),
        sa.Column("issue_summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("assigned_user_id", sa.String(length=36), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["ingestion_record_id"], ["ingestion_records.id"]),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"]),
    )
    op.create_index(
        "idx_data_quality_open",
        "data_quality_issues",
        ["status", "severity", "issue_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_data_quality_open", table_name="data_quality_issues")
    op.drop_table("data_quality_issues")
    op.drop_table("reconciliation_matches")
    op.drop_index("idx_payment_evidence_insurer_branch", table_name="payment_evidence_records")
    op.drop_index("idx_payment_evidence_policy_date", table_name="payment_evidence_records")
    op.drop_table("payment_evidence_records")
    op.drop_index("idx_ingestion_records_run_sheet_row", table_name="ingestion_records")
    op.drop_table("ingestion_records")
    op.drop_table("ingestion_runs")
    op.drop_index("idx_source_documents_category_insurer", table_name="source_documents")
    op.drop_table("source_documents")
