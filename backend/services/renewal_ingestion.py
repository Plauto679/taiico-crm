from __future__ import annotations

import datetime
import tempfile
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func

from config import GOOGLE_DRIVE_SOURCE_FOLDERS, METLIFE_PATHS
from database import (
    Client,
    DataQualityIssue,
    IngestionRecord,
    IngestionRun,
    Policy,
    Product,
    ReconciliationMatch,
    Renewal,
    SessionLocal,
    SourceDocument,
)
from drive.client import build_drive_service, download_drive_file
from services.client_email_directory import lookup_client_email
from services.client_folders import normalize_rfc, valid_client_rfc
from parsers.metlife_gmm_renovaciones import (
    PARSER_VERSION as GMM_PARSER_VERSION,
    parse_metlife_gmm_renewal_workbook,
)
from parsers.metlife_vida_renovaciones import (
    PARSER_VERSION as VIDA_PARSER_VERSION,
    parse_metlife_vida_renewal_workbook,
)


router = APIRouter(prefix="/renewal-ingestion", tags=["renewal-ingestion"])

SUPPORTED_SOURCES = {
    "renovaciones.metlife_gmm": (
        parse_metlife_gmm_renewal_workbook,
        "metlife_gmm_renewal_workbook",
        GMM_PARSER_VERSION,
        "GMM",
        "prod_met_gmm",
    ),
    "renovaciones.metlife_vida": (
        parse_metlife_vida_renewal_workbook,
        "metlife_vida_renewal_workbook",
        VIDA_PARSER_VERSION,
        "VIDA",
        "prod_met_vida",
    ),
}

LOCAL_CANONICAL_PATHS = {
    "renovaciones.metlife_gmm": METLIFE_PATHS["RENOVACIONES_GMM"],
    "renovaciones.metlife_vida": METLIFE_PATHS["RENOVACIONES_VIDA"],
}


class CanonicalRenewalIngestionRequest(BaseModel):
    source_key: str
    dry_run: bool = True
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


def normalize_name(value: str | None) -> str:
    return " ".join(str(value or "").strip().upper().split())


def apply_source_rfc(db, client: Client, rfc: str | None) -> bool:
    """Apply a canonical RFC only when it does not belong to another client."""
    normalized = normalize_rfc(rfc)
    if not valid_client_rfc(normalized):
        return False
    query = db.query(Client).filter(
        func.upper(func.trim(Client.rfc)) == normalized,
    )
    if client.id:
        query = query.filter(Client.id != client.id)
    conflict = query.first()
    metadata = dict(client.metadata_json or {})
    metadata["source_rfc"] = normalized
    if conflict is not None:
        metadata["source_rfc_conflict_client_id"] = conflict.id
        client.metadata_json = metadata
        return False
    metadata.pop("source_rfc_conflict_client_id", None)
    client.rfc = normalized
    client.metadata_json = metadata
    return True


def find_policy(db, policy_number: str | None):
    if not policy_number:
        return None
    return db.query(Policy).filter(
        Policy.insurer_id == "metlife",
        Policy.policy_number == str(policy_number).strip(),
    ).first()


def find_policy_number_conflict(db, policy_number: str | None):
    if not policy_number:
        return None
    return db.query(Policy).filter(
        Policy.policy_number == str(policy_number).strip(),
        Policy.insurer_id != "metlife",
    ).first()


def find_or_create_client(db, payload: dict) -> Client:
    client_name = str(payload.get("client_name") or "METLIFE CLIENTE POR CONFIRMAR").strip()
    normalized = normalize_name(client_name)
    canonical_email = None
    source_rfc = normalize_rfc(payload.get("rfc"))
    try:
        canonical_email = lookup_client_email(client_name)
    except Exception:
        # Email enrichment must not make renewal ingestion unavailable.
        pass

    for client in db.query(Client).filter(Client.full_name == client_name).all():
        if normalize_name(client.full_name) == normalized:
            if not client.email and canonical_email:
                client.email = canonical_email
            apply_source_rfc(db, client, source_rfc)
            return client

    client = Client(
        full_name=client_name,
        rfc=None,
        email=canonical_email or payload.get("email_link_or_value") or None,
        responsible_user_id="usr_pamela",
        status="active",
        metadata_json={
            "created_from": "canonical_metlife_renewal_ingestion",
            "requires_human_review": True,
            "source_rfc": source_rfc or None,
        },
    )
    apply_source_rfc(db, client, source_rfc)
    db.add(client)
    db.flush()
    return client


def create_provisional_policy(db, payload: dict, product_id: str) -> Policy:
    deadline = payload["renewal_deadline"]
    effective_start = payload.get("effective_start_date") or (deadline - datetime.timedelta(days=365))
    client = find_or_create_client(db, payload)
    product = db.query(Product).filter(Product.id == product_id).one()
    policy = Policy(
        policy_number=str(payload["policy_number"]).strip(),
        client_id=client.id,
        insurer_id="metlife",
        product_id=product.id,
        effective_start_date=effective_start,
        effective_end_date=deadline,
        status="in_force",
        premium_amount=payload.get("premium_amount") or Decimal("0"),
        payment_frequency=str(payload.get("payment_frequency_source") or "unknown").lower(),
        responsible_user_id="usr_pamela",
        document_link=payload.get("expediente_link") or None,
        metadata_json={
            "created_from": "canonical_metlife_renewal_ingestion",
            "requires_human_review": True,
            "source_policy_status": payload.get("policy_status_source"),
            "source_collection_channel": payload.get("collection_channel"),
        },
    )
    db.add(policy)
    db.flush()
    return policy


def summarize_rows(db, parsed_rows) -> dict:
    matched = 0
    unmatched = 0
    invalid = 0
    unique_renewals = set()
    for row in parsed_rows:
        payload = row.normalized_payload
        policy_number = payload.get("policy_number")
        deadline = payload.get("renewal_deadline")
        if not policy_number or not deadline:
            invalid += 1
            continue
        unique_renewals.add((str(policy_number), deadline.isoformat()))
        if find_policy(db, policy_number):
            matched += 1
        else:
            unmatched += 1
    return {
        "rows_read": len(parsed_rows),
        "unique_renewals": len(unique_renewals),
        "matched_policy_rows": matched,
        "unmatched_policy_rows": unmatched,
        "invalid_rows": invalid,
    }


def ingest_rows(db, source_document, parsed_rows, workbook_issues, parser_name, parser_version, product_id, auto_create):
    run = IngestionRun(
        source_document_id=source_document.id,
        parser_name=parser_name,
        parser_version=parser_version,
        status="started",
        rows_read=len(parsed_rows),
    )
    db.add(run)
    db.flush()

    issues_created = 0
    provisional_policies = 0
    for issue in workbook_issues:
        db.add(DataQualityIssue(ingestion_run_id=run.id, **issue))
        issues_created += 1

    for row in parsed_rows:
        existing_record = db.query(IngestionRecord).filter(
            IngestionRecord.source_document_id == source_document.id,
            IngestionRecord.sheet_name == row.sheet_name,
            IngestionRecord.row_number == row.row_number,
            IngestionRecord.row_hash == row.row_hash,
        ).first()
        payload = row.normalized_payload
        policy_number = payload.get("policy_number")
        deadline = payload.get("renewal_deadline")
        policy = find_policy(db, policy_number)
        policy_number_conflict = find_policy_number_conflict(db, policy_number) if policy is None else None
        reconciliation_status = "matched" if policy else "unmatched"
        confidence = Decimal("1.00") if policy else Decimal("0.00")
        match_basis = "policy_number_exact" if policy else "policy_number_not_found"

        if not policy_number or not deadline:
            reconciliation_status = "failed"
            match_basis = "missing_policy_number_or_renewal_deadline"
        elif policy_number_conflict is not None:
            reconciliation_status = "failed"
            match_basis = "policy_number_used_by_another_insurer"
        elif policy is None and auto_create:
            policy = create_provisional_policy(db, payload, product_id)
            provisional_policies += 1
            reconciliation_status = "created_provisional"
            confidence = Decimal("0.75")
            match_basis = "created_from_canonical_renewal_source"

        renewal = None
        if policy and deadline:
            source_rfc = normalize_rfc(payload.get("rfc"))
            if policy.client:
                apply_source_rfc(db, policy.client, source_rfc)
            if policy.client and not policy.client.email:
                try:
                    policy.client.email = lookup_client_email(policy.client.full_name)
                except Exception:
                    pass
            renewal = db.query(Renewal).filter(
                Renewal.original_policy_id == policy.id,
                Renewal.renewal_deadline == deadline,
            ).first()
            created = renewal is None
            if renewal is None:
                renewal = Renewal(
                    original_policy_id=policy.id,
                    client_id=policy.client_id,
                    renewal_deadline=deadline,
                    status="not_started",
                )
                db.add(renewal)
            renewal.renewal_quote_amount = payload.get("premium_amount")
            source_renewal_status = str(
                payload.get("renewal_status_source") or ""
            ).strip()
            # The canonical workbook is authoritative when it contains a value,
            # but an empty cell must not erase a status produced by automation.
            if source_renewal_status:
                renewal.insurer_response = source_renewal_status
            renewal.risk_level = payload.get("risk_level") or "none"
            if payload.get("expediente_link") and not policy.document_link:
                policy.document_link = payload["expediente_link"]
            if deadline > policy.effective_end_date:
                policy.effective_end_date = deadline
            db.flush()
            if created:
                run.rows_imported += 1
            else:
                run.rows_updated += 1
        else:
            run.rows_failed += 1

        issue_summary = "; ".join(issue["issue_summary"] for issue in row.issues) if row.issues else None
        if existing_record:
            record = existing_record
            record.source_payload = json_ready(row.source_payload)
            record.normalized_payload = json_ready(payload)
            record.related_object_type = "renewal" if renewal else None
            record.related_object_id = renewal.id if renewal else None
            record.reconciliation_status = reconciliation_status
            record.reconciliation_confidence = confidence
            record.issue_summary = issue_summary
        else:
            record = IngestionRecord(
                ingestion_run_id=run.id,
                source_document_id=source_document.id,
                sheet_name=row.sheet_name,
                row_number=row.row_number,
                row_hash=row.row_hash,
                source_payload=json_ready(row.source_payload),
                normalized_payload=json_ready(payload),
                related_object_type="renewal" if renewal else None,
                related_object_id=renewal.id if renewal else None,
                reconciliation_status=reconciliation_status,
                reconciliation_confidence=confidence,
                issue_summary=issue_summary,
            )
            db.add(record)
            db.flush()
            db.add(ReconciliationMatch(
                ingestion_record_id=record.id,
                matched_object_type="policy",
                matched_object_id=policy.id if policy else None,
                match_basis=match_basis,
                confidence=confidence,
                status=reconciliation_status,
            ))

        for issue in ([] if existing_record else row.issues):
            db.add(DataQualityIssue(ingestion_run_id=run.id, ingestion_record_id=record.id, **issue))
            issues_created += 1
        if not existing_record and reconciliation_status in {"unmatched", "created_provisional"}:
            db.add(DataQualityIssue(
                ingestion_run_id=run.id,
                ingestion_record_id=record.id,
                related_object_type="policy" if policy else None,
                related_object_id=policy.id if policy else None,
                severity="normal",
                issue_type="provisional_policy_created" if policy else "unmatched_policy",
                issue_summary=(
                    f"Policy {policy_number} was created provisionally from the canonical renewal source."
                    if policy else f"Policy {policy_number} was not found and was not materialized."
                ),
            ))
            issues_created += 1
        if not existing_record and policy_number_conflict is not None:
            db.add(DataQualityIssue(
                ingestion_run_id=run.id,
                ingestion_record_id=record.id,
                related_object_type="policy",
                related_object_id=policy_number_conflict.id,
                severity="high",
                issue_type="cross_insurer_policy_number_conflict",
                issue_summary=(
                    f"Policy {policy_number} could not be created for MetLife because the same number "
                    f"is already assigned to insurer {policy_number_conflict.insurer_id}."
                ),
            ))
            issues_created += 1

    run.status = "completed_with_warnings" if issues_created or run.rows_failed else "completed"
    run.completed_at = datetime.datetime.utcnow()
    run.metadata_json = {
        "data_quality_issues_created": issues_created,
        "provisional_policies_created": provisional_policies,
        "auto_create_missing_policies": auto_create,
        "source_key": (source_document.metadata_json or {}).get("configured_source_key"),
    }
    db.flush()
    return {
        "id": run.id,
        "status": run.status,
        "rows_read": run.rows_read,
        "rows_imported": run.rows_imported,
        "rows_updated": run.rows_updated,
        "rows_skipped": run.rows_skipped,
        "rows_failed": run.rows_failed,
        "metadata": run.metadata_json,
    }


def sync_local_canonical_renewals(
    source_key: str,
    *,
    auto_create_missing_policies: bool = True,
) -> dict:
    """Reconcile the SQL read model with an installed local canonical workbook."""
    spec = SUPPORTED_SOURCES.get(source_key)
    canonical_path = LOCAL_CANONICAL_PATHS.get(source_key)
    if not spec or not canonical_path:
        raise ValueError(f"No canonical renewal parser is configured for {source_key}")
    config = GOOGLE_DRIVE_SOURCE_FOLDERS.get(source_key) or {}
    file_id = config.get("file_id")
    if not file_id:
        raise ValueError(f"Missing canonical Drive file ID for {source_key}")

    parser, parser_name, parser_version, branch, product_id = spec
    db = SessionLocal()
    try:
        source_document = db.query(SourceDocument).filter(
            SourceDocument.google_drive_file_id == file_id,
        ).first()
        if not source_document:
            raise ValueError("Canonical source must be registered before ingestion")
        parsed_rows, workbook_issues = parser(canonical_path)
        summary = summarize_rows(db, parsed_rows)
        result = ingest_rows(
            db,
            source_document,
            parsed_rows,
            workbook_issues,
            parser_name,
            parser_version,
            product_id,
            auto_create_missing_policies,
        )
        db.commit()
        return {
            "source_key": source_key,
            "product_branch": branch,
            "workbook_issues": workbook_issues,
            "run": result,
            **summary,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def refresh_and_sync_canonical_renewals(
    source_key: str,
    *,
    auto_create_missing_policies: bool = True,
) -> dict:
    """Download the current Drive workbook, validate it, then reconcile SQL."""
    spec = SUPPORTED_SOURCES.get(source_key)
    canonical_path = LOCAL_CANONICAL_PATHS.get(source_key)
    config = GOOGLE_DRIVE_SOURCE_FOLDERS.get(source_key) or {}
    file_id = config.get("file_id")
    if not spec or not canonical_path:
        raise ValueError(f"No canonical renewal parser is configured for {source_key}")
    if not file_id:
        raise ValueError(f"Missing canonical Drive file ID for {source_key}")

    canonical_path = Path(canonical_path)
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    parser = spec[0]
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{canonical_path.stem}-refresh-",
            suffix=canonical_path.suffix or ".xlsx",
            dir=canonical_path.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        download_drive_file(build_drive_service(), file_id, temporary_path)
        # Preserve the installed workbook when the downloaded source is invalid.
        parser(temporary_path)
        temporary_path.replace(canonical_path)
        temporary_path = None
        return sync_local_canonical_renewals(
            source_key,
            auto_create_missing_policies=auto_create_missing_policies,
        )
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


@router.post("/canonical/run")
async def run_canonical_renewal_ingestion(request: CanonicalRenewalIngestionRequest):
    spec = SUPPORTED_SOURCES.get(request.source_key)
    if not spec:
        raise HTTPException(status_code=400, detail=f"No canonical renewal parser is configured for {request.source_key}")
    config = GOOGLE_DRIVE_SOURCE_FOLDERS.get(request.source_key) or {}
    file_id = config.get("file_id")
    if not file_id:
        raise HTTPException(status_code=400, detail=f"Missing canonical Drive file ID for {request.source_key}")

    parser, parser_name, parser_version, branch, product_id = spec
    db = SessionLocal()
    temp_path = None
    try:
        source_document = db.query(SourceDocument).filter(SourceDocument.google_drive_file_id == file_id).first()
        if not source_document:
            raise HTTPException(status_code=404, detail="Canonical source must be registered before ingestion")
        with tempfile.NamedTemporaryFile(prefix="taiico-renewal-", suffix=".xlsx", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        download_drive_file(build_drive_service(), file_id, temp_path)
        parsed_rows, workbook_issues = parser(temp_path)
        summary = summarize_rows(db, parsed_rows)
        if request.dry_run:
            return {
                "dry_run": True,
                "source_key": request.source_key,
                "file_id": file_id,
                "parser_name": parser_name,
                "parser_version": parser_version,
                "product_branch": branch,
                "workbook_issues": workbook_issues,
                **summary,
            }

        result = ingest_rows(
            db,
            source_document,
            parsed_rows,
            workbook_issues,
            parser_name,
            parser_version,
            product_id,
            request.auto_create_missing_policies,
        )
        db.commit()
        return {"dry_run": False, "source_key": request.source_key, "run": result, **summary}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        db.close()
        if temp_path:
            temp_path.unlink(missing_ok=True)
