from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Union
from datetime import datetime, timedelta
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from decimal import Decimal
from database import SessionLocal, Renewal, Policy, Client, Product, User, PolicyDocumentRetrievalTask
from config import METLIFE_PATHS
from parsers.metlife_gmm_renovaciones import PARSER_VERSION as METLIFE_GMM_RENEWAL_PARSER_VERSION
from parsers.metlife_gmm_renovaciones import parse_metlife_gmm_renewal_workbook
from parsers.metlife_vida_renovaciones import PARSER_VERSION as METLIFE_VIDA_RENEWAL_PARSER_VERSION
from parsers.metlife_vida_renovaciones import parse_metlife_vida_renewal_workbook

router = APIRouter(prefix="/renovaciones", tags=["renovaciones"])

def format_date(d):
    if d is None:
        return None
    return d.strftime("%Y-%m-%d")

def json_ready(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    return value

def normalize_name(value: str) -> str:
    if not value:
        return ""
    return " ".join(str(value).strip().upper().split())

def parse_window(start_date: Optional[str], end_date: Optional[str], days: Optional[int]):
    today = datetime.now().date()
    if start_date:
        window_start = datetime.strptime(start_date, "%Y-%m-%d").date()
    else:
        window_start = today

    if end_date:
        window_end = datetime.strptime(end_date, "%Y-%m-%d").date()
    elif days is not None:
        window_end = window_start + timedelta(days=days)
    else:
        window_end = window_start + timedelta(days=90)

    return today, window_start, window_end

def retrieval_priority(risk_level: str, days_until_renewal: Optional[int]) -> str:
    if risk_level in {"overdue", "high"}:
        return "urgent"
    if risk_level == "medium":
        return "high"
    if risk_level == "low":
        return "medium"
    if days_until_renewal is not None and days_until_renewal <= 120:
        return "low"
    return "low"

def serialize_retrieval_task(task: PolicyDocumentRetrievalTask) -> dict:
    return {
        "id": task.id,
        "insurer_id": task.insurer_id,
        "product_branch": task.product_branch,
        "policy_number": task.policy_number,
        "original_policy_number": task.original_policy_number,
        "client_name": task.client_name,
        "rfc": task.rfc,
        "renewal_deadline": format_date(task.renewal_deadline),
        "days_until_renewal": task.days_until_renewal,
        "risk_level": task.risk_level,
        "priority": task.priority,
        "status": task.status,
        "document_status": task.document_status,
        "expediente_link": task.expediente_link,
        "target_drive_folder_id": task.target_drive_folder_id,
        "target_drive_folder_path": task.target_drive_folder_path,
        "source_name": task.source_name,
        "source_path": task.source_path,
        "source_sheet_name": task.source_sheet_name,
        "source_row_number": task.source_row_number,
        "source_row_hash": task.source_row_hash,
        "retrieval_adapter": task.retrieval_adapter,
        "attempt_count": task.attempt_count,
        "last_attempt_at": task.last_attempt_at.isoformat() if task.last_attempt_at else None,
        "last_error": task.last_error,
        "queued_at": task.queued_at.isoformat() if task.queued_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "normalized_payload": task.normalized_payload,
    }

def metlife_gmm_retrieval_queue_candidates(
    source_path: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    days: Optional[int],
):
    workbook_path = Path(source_path) if source_path else Path(METLIFE_PATHS["RENOVACIONES_GMM"])
    if not workbook_path.exists():
        raise HTTPException(status_code=404, detail=f"MetLife GMM renewal source file not found: {workbook_path}")

    today, window_start, window_end = parse_window(start_date, end_date, days)
    parsed_rows, workbook_issues = parse_metlife_gmm_renewal_workbook(workbook_path, today=today)

    candidates = []
    row_issue_count = 0
    skipped_with_document = 0
    skipped_outside_window = 0

    for row in parsed_rows:
        row_issue_count += len(row.issues)
        payload = row.normalized_payload
        renewal_deadline = payload.get("renewal_deadline")
        in_window = bool(renewal_deadline and window_start <= renewal_deadline <= window_end)
        if not in_window:
            skipped_outside_window += 1
            continue
        if not payload.get("needs_document_retrieval"):
            skipped_with_document += 1
            continue
        if not payload.get("policy_number") or not renewal_deadline:
            continue

        risk_level = payload.get("risk_level") or "unknown"
        task_payload = {
            "insurer_id": payload.get("insurer_id"),
            "product_branch": payload.get("product_branch"),
            "policy_number": payload.get("policy_number"),
            "original_policy_number": payload.get("original_policy_number"),
            "client_name": payload.get("client_name"),
            "rfc": payload.get("rfc"),
            "renewal_deadline": renewal_deadline,
            "days_until_renewal": payload.get("days_until_renewal"),
            "risk_level": risk_level,
            "priority": retrieval_priority(risk_level, payload.get("days_until_renewal")),
            "document_status": payload.get("document_status") or "missing",
            "expediente_link": payload.get("expediente_link"),
            "source_name": "metlife_gmm_renewal_workbook",
            "source_path": str(workbook_path),
            "source_sheet_name": row.sheet_name,
            "source_row_number": row.row_number,
            "source_row_hash": row.row_hash,
            "source_payload": json_ready(row.source_payload),
            "normalized_payload": json_ready(payload),
        }
        candidates.append({
            "task_payload": task_payload,
            "issues": row.issues,
        })

    candidates.sort(key=lambda item: (
        item["task_payload"].get("renewal_deadline") or "9999-12-31",
        {"urgent": 0, "high": 1, "medium": 2, "low": 3}.get(item["task_payload"].get("priority"), 9),
        item["task_payload"].get("policy_number") or "",
    ))

    return {
        "source_path": str(workbook_path),
        "rows_read": len(parsed_rows),
        "window_start": window_start,
        "window_end": window_end,
        "workbook_issues": workbook_issues,
        "row_issues_count": row_issue_count,
        "skipped_with_document": skipped_with_document,
        "skipped_outside_window": skipped_outside_window,
        "candidates": candidates,
    }

def upsert_retrieval_task(db, payload: dict) -> tuple[PolicyDocumentRetrievalTask, bool]:
    existing = db.query(PolicyDocumentRetrievalTask).filter(
        PolicyDocumentRetrievalTask.insurer_id == payload["insurer_id"],
        PolicyDocumentRetrievalTask.product_branch == payload["product_branch"],
        PolicyDocumentRetrievalTask.policy_number == payload["policy_number"],
        PolicyDocumentRetrievalTask.renewal_deadline == payload["renewal_deadline"],
    ).first()

    if existing:
        for field in [
            "original_policy_number",
            "client_name",
            "rfc",
            "days_until_renewal",
            "risk_level",
            "priority",
            "document_status",
            "expediente_link",
            "source_path",
            "source_sheet_name",
            "source_row_number",
            "source_row_hash",
            "source_payload",
            "normalized_payload",
        ]:
            setattr(existing, field, payload.get(field))
        existing.updated_at = datetime.utcnow()
        return existing, False

    task = PolicyDocumentRetrievalTask(
        **payload,
        status="queued",
        retrieval_adapter="metlife_portal_adapter_pending",
    )
    db.add(task)
    return task, True

def send_email_smtp(subject: str, body: str, recipients: List[str], attachments: List[dict] = []):
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("SMTP_SENDER", user)
    use_starttls = os.environ.get("SMTP_USE_STARTTLS", "true").lower() in {"1", "true", "yes"}

    if not all([host, user, password, sender]):
        raise RuntimeError("Missing SMTP configuration")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    for att in attachments:
        name = att.get("name")
        content = att.get("content")
        if name and content:
            message.add_attachment(
                content,
                maintype="application",
                subtype="octet-stream",
                filename=name,
            )

    with smtplib.SMTP(host, port) as server:
        if use_starttls:
            server.starttls()
        server.login(user, password)
        server.send_message(message)

@router.post("/metlife/gmm/source-dry-run")
async def dry_run_metlife_gmm_renewal_source(
    source_path: Optional[str] = Body(None, embed=True),
    start_date: Optional[str] = Body(None, embed=True),
    end_date: Optional[str] = Body(None, embed=True),
    days: Optional[int] = Body(None, embed=True),
    include_all: bool = Body(False, embed=True),
    limit: int = Body(25, embed=True),
):
    workbook_path = Path(source_path) if source_path else Path(METLIFE_PATHS["RENOVACIONES_GMM"])
    if not workbook_path.exists():
        raise HTTPException(status_code=404, detail=f"MetLife GMM renewal source file not found: {workbook_path}")

    today = datetime.now().date()
    if start_date:
        window_start = datetime.strptime(start_date, "%Y-%m-%d").date()
    else:
        window_start = today

    if end_date:
        window_end = datetime.strptime(end_date, "%Y-%m-%d").date()
    elif days is not None:
        window_end = window_start + timedelta(days=days)
    else:
        window_end = window_start + timedelta(days=90)

    parsed_rows, workbook_issues = parse_metlife_gmm_renewal_workbook(workbook_path, today=today)

    candidates = []
    row_issue_count = 0
    status_counts = {}
    risk_counts = {}
    document_counts = {}
    rows_missing_documents = 0

    for row in parsed_rows:
        row_issue_count += len(row.issues)
        payload = row.normalized_payload
        renewal_deadline = payload.get("renewal_deadline")
        in_window = bool(renewal_deadline and window_start <= renewal_deadline <= window_end)
        if not include_all and not in_window:
            continue

        status = payload.get("renewal_status_source") or "UNKNOWN"
        risk = payload.get("risk_level") or "unknown"
        document_status = payload.get("document_status") or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
        document_counts[document_status] = document_counts.get(document_status, 0) + 1
        if payload.get("needs_document_retrieval"):
            rows_missing_documents += 1

        candidates.append({
            "sheet_name": row.sheet_name,
            "row_number": row.row_number,
            "row_hash": row.row_hash,
            "normalized_payload": json_ready(payload),
            "issues": row.issues,
        })

    candidates.sort(key=lambda item: (
        item["normalized_payload"].get("renewal_deadline") or "9999-12-31",
        item["normalized_payload"].get("policy_number") or "",
    ))

    return {
        "dry_run": True,
        "source_path": str(workbook_path),
        "parser_name": "metlife_gmm_renewal_workbook",
        "parser_version": METLIFE_GMM_RENEWAL_PARSER_VERSION,
        "rows_read": len(parsed_rows),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "candidate_count": len(candidates),
        "status_counts": status_counts,
        "risk_counts": risk_counts,
        "document_counts": document_counts,
        "rows_missing_documents": rows_missing_documents,
        "workbook_issues": workbook_issues,
        "row_issues_count": row_issue_count,
        "sample_candidates": candidates[: max(0, min(limit, 100))],
    }

@router.post("/metlife/vida/source-dry-run")
async def dry_run_metlife_vida_renewal_source(
    source_path: Optional[str] = Body(None, embed=True),
    start_date: Optional[str] = Body(None, embed=True),
    end_date: Optional[str] = Body(None, embed=True),
    days: Optional[int] = Body(None, embed=True),
    include_all: bool = Body(False, embed=True),
    limit: int = Body(25, embed=True),
):
    workbook_path = Path(source_path) if source_path else Path(METLIFE_PATHS["RENOVACIONES_VIDA"])
    if not workbook_path.exists():
        raise HTTPException(status_code=404, detail=f"MetLife Vida renewal source file not found: {workbook_path}")

    today = datetime.now().date()
    if start_date:
        window_start = datetime.strptime(start_date, "%Y-%m-%d").date()
    else:
        window_start = today

    if end_date:
        window_end = datetime.strptime(end_date, "%Y-%m-%d").date()
    elif days is not None:
        window_end = window_start + timedelta(days=days)
    else:
        window_end = window_start + timedelta(days=90)

    parsed_rows, workbook_issues = parse_metlife_vida_renewal_workbook(workbook_path, today=today)

    candidates = []
    row_issue_count = 0
    status_counts = {}
    risk_counts = {}
    document_counts = {}
    rows_missing_documents = 0

    for row in parsed_rows:
        row_issue_count += len(row.issues)
        payload = row.normalized_payload
        renewal_deadline = payload.get("renewal_deadline")
        in_window = bool(renewal_deadline and window_start <= renewal_deadline <= window_end)
        if not include_all and not in_window:
            continue

        status = payload.get("renewal_status_source") or "UNKNOWN"
        risk = payload.get("risk_level") or "unknown"
        document_status = payload.get("document_status") or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
        document_counts[document_status] = document_counts.get(document_status, 0) + 1
        if payload.get("needs_document_retrieval"):
            rows_missing_documents += 1

        candidates.append({
            "sheet_name": row.sheet_name,
            "row_number": row.row_number,
            "row_hash": row.row_hash,
            "normalized_payload": json_ready(payload),
            "issues": row.issues,
        })

    candidates.sort(key=lambda item: (
        item["normalized_payload"].get("renewal_deadline") or "9999-12-31",
        item["normalized_payload"].get("policy_number") or "",
    ))

    return {
        "dry_run": True,
        "source_path": str(workbook_path),
        "parser_name": "metlife_vida_renewal_workbook",
        "parser_version": METLIFE_VIDA_RENEWAL_PARSER_VERSION,
        "rows_read": len(parsed_rows),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "candidate_count": len(candidates),
        "status_counts": status_counts,
        "risk_counts": risk_counts,
        "document_counts": document_counts,
        "rows_missing_documents": rows_missing_documents,
        "workbook_issues": workbook_issues,
        "row_issues_count": row_issue_count,
        "sample_candidates": candidates[: max(0, min(limit, 100))],
    }

@router.post("/metlife/gmm/retrieval-queue/preview")
async def preview_metlife_gmm_retrieval_queue(
    source_path: Optional[str] = Body(None, embed=True),
    start_date: Optional[str] = Body(None, embed=True),
    end_date: Optional[str] = Body(None, embed=True),
    days: Optional[int] = Body(None, embed=True),
    limit: int = Body(25, embed=True),
):
    queue = metlife_gmm_retrieval_queue_candidates(source_path, start_date, end_date, days)
    sample = [
        {
            **json_ready(item["task_payload"]),
            "issues": item["issues"],
        }
        for item in queue["candidates"][: max(0, min(limit, 100))]
    ]

    priority_counts = {}
    risk_counts = {}
    for item in queue["candidates"]:
        payload = item["task_payload"]
        priority = payload.get("priority") or "unknown"
        risk = payload.get("risk_level") or "unknown"
        priority_counts[priority] = priority_counts.get(priority, 0) + 1
        risk_counts[risk] = risk_counts.get(risk, 0) + 1

    return {
        "dry_run": True,
        "source_path": queue["source_path"],
        "parser_name": "metlife_gmm_renewal_workbook",
        "parser_version": METLIFE_GMM_RENEWAL_PARSER_VERSION,
        "rows_read": queue["rows_read"],
        "window_start": queue["window_start"].isoformat(),
        "window_end": queue["window_end"].isoformat(),
        "candidate_count": len(queue["candidates"]),
        "priority_counts": priority_counts,
        "risk_counts": risk_counts,
        "skipped_with_document": queue["skipped_with_document"],
        "skipped_outside_window": queue["skipped_outside_window"],
        "workbook_issues": queue["workbook_issues"],
        "row_issues_count": queue["row_issues_count"],
        "sample_tasks": sample,
    }

@router.post("/metlife/gmm/retrieval-queue/build")
async def build_metlife_gmm_retrieval_queue(
    source_path: Optional[str] = Body(None, embed=True),
    start_date: Optional[str] = Body(None, embed=True),
    end_date: Optional[str] = Body(None, embed=True),
    days: Optional[int] = Body(None, embed=True),
    limit: int = Body(25, embed=True),
):
    queue = metlife_gmm_retrieval_queue_candidates(source_path, start_date, end_date, days)
    db = SessionLocal()
    try:
        created = 0
        updated = 0
        tasks = []
        for item in queue["candidates"]:
            task, was_created = upsert_retrieval_task(db, item["task_payload"])
            if was_created:
                created += 1
            else:
                updated += 1
            tasks.append(task)
        db.commit()

        for task in tasks:
            db.refresh(task)

        priority_counts = {}
        risk_counts = {}
        for task in tasks:
            priority_counts[task.priority] = priority_counts.get(task.priority, 0) + 1
            risk_counts[task.risk_level] = risk_counts.get(task.risk_level, 0) + 1

        return {
            "created": created,
            "updated": updated,
            "total_queued": len(tasks),
            "source_path": queue["source_path"],
            "window_start": queue["window_start"].isoformat(),
            "window_end": queue["window_end"].isoformat(),
            "priority_counts": priority_counts,
            "risk_counts": risk_counts,
            "skipped_with_document": queue["skipped_with_document"],
            "skipped_outside_window": queue["skipped_outside_window"],
            "workbook_issues": queue["workbook_issues"],
            "row_issues_count": queue["row_issues_count"],
            "sample_tasks": [serialize_retrieval_task(task) for task in tasks[: max(0, min(limit, 100))]],
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to build MetLife GMM retrieval queue: {e}")
    finally:
        db.close()

@router.get("/retrieval-queue")
async def list_policy_document_retrieval_queue(
    status: Optional[str] = Query("queued"),
    insurer_id: Optional[str] = Query(None),
    product_branch: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    db = SessionLocal()
    try:
        query = db.query(PolicyDocumentRetrievalTask)
        if status:
            query = query.filter(PolicyDocumentRetrievalTask.status == status)
        if insurer_id:
            query = query.filter(PolicyDocumentRetrievalTask.insurer_id == insurer_id)
        if product_branch:
            query = query.filter(PolicyDocumentRetrievalTask.product_branch == product_branch)

        tasks = query.order_by(
            PolicyDocumentRetrievalTask.renewal_deadline.asc(),
            PolicyDocumentRetrievalTask.priority.asc(),
            PolicyDocumentRetrievalTask.policy_number.asc(),
        ).limit(limit).all()

        return {
            "count": len(tasks),
            "tasks": [serialize_retrieval_task(task) for task in tasks],
        }
    finally:
        db.close()

@router.get("/upcoming")
async def get_upcoming_renewals(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    days: Optional[int] = Query(30, description="Days to look ahead"),
    insurer: str = Query("Metlife", description="Insurer name"),
    type: str = Query("ALL", description="Policy type: ALL, VIDA, GMM")
):
    db = SessionLocal()
    try:
        results = []
        
        # Build base date range
        today = datetime.now().date()
        if start_date and end_date:
            try:
                sd = datetime.strptime(start_date, "%Y-%m-%d").date()
                ed = datetime.strptime(end_date, "%Y-%m-%d").date()
            except:
                sd = today
                ed = today + timedelta(days=days or 30)
        else:
            sd = today
            ed = today + timedelta(days=days or 30)
            
        # Base query joining Policy, Client, and Product
        query = db.query(Renewal).join(Policy, Renewal.original_policy_id == Policy.id).join(Client).join(Product)
        
        # Filter by date range
        query = query.filter(Renewal.renewal_deadline >= sd).filter(Renewal.renewal_deadline <= ed)
        
        # Filter by Insurer
        if insurer.lower() == "metlife":
            query = query.filter(Policy.insurer_id == "metlife")
            if type.upper() == "VIDA":
                query = query.filter(Policy.product_id == "prod_met_vida")
            elif type.upper() == "GMM":
                query = query.filter(Policy.product_id == "prod_met_gmm")
                
            renewals = query.all()
            
            for ren in renewals:
                pol = ren.original_policy
                if pol.product_id == "prod_met_vida":
                    results.append({
                        "POLIZA_ACTUAL": pol.policy_number,
                        "CONTRATANTE": pol.client.full_name if pol.client else "",
                        "INI_VIG": format_date(pol.effective_start_date),
                        "FIN_VIG": format_date(ren.renewal_deadline),
                        "FORMA_PAGO": pol.payment_frequency.upper(),
                        "CONDUCTO_COBRO": "Conducto de Cobro",
                        "AGENTE": "Pamela Asmara",
                        "PRIMA_ANUAL": float(pol.premium_amount) if pol.premium_amount else 0.0,
                        "PRIMA_MODAL": float(pol.premium_amount / 12) if pol.premium_amount else 0.0,
                        "PAGADO_HASTA": format_date(pol.effective_end_date),
                        "ESTATUS_DE_RENOVACION": ren.insurer_response,
                        "EXPEDIENTE": pol.document_link,
                        "Email": pol.client.email if pol.client else None
                    })
                else:
                    results.append({
                        "NPOLIZA": pol.policy_number,
                        "POLORIG": pol.policy_number,
                        "CONTRATANTE": pol.client.full_name if pol.client else "",
                        "FFINVIG": format_date(ren.renewal_deadline),
                        "PRIMA.1": float(pol.premium_amount) if pol.premium_amount else 0.0,
                        "IVA": float(pol.premium_amount) * 0.16 if pol.premium_amount else 0.0,
                        "NOMBREL": pol.client.full_name if pol.client else "",
                        "DEDUCIBLE": 0.0,
                        "PAGADOHASTA": format_date(pol.effective_end_date),
                        "COASEGURO": 0.0,
                        "ESTATUS_DE_RENOVACION": ren.insurer_response,
                        "EXPEDIENTE": pol.document_link,
                        "Email": pol.client.email if pol.client else None
                    })
                    
        elif insurer.lower() == "sura" or insurer == "Promotoria SURA":
            query = query.filter(Policy.insurer_id == "sura")
            renewals = query.all()
            
            for ren in renewals:
                pol = ren.original_policy
                prospectador = pol.client.metadata_json.get("prospectador", "") if pol.client else ""
                
                if insurer == "Promotoria SURA":
                    results.append({
                        "PÓLIZA": pol.policy_number,
                        "OFICINA": "SURA",
                        "RAMO": pol.product.branch if pol.product else "GMM",
                        "INICIO VIGENCIA": format_date(pol.effective_start_date),
                        "FIN VIGENCIA": format_date(ren.renewal_deadline),
                        "CONTRATANTE": pol.client.full_name if pol.client else "",
                        "PRIMA ANUALIZADA": float(pol.premium_amount) if pol.premium_amount else 0.0,
                        "AGENTE": "SURA Agent",
                        "NOMBRE RAMO": pol.product.name if pol.product else "GMM Product",
                        "PROCEDENCIA": "Promotoría",
                        "Poliza anterior": pol.policy_number,
                        "Llave Póliza": pol.policy_number,
                        "ESTATUS_DE_RENOVACION": ren.insurer_response,
                        "EXPEDIENTE": pol.document_link,
                        "Email": pol.client.email if pol.client else None,
                        "PROMOTOR": "SURA Promotor"
                    })
                else:
                    results.append({
                        "POLIZA": pol.policy_number,
                        "NOMBRE": pol.client.full_name if pol.client else "",
                        "INICIO VIGENCIA": format_date(pol.effective_start_date),
                        "FIN VIGENCIA": format_date(ren.renewal_deadline),
                        "RAMO": pol.product.branch if pol.product else "GMM",
                        "PRIMA": float(pol.premium_amount) if pol.premium_amount else 0.0,
                        "PERIODICIDAD_PAGO": pol.payment_frequency,
                        "PROSPECTADOR": prospectador,
                        "ESTATUS_DE_RENOVACION": ren.insurer_response,
                        "EXPEDIENTE": pol.document_link,
                        "Email": pol.client.email if pol.client else None
                    })
                    
        elif insurer.upper() in ["AARCO_AXA", "AARCO"]:
            query = query.filter(Policy.insurer_id == "aarco")
            renewals = query.all()
            
            for ren in renewals:
                pol = ren.original_policy
                prospectador = pol.client.metadata_json.get("prospectador", "") if pol.client else ""
                results.append({
                    "POLIZA": pol.policy_number,
                    "ASEGURADORA": "AARCO",
                    "PROMOTORIA": "AARCO Promotoria",
                    "AGENTE": "Aarco Agente",
                    "PROSPECTADOR": prospectador,
                    "RAMO": pol.product.branch if pol.product else "VIDA",
                    "PRODUCTO": pol.product.name if pol.product else "Vida Individual",
                    "CONTRATANTE": pol.client.full_name if pol.client else "",
                    "ASEGURADO": pol.client.full_name if pol.client else "",
                    "INICIO VIGENCIA": format_date(pol.effective_start_date),
                    "FIN VIGENCIA": format_date(ren.renewal_deadline),
                    "PRIMA NETA ANUAL": float(pol.premium_amount) if pol.premium_amount else 0.0,
                    "ESTATUS_DE_RENOVACION": ren.insurer_response,
                    "EXPEDIENTE": pol.document_link,
                    "Email": pol.client.email if pol.client else None
                })
                
        return results
    except Exception as e:
        print(f"Error fetching upcoming renewals: {e}")
        return []
    finally:
        db.close()

@router.post("/update")
async def update_renewal_status(
    insurer: str = Body(..., embed=True),
    type: str = Body(..., embed=True),
    policy_number: Union[str, int] = Body(..., embed=True),
    new_status: Optional[str] = Body(None, embed=True),
    expediente: Optional[str] = Body(None, embed=True),
    email: Optional[str] = Body(None, embed=True)
):
    """
    Update the ESTATUS_DE_RENOVACION, EXPEDIENTE, and EMAIL in the SQL database.
    """
    db = SessionLocal()
    try:
        policy_str = str(policy_number).strip().split('.')[0]
        policy = db.query(Policy).filter(Policy.policy_number == policy_str).first()
        
        if not policy:
            raise HTTPException(status_code=404, detail=f"Policy {policy_number} not found")
            
        # Retrieve related renewal
        renewal = db.query(Renewal).filter(Renewal.original_policy_id == policy.id).first()
        if not renewal:
            # Fallback create renewal if missing
            renewal = Renewal(
                original_policy_id=policy.id,
                client_id=policy.client_id,
                renewal_deadline=policy.effective_end_date,
                status="in_progress"
            )
            db.add(renewal)
            db.flush()
            
        if new_status is not None:
            renewal.insurer_response = new_status
            
        if expediente is not None:
            policy.document_link = expediente
            
        if email is not None and policy.client:
            policy.client.email = email
            
        db.commit()
        return {"message": "Policy and renewal updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating renewal: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/vida")
async def get_renovaciones_vida(days: int = 30):
    return await get_upcoming_renewals(days=days, insurer="Metlife", type="VIDA")

@router.post("/send-email")
async def send_renewal_email_endpoint(
    insurer: str = Body(..., embed=True),
    type: str = Body(..., embed=True),
    policy_number: Union[str, int] = Body(..., embed=True),
    client_name: str = Body(..., embed=True),
    end_date: str = Body(..., embed=True),
    expediente: Optional[str] = Body(None, embed=True)
):
    """
    Send renewal email using database details. Updates status in database upon success.
    """
    db = SessionLocal()
    try:
        policy_str = str(policy_number).strip().split('.')[0]
        policy = db.query(Policy).filter(Policy.policy_number == policy_str).first()
        
        if not policy or not policy.client:
            raise HTTPException(status_code=404, detail="Policy or client profile not found")
            
        recipient_email = policy.client.email
        if not recipient_email:
            raise HTTPException(
                status_code=404, 
                detail=f"No email registered for client {client_name}. Please update in the client card first."
            )
            
        # Build SMTP elements
        subject = f"Renovacion {policy_str} {policy.client.full_name}"
        body = (
            f"Buen día,\n"
            f"Comparto póliza {policy_str} con fecha Fin de Vigencia {end_date}.\n\n"
            f"La renovacion se encuentra adjunta en el correo o disponible en el sistema.\n"
            f"Nos mantenemos en contacto para cualquier duda\n\n"
            f"Atentamente Taiico Life Advisors"
        )
        
        # Read attachments if local folder exists
        attachments = []
        if expediente:
            exp_path = expediente.strip().strip("'").strip('"')
            if os.path.exists(exp_path):
                if os.path.isdir(exp_path):
                    for filename in os.listdir(exp_path):
                        file_path = os.path.join(exp_path, filename)
                        if os.path.isfile(file_path) and not filename.startswith('.'):
                            with open(file_path, "rb") as f:
                                attachments.append({
                                    "name": filename,
                                    "content": f.read()
                                })
                elif os.path.isfile(exp_path):
                    with open(exp_path, "rb") as f:
                        attachments.append({
                            "name": os.path.basename(exp_path),
                            "content": f.read()
                        })
            elif exp_path.startswith("http"):
                body += f"\n\nLink al expediente: {exp_path}"
                
        # Send Email
        recipients = [r.strip() for r in recipient_email.split(",") if r.strip()]
        send_email_smtp(subject, body, recipients, attachments)
        
        # Update database status
        renewal = db.query(Renewal).filter(Renewal.original_policy_id == policy.id).first()
        if renewal:
            renewal.insurer_response = "Enviado"
            db.commit()
            
        return {"message": f"Correo enviado a {recipient_email}"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error sending email: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al enviar correo: {str(e)}")
    finally:
        db.close()
