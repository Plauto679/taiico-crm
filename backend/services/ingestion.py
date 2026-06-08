from __future__ import annotations

import datetime
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from config import METLIFE_PATHS, SURA_PATHS
from database import (
    DataQualityIssue,
    IngestionRecord,
    IngestionRun,
    PaymentEvidenceRecord,
    Client,
    Policy,
    Product,
    ReconciliationMatch,
    SessionLocal,
    SourceDocument,
)
from drive.client import build_drive_service, download_drive_file
from drive.registry import upsert_drive_source_document
from parsers.metlife_cobranza import PARSER_VERSION, parse_metlife_cobranza_workbook
from parsers.sura_cobranza import PARSER_VERSION as SURA_PARSER_VERSION
from parsers.sura_cobranza import parse_sura_cobranza_workbook


router = APIRouter(prefix="/ingestion", tags=["ingestion"])


class MetlifeCobranzaRunRequest(BaseModel):
    source_path: Optional[str] = None
    dry_run: bool = False
    sheets: Optional[list[str]] = None


class SuraCobranzaRunRequest(BaseModel):
    source_path: Optional[str] = None
    dry_run: bool = False
    sheets: Optional[list[str]] = None
    auto_create_missing_policies: bool = False


class SuraCobranzaDriveFileRunRequest(BaseModel):
    file_id: str
    dry_run: bool = False
    sheets: Optional[list[str]] = None
    auto_create_missing_policies: bool = False


def json_ready(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    return value


def decimal_or_none(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def date_or_none(value):
    if value is None:
        return None
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value))


def register_local_source_document(db, source_path: Path, insurer_id: str) -> SourceDocument:
    resolved_path = source_path.resolve()
    source_uri = f"local_file:{resolved_path}"
    source_document = db.query(SourceDocument).filter(SourceDocument.source_uri == source_uri).first()
    if source_document:
        return source_document

    source_document = SourceDocument(
        storage_provider="local_file",
        source_uri=source_uri,
        original_filename=resolved_path.name,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        source_category="cobranza",
        insurer_id=insurer_id,
        metadata_json={"local_path": str(resolved_path)},
    )
    db.add(source_document)
    db.flush()
    return source_document


def create_data_quality_issue(db, ingestion_run_id, ingestion_record_id, issue):
    db.add(
        DataQualityIssue(
            ingestion_run_id=ingestion_run_id,
            ingestion_record_id=ingestion_record_id,
            severity=issue["severity"],
            issue_type=issue["issue_type"],
            issue_summary=issue["issue_summary"],
        )
    )


def find_policy_match(db, insurer_id: str, policy_number: str | None):
    if not policy_number:
        return None, "failed", Decimal("0.00"), "missing_policy_number"

    matches = (
        db.query(Policy)
        .filter(Policy.insurer_id == insurer_id)
        .filter(Policy.policy_number == policy_number)
        .all()
    )
    if len(matches) == 1:
        return matches[0], "matched", Decimal("1.00"), "policy_number_exact"
    if len(matches) > 1:
        return None, "ambiguous", Decimal("0.50"), "multiple_policy_number_matches"
    return None, "unmatched", Decimal("0.00"), "policy_number_not_found"


def ensure_sura_product(db, product_branch: str | None) -> Product:
    branch = (product_branch or "DANOS").upper()
    product_id_by_branch = {
        "VIDA": "prod_sura_vida",
        "GMM": "prod_sura_gmm",
        "DANOS": "prod_sura_danos",
    }
    product_name_by_branch = {
        "VIDA": "Sura Vida",
        "GMM": "Sura GMM",
        "DANOS": "Sura Daños / No Vida",
    }

    product_id = product_id_by_branch.get(branch, "prod_sura_danos")
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        return product

    product = Product(
        id=product_id,
        insurer_id="sura",
        name=product_name_by_branch.get(branch, "Sura Daños / No Vida"),
        branch=branch,
    )
    db.add(product)
    db.flush()
    return product


def find_or_create_provisional_client(db, client_name: str | None, row_metadata: dict) -> Client:
    name = (client_name or "SURA CLIENTE POR CONFIRMAR").strip()
    existing = db.query(Client).filter(Client.full_name == name).first()
    if existing:
        return existing

    client = Client(
        full_name=name,
        responsible_user_id="usr_pamela",
        status="active",
        metadata_json={
            "created_from": "sura_cobranza_evidence",
            "requires_human_review": True,
            **row_metadata,
        },
    )
    db.add(client)
    db.flush()
    return client


def infer_payment_frequency(receipt_series: str | None) -> str:
    if not receipt_series or "/" not in str(receipt_series):
        return "unknown"

    try:
        total_receipts = int(str(receipt_series).split("/")[-1])
    except ValueError:
        return "unknown"

    if total_receipts == 1:
        return "annual"
    if total_receipts == 2:
        return "semi_annual"
    if total_receipts == 4:
        return "quarterly"
    if total_receipts == 12:
        return "monthly"
    return "unknown"


def materialize_sura_policy_from_evidence(db, row) -> tuple[Policy, str, Decimal, str]:
    policy_number = row.normalized_payload.get("policy_number")
    if not policy_number:
        return None, "failed", Decimal("0.00"), "missing_policy_number"

    existing, status, confidence, basis = find_policy_match(db, "sura", policy_number)
    if existing:
        return existing, status, confidence, basis

    existing_any_insurer = db.query(Policy).filter(Policy.policy_number == policy_number).first()
    if existing_any_insurer:
        return None, "ambiguous", Decimal("0.50"), "policy_number_exists_for_different_insurer"

    product = ensure_sura_product(db, row.normalized_payload.get("product_branch"))
    start_date = (
        date_or_none(row.normalized_payload.get("policy_effective_start"))
        or date_or_none(row.normalized_payload.get("payment_date"))
        or date_or_none(row.normalized_payload.get("source_cutoff_date"))
        or datetime.date.today()
    )
    end_date = start_date + datetime.timedelta(days=365)
    premium_amount = decimal_or_none(row.normalized_payload.get("paid_amount")) or Decimal("0.00")
    commission_percentage = decimal_or_none(row.normalized_payload.get("commission_percentage_paid")) or Decimal("0.00")

    client = find_or_create_provisional_client(
        db,
        row.normalized_payload.get("client_name"),
        {
            "source_policy_number": policy_number,
            "source_insurer": "sura",
            "source_format": row.normalized_payload.get("source_format"),
        },
    )

    policy = Policy(
        policy_number=policy_number,
        client_id=client.id,
        insurer_id="sura",
        product_id=product.id,
        effective_start_date=start_date,
        effective_end_date=end_date,
        status="in_force",
        premium_amount=premium_amount,
        payment_frequency=infer_payment_frequency(row.normalized_payload.get("receipt_series")),
        responsible_user_id="usr_pamela",
        commission_percentage=commission_percentage,
        metadata_json=json_ready({
            "created_from": "sura_cobranza_evidence",
            "provisional": True,
            "requires_human_review": True,
            "source_format": row.normalized_payload.get("source_format"),
            "source_cutoff_date": row.normalized_payload.get("source_cutoff_date"),
            "policy_effective_start": row.normalized_payload.get("policy_effective_start"),
            "receipt_number": row.normalized_payload.get("receipt_number"),
            "receipt_series": row.normalized_payload.get("receipt_series"),
            "currency": row.normalized_payload.get("currency"),
            "prospectador_name": row.normalized_payload.get("prospectador_name"),
            "prospectador_percentage": row.normalized_payload.get("prospectador_percentage"),
            "prospectador_commission_amount": row.normalized_payload.get("prospectador_commission_amount"),
        }),
    )
    db.add(policy)
    db.flush()
    return policy, "created_provisional", Decimal("0.75"), "created_from_sura_cobranza_evidence"


def serialize_sura_dry_run(source_reference: str, parsed_rows, workbook_issues) -> dict:
    sheet_counts = {}
    row_issue_count = 0
    source_formats = {}
    for row in parsed_rows:
        sheet_counts[row.sheet_name] = sheet_counts.get(row.sheet_name, 0) + 1
        row_issue_count += len(row.issues)
        source_format = row.normalized_payload.get("source_format")
        source_formats[source_format] = source_formats.get(source_format, 0) + 1

    return {
        "dry_run": True,
        "source_reference": source_reference,
        "rows_read": len(parsed_rows),
        "sheet_counts": sheet_counts,
        "source_formats": source_formats,
        "workbook_issues": workbook_issues,
        "row_issues_count": row_issue_count,
        "sample_rows": [
            {
                "sheet_name": row.sheet_name,
                "row_number": row.row_number,
                "row_hash": row.row_hash,
                "normalized_payload": json_ready(row.normalized_payload),
                "issues": row.issues,
            }
            for row in parsed_rows[:3]
        ],
    }


def ingest_sura_cobranza_rows(
    db,
    source_document: SourceDocument,
    parsed_rows,
    workbook_issues,
    auto_create_missing_policies: bool = False,
) -> dict:
    run = IngestionRun(
        source_document_id=source_document.id,
        parser_name="sura_cobranza_workbook",
        parser_version=SURA_PARSER_VERSION,
        status="started",
    )
    db.add(run)
    db.flush()

    issue_count = 0
    for issue in workbook_issues:
        create_data_quality_issue(db, run.id, None, issue)
        issue_count += 1

    run.rows_read = len(parsed_rows)
    materialized_policy_count = 0

    for row in parsed_rows:
        existing_record = (
            db.query(IngestionRecord)
            .filter(IngestionRecord.source_document_id == source_document.id)
            .filter(IngestionRecord.sheet_name == row.sheet_name)
            .filter(IngestionRecord.row_number == row.row_number)
            .filter(IngestionRecord.row_hash == row.row_hash)
            .first()
        )
        if existing_record:
            run.rows_skipped += 1
            continue

        policy_number = row.normalized_payload.get("policy_number")
        policy, recon_status, confidence, match_basis = find_policy_match(db, "sura", policy_number)
        if row.issues and any(issue["issue_type"] == "missing_policy_number" for issue in row.issues):
            recon_status = "failed"
        elif recon_status == "unmatched" and auto_create_missing_policies:
            policy, recon_status, confidence, match_basis = materialize_sura_policy_from_evidence(db, row)
            if recon_status == "created_provisional":
                materialized_policy_count += 1

        ingestion_record = IngestionRecord(
            ingestion_run_id=run.id,
            source_document_id=source_document.id,
            sheet_name=row.sheet_name,
            row_number=row.row_number,
            row_hash=row.row_hash,
            source_payload=json_ready(row.source_payload),
            normalized_payload=json_ready(row.normalized_payload),
            related_object_type="policy" if policy else None,
            related_object_id=policy.id if policy else None,
            reconciliation_status=recon_status,
            reconciliation_confidence=confidence,
            issue_summary="; ".join(issue["issue_summary"] for issue in row.issues) if row.issues else None,
        )
        db.add(ingestion_record)
        db.flush()

        db.add(
            ReconciliationMatch(
                ingestion_record_id=ingestion_record.id,
                matched_object_type="policy",
                matched_object_id=policy.id if policy else None,
                match_basis=match_basis,
                confidence=confidence,
                status=recon_status,
            )
        )

        if recon_status in {"unmatched", "ambiguous"}:
            create_data_quality_issue(
                db,
                run.id,
                ingestion_record.id,
                {
                    "severity": "high" if recon_status == "ambiguous" else "normal",
                    "issue_type": "ambiguous_policy_match" if recon_status == "ambiguous" else "unmatched_policy",
                    "issue_summary": f"{row.sheet_name} row {row.row_number} could not be matched exactly to a SURA policy.",
                },
            )
            issue_count += 1
        elif recon_status == "created_provisional":
            create_data_quality_issue(
                db,
                run.id,
                ingestion_record.id,
                {
                    "severity": "normal",
                    "issue_type": "provisional_policy_created",
                    "issue_summary": f"{row.sheet_name} row {row.row_number} created provisional SURA policy {policy_number} from cobranza evidence.",
                },
            )
            issue_count += 1

        for issue in row.issues:
            create_data_quality_issue(db, run.id, ingestion_record.id, issue)
            issue_count += 1

        if policy_number:
            payment_date = date_or_none(row.normalized_payload.get("payment_date"))
            db.add(
                PaymentEvidenceRecord(
                    ingestion_record_id=ingestion_record.id,
                    policy_id=policy.id if policy else None,
                    client_id=policy.client_id if policy else None,
                    insurer_id="sura",
                    product_branch=row.normalized_payload.get("product_branch"),
                    policy_number=policy_number,
                    client_name=row.normalized_payload.get("client_name") or (policy.client.full_name if policy and policy.client else None),
                    evidence_type="commission_statement",
                    evidence_date=payment_date,
                    paid_amount=decimal_or_none(row.normalized_payload.get("paid_amount")),
                    net_commission_amount=decimal_or_none(row.normalized_payload.get("net_commission_amount")),
                    receipt_number=row.normalized_payload.get("receipt_number"),
                    insurer_reference=row.normalized_payload.get("liquidation_number"),
                    payment_application_status="applied_by_insurer" if payment_date else None,
                    reconciliation_status=recon_status,
                    reconciliation_confidence=confidence,
                    metadata_json=json_ready({
                        "receipt_series": row.normalized_payload.get("receipt_series"),
                        "agent_code": row.normalized_payload.get("agent_code"),
                        "agency_name": row.normalized_payload.get("agency_name"),
                        "group_code": row.normalized_payload.get("group_code"),
                        "office_code": row.normalized_payload.get("office_code"),
                        "branch_code": row.normalized_payload.get("branch_code"),
                        "currency": row.normalized_payload.get("currency"),
                        "source_cutoff_date": row.normalized_payload.get("source_cutoff_date"),
                        "policy_effective_start": row.normalized_payload.get("policy_effective_start"),
                        "exchange_rate": row.normalized_payload.get("exchange_rate"),
                        "net_premium_amount": row.normalized_payload.get("net_premium_amount"),
                        "commission_percentage_paid": row.normalized_payload.get("commission_percentage_paid"),
                        "commission_right_amount": row.normalized_payload.get("commission_right_amount"),
                        "total_commission_paid": row.normalized_payload.get("total_commission_paid"),
                        "voucher_number": row.normalized_payload.get("voucher_number"),
                        "prospectador_name": row.normalized_payload.get("prospectador_name"),
                        "prospectador_percentage": row.normalized_payload.get("prospectador_percentage"),
                        "prospectador_commission_amount": row.normalized_payload.get("prospectador_commission_amount"),
                        "source_format": row.normalized_payload.get("source_format"),
                    }),
                )
            )
            run.rows_imported += 1
        else:
            run.rows_failed += 1

    run.metadata_json = {
        "data_quality_issues_created": issue_count,
        "materialized_policy_count": materialized_policy_count,
        "auto_create_missing_policies": auto_create_missing_policies,
    }
    run.status = "completed_with_warnings" if issue_count or run.rows_failed else "completed"
    run.completed_at = datetime.datetime.utcnow()
    db.flush()

    return serialize_ingestion_run(run)


def ingest_metlife_cobranza_from_local_file(source_path: Path, sheets: list[str] | None = None, dry_run: bool = False) -> dict:
    if not source_path.exists():
        raise FileNotFoundError(f"MetLife cobranza source file not found: {source_path}")

    parsed_rows, workbook_issues = parse_metlife_cobranza_workbook(source_path, sheets=sheets)
    if dry_run:
        return {
            "dry_run": True,
            "source_path": str(source_path),
            "rows_read": len(parsed_rows),
            "workbook_issues": workbook_issues,
        }

    db = SessionLocal()
    try:
        source_document = register_local_source_document(db, source_path, "metlife")
        run = IngestionRun(
            source_document_id=source_document.id,
            parser_name="metlife_cobranza_workbook",
            parser_version=PARSER_VERSION,
            status="started",
        )
        db.add(run)
        db.flush()

        issue_count = 0
        for issue in workbook_issues:
            create_data_quality_issue(db, run.id, None, issue)
            issue_count += 1

        run.rows_read = len(parsed_rows)

        for row in parsed_rows:
            existing_record = (
                db.query(IngestionRecord)
                .filter(IngestionRecord.source_document_id == source_document.id)
                .filter(IngestionRecord.sheet_name == row.sheet_name)
                .filter(IngestionRecord.row_number == row.row_number)
                .filter(IngestionRecord.row_hash == row.row_hash)
                .first()
            )
            if existing_record:
                run.rows_skipped += 1
                continue

            policy_number = row.normalized_payload.get("policy_number")
            policy, recon_status, confidence, match_basis = find_policy_match(db, "metlife", policy_number)
            if row.issues and any(issue["issue_type"] == "missing_policy_number" for issue in row.issues):
                recon_status = "failed"

            ingestion_record = IngestionRecord(
                ingestion_run_id=run.id,
                source_document_id=source_document.id,
                sheet_name=row.sheet_name,
                row_number=row.row_number,
                row_hash=row.row_hash,
                source_payload=json_ready(row.source_payload),
                normalized_payload=json_ready(row.normalized_payload),
                related_object_type="policy" if policy else None,
                related_object_id=policy.id if policy else None,
                reconciliation_status=recon_status,
                reconciliation_confidence=confidence,
                issue_summary="; ".join(issue["issue_summary"] for issue in row.issues) if row.issues else None,
            )
            db.add(ingestion_record)
            db.flush()

            db.add(
                ReconciliationMatch(
                    ingestion_record_id=ingestion_record.id,
                    matched_object_type="policy",
                    matched_object_id=policy.id if policy else None,
                    match_basis=match_basis,
                    confidence=confidence,
                    status=recon_status,
                )
            )

            if recon_status in {"unmatched", "ambiguous"}:
                create_data_quality_issue(
                    db,
                    run.id,
                    ingestion_record.id,
                    {
                        "severity": "high" if recon_status == "ambiguous" else "normal",
                        "issue_type": "ambiguous_policy_match" if recon_status == "ambiguous" else "unmatched_policy",
                        "issue_summary": f"{row.sheet_name} row {row.row_number} could not be matched exactly to a MetLife policy.",
                    },
                )
                issue_count += 1

            for issue in row.issues:
                create_data_quality_issue(db, run.id, ingestion_record.id, issue)
                issue_count += 1

            if policy_number:
                payment_date = date_or_none(row.normalized_payload.get("payment_date"))
                db.add(
                    PaymentEvidenceRecord(
                        ingestion_record_id=ingestion_record.id,
                        policy_id=policy.id if policy else None,
                        client_id=policy.client_id if policy else None,
                        insurer_id="metlife",
                        product_branch=row.normalized_payload.get("product_branch"),
                        policy_number=policy_number,
                        client_name=policy.client.full_name if policy and policy.client else None,
                        evidence_type="commission_statement",
                        evidence_date=payment_date,
                        paid_amount=decimal_or_none(row.normalized_payload.get("paid_amount")),
                        gross_commission_amount=decimal_or_none(row.normalized_payload.get("gross_commission_amount")),
                        net_commission_amount=decimal_or_none(row.normalized_payload.get("net_commission_amount")),
                        tax_amount=decimal_or_none(row.normalized_payload.get("tax_amount")),
                        receipt_status=row.normalized_payload.get("receipt_status"),
                        policy_status_source=row.normalized_payload.get("policy_status_source"),
                        collection_channel=row.normalized_payload.get("collection_channel"),
                        commission_type=row.normalized_payload.get("commission_type"),
                        payment_application_status=row.normalized_payload.get("receipt_status"),
                        reconciliation_status=recon_status,
                        reconciliation_confidence=confidence,
                        metadata_json=json_ready({
                            "source_period_key": row.normalized_payload.get("source_period_key"),
                            "product_name": row.normalized_payload.get("product_name"),
                            "agent_code": row.normalized_payload.get("agent_code"),
                            "msi": row.normalized_payload.get("msi"),
                            "policy_life_year": row.normalized_payload.get("policy_life_year"),
                            "insured_age": row.normalized_payload.get("insured_age"),
                            "insured_gender": row.normalized_payload.get("insured_gender"),
                            "insured_state": row.normalized_payload.get("insured_state"),
                            "branch_code": row.normalized_payload.get("branch_code"),
                        }),
                    )
                )
                run.rows_imported += 1
            else:
                run.rows_failed += 1

        run.metadata_json = {"data_quality_issues_created": issue_count}
        run.status = "completed_with_warnings" if issue_count or run.rows_failed else "completed"
        run.completed_at = datetime.datetime.utcnow()
        db.commit()

        return serialize_ingestion_run(run)
    except IntegrityError as exc:
        db.rollback()
        raise RuntimeError(f"Ingestion failed due to an integrity error: {exc}") from exc
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def ingest_sura_cobranza_from_local_file(
    source_path: Path,
    sheets: list[str] | None = None,
    dry_run: bool = False,
    auto_create_missing_policies: bool = False,
) -> dict:
    if not source_path.exists():
        raise FileNotFoundError(f"SURA cobranza source file not found: {source_path}")

    parsed_rows, workbook_issues = parse_sura_cobranza_workbook(source_path, sheets=sheets)
    if dry_run:
        return serialize_sura_dry_run(str(source_path), parsed_rows, workbook_issues)

    db = SessionLocal()
    try:
        source_document = register_local_source_document(db, source_path, "sura")
        result = ingest_sura_cobranza_rows(
            db,
            source_document,
            parsed_rows,
            workbook_issues,
            auto_create_missing_policies=auto_create_missing_policies,
        )
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise RuntimeError(f"Ingestion failed due to an integrity error: {exc}") from exc
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_drive_file_metadata(service, file_id: str) -> dict:
    return service.files().get(
        fileId=file_id,
        fields=(
            "id, name, mimeType, parents, webViewLink, createdTime, modifiedTime, "
            "md5Checksum, size, version, driveId"
        ),
        supportsAllDrives=True,
    ).execute()


def ingest_sura_cobranza_from_drive_file(
    file_id: str,
    sheets: list[str] | None = None,
    dry_run: bool = False,
    auto_create_missing_policies: bool = False,
) -> dict:
    service = build_drive_service()
    file_metadata = get_drive_file_metadata(service, file_id)
    source_config = {
        "folder_id": (file_metadata.get("parents") or [None])[0],
        "source_category": "cobranza",
        "insurer_id": "sura",
        "product_branch": None,
        "parser_name": "sura_cobranza_workbook",
    }

    suffix = ""
    if file_metadata.get("name") and "." in file_metadata["name"]:
        suffix = "." + file_metadata["name"].split(".")[-1]

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix="taiico-drive-sura-cobranza-", suffix=suffix, delete=False) as temp_file:
            temp_path = Path(temp_file.name)

        download_drive_file(service, file_id, temp_path)
        parsed_rows, workbook_issues = parse_sura_cobranza_workbook(temp_path, sheets=sheets)

        if dry_run:
            return {
                **serialize_sura_dry_run(f"google_drive:{file_id}", parsed_rows, workbook_issues),
                "source_document": {
                    "google_drive_file_id": file_metadata.get("id"),
                    "google_drive_parent_id": (file_metadata.get("parents") or [None])[0],
                    "shared_drive_id": file_metadata.get("driveId"),
                    "original_filename": file_metadata.get("name"),
                    "mime_type": file_metadata.get("mimeType"),
                    "web_view_link": file_metadata.get("webViewLink"),
                },
            }

        db = SessionLocal()
        try:
            source_document, _ = upsert_drive_source_document(
                db,
                file_metadata,
                source_config,
                "cobranza.sura.drive_file",
            )
            result = ingest_sura_cobranza_rows(
                db,
                source_document,
                parsed_rows,
                workbook_issues,
                auto_create_missing_policies=auto_create_missing_policies,
            )
            db.commit()
            return result
        except IntegrityError as exc:
            db.rollback()
            raise RuntimeError(f"Ingestion failed due to an integrity error: {exc}") from exc
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)


def serialize_ingestion_run(run: IngestionRun) -> dict:
    return {
        "id": run.id,
        "source_document_id": run.source_document_id,
        "parser_name": run.parser_name,
        "parser_version": run.parser_version,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "rows_read": run.rows_read,
        "rows_imported": run.rows_imported,
        "rows_updated": run.rows_updated,
        "rows_skipped": run.rows_skipped,
        "rows_failed": run.rows_failed,
        "error_summary": run.error_summary,
        "metadata": run.metadata_json,
    }


@router.post("/metlife/cobranza/run")
async def run_metlife_cobranza_ingestion(request: MetlifeCobranzaRunRequest = Body(default=MetlifeCobranzaRunRequest())):
    source_path = Path(request.source_path) if request.source_path else Path(METLIFE_PATHS["COBRANZA"])
    try:
        return ingest_metlife_cobranza_from_local_file(source_path, sheets=request.sheets, dry_run=request.dry_run)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sura/cobranza/run")
async def run_sura_cobranza_ingestion(request: SuraCobranzaRunRequest = Body(default=SuraCobranzaRunRequest())):
    source_path = Path(request.source_path) if request.source_path else Path(SURA_PATHS["COBRANZA"])
    try:
        return ingest_sura_cobranza_from_local_file(
            source_path,
            sheets=request.sheets,
            dry_run=request.dry_run,
            auto_create_missing_policies=request.auto_create_missing_policies,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sura/cobranza/drive-file/run")
async def run_sura_cobranza_drive_file_ingestion(request: SuraCobranzaDriveFileRunRequest):
    try:
        return ingest_sura_cobranza_from_drive_file(
            request.file_id,
            sheets=request.sheets,
            dry_run=request.dry_run,
            auto_create_missing_policies=request.auto_create_missing_policies,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/runs")
async def list_ingestion_runs(limit: int = Query(25, ge=1, le=200)):
    db = SessionLocal()
    try:
        runs = db.query(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit).all()
        return [serialize_ingestion_run(run) for run in runs]
    finally:
        db.close()


@router.get("/runs/{run_id}")
async def get_ingestion_run(run_id: str):
    db = SessionLocal()
    try:
        run = db.query(IngestionRun).filter(IngestionRun.id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Ingestion run not found")
        return serialize_ingestion_run(run)
    finally:
        db.close()


@router.get("/runs/{run_id}/records")
async def get_ingestion_run_records(run_id: str, limit: int = Query(100, ge=1, le=500)):
    db = SessionLocal()
    try:
        records = (
            db.query(IngestionRecord)
            .filter(IngestionRecord.ingestion_run_id == run_id)
            .order_by(IngestionRecord.sheet_name, IngestionRecord.row_number)
            .limit(limit)
            .all()
        )
        return [
            {
                "id": record.id,
                "sheet_name": record.sheet_name,
                "row_number": record.row_number,
                "row_hash": record.row_hash,
                "reconciliation_status": record.reconciliation_status,
                "reconciliation_confidence": float(record.reconciliation_confidence) if record.reconciliation_confidence is not None else None,
                "related_object_type": record.related_object_type,
                "related_object_id": record.related_object_id,
                "issue_summary": record.issue_summary,
                "normalized_payload": record.normalized_payload,
            }
            for record in records
        ]
    finally:
        db.close()
