from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Body, Depends
from starlette.concurrency import run_in_threadpool
from typing import List, Optional, Union
from datetime import datetime, timedelta
import io
import mimetypes
import os
import re
import smtplib
from functools import lru_cache
from email.message import EmailMessage
from pathlib import Path
from decimal import Decimal
from urllib.parse import parse_qs, urlparse
from googleapiclient.http import MediaIoBaseDownload
from database import (
    SessionLocal,
    Renewal,
    Policy,
    Client,
    Product,
    User,
    PolicyDocumentRetrievalTask,
    PolicyDocumentRetrievalRun,
    PolicyDocumentRetrievalStep,
)
from config import METLIFE_PATHS
from parsers.metlife_gmm_renovaciones import PARSER_VERSION as METLIFE_GMM_RENEWAL_PARSER_VERSION
from parsers.metlife_gmm_renovaciones import parse_metlife_gmm_renewal_workbook
from parsers.metlife_vida_renovaciones import PARSER_VERSION as METLIFE_VIDA_RENEWAL_PARSER_VERSION
from parsers.metlife_vida_renovaciones import parse_metlife_vida_renewal_workbook
from adapters.metlife_gmm_portal import MetLifeGmmPortalAdapter, MetLifeGmmPortalTask, result_to_dict, stable_chrome_profile_dir
from services.mail_configuration import smtp_settings_for, smtp_ssl_context
from services.metlife_agent_directory import normalize_agent_key, promotoria_by_agent_key
from services.session_auth import current_username
from drive.client import build_drive_service

router = APIRouter(prefix="/renovaciones", tags=["renovaciones"])

DRIVE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
DRIVE_SHORTCUT_MIME_TYPE = "application/vnd.google-apps.shortcut"
DEFAULT_MAX_RENEWAL_ATTACHMENT_BYTES = 18 * 1024 * 1024
DEFAULT_MAX_RENEWAL_ATTACHMENT_COUNT = 100
DEFAULT_RENEWAL_EMAIL_CC_RECIPIENTS = (
    "alberto.alfaro@taiico.com",
    "veronica.alfaro@taiico.com",
    "pamela.alfaro@taiico.com",
)
GOOGLE_NATIVE_EXPORTS = {
    "application/vnd.google-apps.document": ("application/pdf", ".pdf"),
    "application/vnd.google-apps.spreadsheet": (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xlsx",
    ),
    "application/vnd.google-apps.presentation": (
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".pptx",
    ),
    "application/vnd.google-apps.drawing": ("application/pdf", ".pdf"),
}


class DriveAttachmentError(ValueError):
    pass


class SmtpDeliveryUncertainError(RuntimeError):
    pass

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


@lru_cache(maxsize=4)
def _cached_metlife_gmm_agents(
    workbook_path: str,
    modified_time_ns: int,
    size: int,
) -> dict[tuple[str, str], dict[str, str]]:
    """Index agent fields from the current canonical workbook version."""
    del modified_time_ns, size  # Values intentionally participate in the cache key.
    parsed_rows, _issues = parse_metlife_gmm_renewal_workbook(Path(workbook_path))
    indexed: dict[tuple[str, str], dict[str, str]] = {}
    for row in parsed_rows:
        payload = row.normalized_payload
        policy_number = str(payload.get("policy_number") or "").strip()
        if not policy_number:
            continue
        renewal_deadline = payload.get("renewal_deadline")
        deadline_key = renewal_deadline.isoformat() if renewal_deadline else ""
        agent = {
            "AGENTE": str(payload.get("agent_code") or ""),
            "NOMBRE": str(payload.get("agent_name") or ""),
        }
        indexed[(policy_number, deadline_key)] = agent
        indexed[(policy_number, "")] = agent
    return indexed


def metlife_gmm_agents() -> dict[tuple[str, str], dict[str, str]]:
    workbook_path = Path(METLIFE_PATHS["RENOVACIONES_GMM"])
    stat = workbook_path.stat()
    return _cached_metlife_gmm_agents(
        str(workbook_path),
        stat.st_mtime_ns,
        stat.st_size,
    )


@lru_cache(maxsize=4)
def _cached_metlife_vida_agents(
    workbook_path: str,
    modified_time_ns: int,
    size: int,
) -> dict[tuple[str, str], dict[str, str]]:
    """Index Vida agent fields from the current canonical workbook version."""
    del modified_time_ns, size
    parsed_rows, _issues = parse_metlife_vida_renewal_workbook(Path(workbook_path))
    indexed: dict[tuple[str, str], dict[str, str]] = {}
    for row in parsed_rows:
        payload = row.normalized_payload
        policy_number = str(payload.get("policy_number") or "").strip()
        if not policy_number:
            continue
        renewal_deadline = payload.get("renewal_deadline")
        deadline_key = renewal_deadline.isoformat() if renewal_deadline else ""
        agent = {
            "AGENTE": str(payload.get("agent_code") or ""),
            "NOMBRE": str(payload.get("agent_name") or ""),
        }
        indexed[(policy_number, deadline_key)] = agent
        indexed[(policy_number, "")] = agent
    return indexed


def metlife_vida_agents() -> dict[tuple[str, str], dict[str, str]]:
    workbook_path = Path(METLIFE_PATHS["RENOVACIONES_VIDA"])
    stat = workbook_path.stat()
    return _cached_metlife_vida_agents(
        str(workbook_path),
        stat.st_mtime_ns,
        stat.st_size,
    )

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

def serialize_retrieval_run(run: PolicyDocumentRetrievalRun) -> dict:
    return {
        "id": run.id,
        "adapter_name": run.adapter_name,
        "insurer_id": run.insurer_id,
        "product_branch": run.product_branch,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "queued_at_start": run.queued_at_start,
        "selected_count": run.selected_count,
        "processed_count": run.processed_count,
        "succeeded_count": run.succeeded_count,
        "failed_count": run.failed_count,
        "escalated_count": run.escalated_count,
        "summary_email_to": run.summary_email_to,
        "metadata": run.metadata_json,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }

def serialize_retrieval_step(step: PolicyDocumentRetrievalStep) -> dict:
    return {
        "id": step.id,
        "run_id": step.run_id,
        "task_id": step.task_id,
        "step_name": step.step_name,
        "status": step.status,
        "started_at": step.started_at.isoformat() if step.started_at else None,
        "completed_at": step.completed_at.isoformat() if step.completed_at else None,
        "error_message": step.error_message,
        "metadata": step.metadata_json,
    }

def build_escalation_email_payload(
    task: PolicyDocumentRetrievalTask,
    failed_step: str,
    error_message: str,
    system_admin_email: str,
    run_id: Optional[str] = None,
) -> dict:
    subject = f"[Taiico OS] Renewal retrieval failed for policy {task.policy_number}"
    body = "\n".join([
        "A renewal document retrieval task failed and requires review.",
        "",
        f"Run ID: {run_id or 'dry-run'}",
        f"Task ID: {task.id}",
        f"Policy number: {task.policy_number}",
        f"Client: {task.client_name or 'Unknown'}",
        f"Insurer / branch: {task.insurer_id} / {task.product_branch}",
        f"Renewal deadline: {format_date(task.renewal_deadline)}",
        f"Risk level: {task.risk_level}",
        f"Priority: {task.priority}",
        f"Failed step: {failed_step}",
        f"Error: {error_message}",
        f"Attempt count: {task.attempt_count}",
        "",
        "Suggested action: review the portal manually, confirm the policy document location, and update the task.",
    ])
    return {
        "to": [system_admin_email],
        "subject": subject,
        "body": body,
    }

METLIFE_GMM_RETRIEVAL_STEPS = [
    "open_browser",
    "authenticate_portal",
    "search_policy",
    "confirm_policy_match",
    "download_policy_document",
    "validate_download",
    "upload_to_drive",
    "update_crm",
    "send_required_email",
]

def retrieval_step_plan(task: PolicyDocumentRetrievalTask) -> list[dict]:
    return [
        {
            "step_name": step_name,
            "status": "planned",
            "task_id": task.id,
            "policy_number": task.policy_number,
        }
        for step_name in METLIFE_GMM_RETRIEVAL_STEPS
    ]

def select_retrieval_tasks(db, insurer_id: str, product_branch: str, limit: int):
    tasks = db.query(PolicyDocumentRetrievalTask).filter(
        PolicyDocumentRetrievalTask.status == "queued",
        PolicyDocumentRetrievalTask.insurer_id == insurer_id,
        PolicyDocumentRetrievalTask.product_branch == product_branch,
    ).all()
    priority_rank = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(
        tasks,
        key=lambda task: (
            priority_rank.get(task.priority, 9),
            task.renewal_deadline,
            task.policy_number,
        ),
    )[:limit]

def get_retrieval_task_for_adapter(
    db,
    task_id: Optional[str] = None,
    policy_number: Optional[str] = None,
) -> PolicyDocumentRetrievalTask:
    query = db.query(PolicyDocumentRetrievalTask).filter(
        PolicyDocumentRetrievalTask.insurer_id == "metlife",
        PolicyDocumentRetrievalTask.product_branch == "GMM",
    )
    if task_id:
        query = query.filter(PolicyDocumentRetrievalTask.id == task_id)
    elif policy_number:
        query = query.filter(PolicyDocumentRetrievalTask.policy_number == str(policy_number))
    else:
        task = select_retrieval_tasks(db, "metlife", "GMM", 1)
        if not task:
            raise HTTPException(status_code=404, detail="No queued MetLife GMM retrieval task found")
        return task[0]

    task = query.first()
    if not task:
        raise HTTPException(status_code=404, detail="MetLife GMM retrieval task not found")
    return task

def persist_adapter_steps(db, run_id: str, task_id: str, steps: list[dict]) -> None:
    for step in steps:
        db.add(PolicyDocumentRetrievalStep(
            run_id=run_id,
            task_id=task_id,
            step_name=step.get("step_name"),
            status=step.get("status"),
            started_at=datetime.fromisoformat(step["started_at"]) if step.get("started_at") else datetime.utcnow(),
            completed_at=datetime.fromisoformat(step["completed_at"]) if step.get("completed_at") else None,
            error_message=step.get("error_message"),
            metadata_json=step.get("metadata") or {},
        ))

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

def drive_file_id_from_url(value: str) -> Optional[str]:
    """Return a Drive file/folder ID only for recognized Google Drive URLs."""
    text = str(value or "").strip().strip("'").strip('"')
    if not text:
        return None
    parsed = urlparse(text)
    hostname = (parsed.hostname or "").casefold()
    if hostname not in {"drive.google.com", "docs.google.com"}:
        return None

    query_id = parse_qs(parsed.query).get("id", [None])[0]
    if query_id and re.fullmatch(r"[A-Za-z0-9_-]+", query_id):
        return query_id

    match = re.search(r"/(?:drive/(?:u/\d+/)?folders|folders|file/d|document/d|spreadsheets/d|presentation/d)/([A-Za-z0-9_-]+)", parsed.path)
    return match.group(1) if match else None


def _download_drive_request(request) -> bytes:
    output = io.BytesIO()
    downloader = MediaIoBaseDownload(output, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return output.getvalue()


def _drive_attachment_content(service, item: dict) -> tuple[bytes, str, str]:
    file_id = item["id"]
    name = str(item.get("name") or file_id)
    mime_type = str(item.get("mimeType") or "application/octet-stream")
    if mime_type == DRIVE_SHORTCUT_MIME_TYPE:
        shortcut = item.get("shortcutDetails") or {}
        target_id = shortcut.get("targetId")
        if not target_id:
            raise DriveAttachmentError(f"El acceso directo {name} no tiene un destino válido")
        item = service.files().get(
            fileId=target_id,
            fields="id,name,mimeType,size,shortcutDetails(targetId,targetMimeType)",
            supportsAllDrives=True,
        ).execute()
        file_id = item["id"]
        mime_type = str(item.get("mimeType") or "application/octet-stream")

    export = GOOGLE_NATIVE_EXPORTS.get(mime_type)
    if mime_type.startswith("application/vnd.google-apps.") and not export:
        raise DriveAttachmentError(
            f"El archivo {name} usa un formato nativo de Google que no se puede adjuntar"
        )
    if export:
        exported_mime, extension = export
        if not name.casefold().endswith(extension):
            name = f"{name}{extension}"
        request = service.files().export_media(fileId=file_id, mimeType=exported_mime)
        return _download_drive_request(request), name, exported_mime

    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    return _download_drive_request(request), name, mime_type


def drive_folder_attachments(
    folder_url: str,
    service=None,
    max_bytes: Optional[int] = None,
    max_count: Optional[int] = None,
) -> List[dict]:
    folder_id = drive_file_id_from_url(folder_url)
    if not folder_id:
        raise DriveAttachmentError("El enlace del expediente no es una URL válida de Google Drive")

    max_bytes = max_bytes or int(os.getenv(
        "RENEWAL_EMAIL_MAX_ATTACHMENT_BYTES",
        str(DEFAULT_MAX_RENEWAL_ATTACHMENT_BYTES),
    ))
    max_count = max_count or int(os.getenv(
        "RENEWAL_EMAIL_MAX_ATTACHMENT_COUNT",
        str(DEFAULT_MAX_RENEWAL_ATTACHMENT_COUNT),
    ))
    service = service or build_drive_service()
    metadata = service.files().get(
        fileId=folder_id,
        fields="id,name,mimeType",
        supportsAllDrives=True,
    ).execute()
    if metadata.get("mimeType") != DRIVE_FOLDER_MIME_TYPE:
        raise DriveAttachmentError("El enlace del expediente debe apuntar a una carpeta de Drive")

    items: List[dict] = []
    page_token = None
    while True:
        response = service.files().list(
            q=f"'{folder_id}' in parents and trashed = false",
            fields="nextPageToken,files(id,name,mimeType,size,shortcutDetails(targetId,targetMimeType))",
            pageToken=page_token,
            pageSize=1000,
            orderBy="name",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        items.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    nested_folders = [item.get("name", "") for item in items if item.get("mimeType") == DRIVE_FOLDER_MIME_TYPE]
    files = [item for item in items if item.get("mimeType") != DRIVE_FOLDER_MIME_TYPE]
    if nested_folders:
        raise DriveAttachmentError(
            "El expediente contiene subcarpetas. Coloca los archivos directamente en la carpeta antes de enviar."
        )
    if not files:
        raise DriveAttachmentError("La carpeta del expediente no contiene archivos para adjuntar")
    if len(files) > max_count:
        raise DriveAttachmentError(
            f"El expediente contiene {len(files)} archivos; el máximo permitido es {max_count}"
        )

    known_bytes = sum(int(item.get("size") or 0) for item in files)
    if known_bytes > max_bytes:
        raise DriveAttachmentError(
            "Los archivos del expediente exceden el límite seguro de adjuntos del correo"
        )

    attachments = []
    total_bytes = 0
    for item in files:
        content, name, mime_type = _drive_attachment_content(service, item)
        total_bytes += len(content)
        if total_bytes > max_bytes:
            raise DriveAttachmentError(
                "Los archivos del expediente exceden el límite seguro de adjuntos del correo"
            )
        attachments.append({"name": name, "content": content, "mime_type": mime_type})
    return attachments


def renewal_email_cc_recipients(primary_recipients: List[str]) -> List[str]:
    configured = os.getenv("RENEWAL_EMAIL_CC_RECIPIENTS", "").strip()
    candidates = (
        [email.strip() for email in configured.split(",") if email.strip()]
        if configured
        else list(DEFAULT_RENEWAL_EMAIL_CC_RECIPIENTS)
    )
    primary = {email.strip().casefold() for email in primary_recipients if email.strip()}
    result = []
    seen = set(primary)
    for email in candidates:
        normalized = email.casefold()
        if normalized not in seen:
            result.append(email)
            seen.add(normalized)
    return result


def send_email_smtp(
    subject: str,
    body: str,
    recipients: List[str],
    attachments: Optional[List[dict]] = None,
    cc_recipients: Optional[List[str]] = None,
    settings: dict | None = None,
    html_body: str | None = None,
):
    settings = settings or {}
    host = settings.get("host") or os.environ.get("SMTP_HOST")
    port = int(settings.get("port") or os.environ.get("SMTP_PORT", "587"))
    user = settings.get("user") or os.environ.get("SMTP_USER")
    password = settings.get("password") or os.environ.get("SMTP_PASSWORD")
    sender = settings.get("sender") or os.environ.get("SMTP_SENDER", user)
    use_starttls = settings.get("use_starttls")
    if use_starttls is None:
        use_starttls = os.environ.get("SMTP_USE_STARTTLS", "true").lower() in {"1", "true", "yes"}

    if not all([host, user, password, sender]):
        raise RuntimeError("Missing SMTP configuration")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    effective_cc = renewal_email_cc_recipients(recipients) if cc_recipients is None else cc_recipients
    if effective_cc:
        message["Cc"] = ", ".join(effective_cc)
    message.set_content(body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    for att in attachments or []:
        name = att.get("name")
        content = att.get("content")
        if name and content is not None:
            mime_type = att.get("mime_type") or mimetypes.guess_type(name)[0] or "application/octet-stream"
            maintype, subtype = mime_type.split("/", 1)
            message.add_attachment(
                content,
                maintype=maintype,
                subtype=subtype,
                filename=name,
            )

    try:
        with smtplib.SMTP(host, port, timeout=60) as server:
            server.ehlo()
            if use_starttls:
                server.starttls(context=smtp_ssl_context())
                server.ehlo()
            server.login(user, password)
            server.send_message(message)
    except (BrokenPipeError, ConnectionResetError, smtplib.SMTPServerDisconnected) as exc:
        raise SmtpDeliveryUncertainError(
            "Gmail cerró la conexión durante el envío. Por seguridad no se reintentó "
            "automáticamente para evitar duplicados. Revisa la carpeta Enviados antes "
            "de volver a intentarlo."
        ) from exc


def build_metlife_gmm_renewal_email_body(
    client_name: str,
    client_email: str,
    policy_number: str,
    end_date: str,
) -> str:
    try:
        period_start = datetime.strptime(end_date, "%Y-%m-%d").year
    except ValueError:
        period_start = datetime.now().year
    period_end = period_start + 1
    return (
        f"Hola {client_name},\n\n"
        "Te compartimos la documentación correspondiente a la renovación de tu póliza "
        f"de Gastos Médicos Mayores MetLife para el periodo {period_start} - {period_end}.\n\n"
        "Adjuntamos:\n"
        "- CFDIs y avisos de la renovación.\n"
        "- Documentos de la póliza.\n\n"
        f"Póliza de referencia: {policy_number}\n\n"
        "Saludos,\nTAIICO"
    )


def renewal_email_recipients(intended_client_email: str) -> list[str]:
    internal_only = os.getenv("RENEWAL_EMAIL_INTERNAL_ONLY", "true").lower() in {"1", "true", "yes"}
    if not internal_only:
        return [email.strip() for email in intended_client_email.split(",") if email.strip()]

    configured = os.getenv("RENEWAL_EMAIL_INTERNAL_RECIPIENTS", "")
    recipients = [email.strip() for email in configured.split(",") if email.strip()]
    if not recipients:
        raise RuntimeError("RENEWAL_EMAIL_INTERNAL_RECIPIENTS is required while internal-only mode is enabled")
    return recipients

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

@router.post("/metlife/gmm/retrieval-adapter-contract")
async def run_metlife_gmm_retrieval_adapter_contract(
    dry_run: bool = Body(True, embed=True),
    limit: int = Body(5, embed=True),
    simulate_result: str = Body("adapter_not_implemented", embed=True),
    fail_step: str = Body("open_browser", embed=True),
    system_admin_email: str = Body("alberto.alfaro@taiico.com", embed=True),
):
    """
    Defines the run/task/step contract consumed later by the real browser adapter.

    dry_run=True returns the execution plan without changing queued work.
    dry_run=False performs state transitions using a simulated result.
    """
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    if simulate_result not in {"success", "adapter_not_implemented", "fail_at_step"}:
        raise HTTPException(status_code=400, detail="simulate_result must be success, adapter_not_implemented, or fail_at_step")
    if fail_step not in METLIFE_GMM_RETRIEVAL_STEPS:
        raise HTTPException(status_code=400, detail=f"fail_step must be one of: {', '.join(METLIFE_GMM_RETRIEVAL_STEPS)}")

    db = SessionLocal()
    try:
        queued_at_start = db.query(PolicyDocumentRetrievalTask).filter(
            PolicyDocumentRetrievalTask.status == "queued",
            PolicyDocumentRetrievalTask.insurer_id == "metlife",
            PolicyDocumentRetrievalTask.product_branch == "GMM",
        ).count()
        tasks = select_retrieval_tasks(db, "metlife", "GMM", limit)

        execution_plan = [
            {
                "task": serialize_retrieval_task(task),
                "steps": retrieval_step_plan(task),
                "failure_escalation_preview": build_escalation_email_payload(
                    task=task,
                    failed_step=fail_step,
                    error_message="Adapter is not implemented yet." if simulate_result == "adapter_not_implemented" else "Simulated adapter failure.",
                    system_admin_email=system_admin_email,
                ),
            }
            for task in tasks
        ]

        if dry_run:
            return {
                "dry_run": True,
                "adapter_name": "metlife_gmm_portal_adapter",
                "queued_at_start": queued_at_start,
                "selected_count": len(tasks),
                "simulate_result": simulate_result,
                "system_admin_email": system_admin_email,
                "execution_plan": execution_plan,
            }

        run = PolicyDocumentRetrievalRun(
            adapter_name="metlife_gmm_portal_adapter",
            insurer_id="metlife",
            product_branch="GMM",
            status="started",
            queued_at_start=queued_at_start,
            selected_count=len(tasks),
            summary_email_to=system_admin_email,
            metadata_json={
                "simulate_result": simulate_result,
                "contract_version": "1.0.0",
                "steps": METLIFE_GMM_RETRIEVAL_STEPS,
            },
        )
        db.add(run)
        db.flush()

        generated_escalations = []
        generated_steps = []
        succeeded = 0
        failed = 0
        escalated = 0

        for task in tasks:
            task.status = "in_progress"
            task.attempt_count = (task.attempt_count or 0) + 1
            task.last_attempt_at = datetime.utcnow()
            task.retrieval_adapter = "metlife_gmm_portal_adapter"
            task.updated_at = datetime.utcnow()

            failed_step_name = fail_step
            if simulate_result == "adapter_not_implemented":
                failed_step_name = "open_browser"

            task_failed = False
            for step_name in METLIFE_GMM_RETRIEVAL_STEPS:
                step_status = "completed"
                error_message = None
                if simulate_result in {"adapter_not_implemented", "fail_at_step"} and step_name == failed_step_name:
                    step_status = "failed"
                    error_message = "Adapter is not implemented yet." if simulate_result == "adapter_not_implemented" else "Simulated adapter failure."
                    task_failed = True

                step = PolicyDocumentRetrievalStep(
                    run_id=run.id,
                    task_id=task.id,
                    step_name=step_name,
                    status=step_status,
                    completed_at=datetime.utcnow(),
                    error_message=error_message,
                    metadata_json={
                        "policy_number": task.policy_number,
                        "client_name": task.client_name,
                    },
                )
                db.add(step)
                generated_steps.append(step)
                if task_failed:
                    break

            if task_failed:
                failed += 1
                escalated += 1
                task.status = "escalated"
                task.last_error = f"{failed_step_name}: {error_message}"
                task.updated_at = datetime.utcnow()
                generated_escalations.append(build_escalation_email_payload(
                    task=task,
                    failed_step=failed_step_name,
                    error_message=error_message or "Unknown adapter failure.",
                    system_admin_email=system_admin_email,
                    run_id=run.id,
                ))
            else:
                succeeded += 1
                task.status = "retrieved"
                task.document_status = "linked"
                task.completed_at = datetime.utcnow()
                task.last_error = None
                task.updated_at = datetime.utcnow()

        run.processed_count = len(tasks)
        run.succeeded_count = succeeded
        run.failed_count = failed
        run.escalated_count = escalated
        run.completed_at = datetime.utcnow()
        run.status = "completed_with_escalations" if escalated else "completed"

        db.commit()
        db.refresh(run)

        persisted_steps = db.query(PolicyDocumentRetrievalStep).filter(
            PolicyDocumentRetrievalStep.run_id == run.id,
        ).order_by(
            PolicyDocumentRetrievalStep.started_at.asc(),
            PolicyDocumentRetrievalStep.step_name.asc(),
        ).all()

        return {
            "dry_run": False,
            "run": serialize_retrieval_run(run),
            "steps": [serialize_retrieval_step(step) for step in persisted_steps],
            "escalation_emails": generated_escalations,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to run retrieval adapter contract: {e}")
    finally:
        db.close()

@router.post("/metlife/gmm/retrieval-adapter/run-task")
async def run_metlife_gmm_retrieval_adapter_task(
    task_id: Optional[str] = Body(None, embed=True),
    policy_number: Optional[str] = Body(None, embed=True),
    stop_after: str = Body("confirm_policy_match", embed=True),
    headless: bool = Body(False, embed=True),
    upload_to_drive: bool = Body(False, embed=True),
    mutate_queue: bool = Body(False, embed=True),
):
    db = SessionLocal()
    try:
        if upload_to_drive or mutate_queue:
            raise HTTPException(
                status_code=400,
                detail="The MetLife GMM MFA workflow is dry-run only; upload_to_drive and mutate_queue must be false.",
            )
        task = get_retrieval_task_for_adapter(db, task_id=task_id, policy_number=policy_number)
        adapter_task = MetLifeGmmPortalTask(
            id=task.id,
            policy_number=task.policy_number,
            rfc=task.rfc,
            client_name=task.client_name,
            renewal_deadline=task.renewal_deadline,
        )

        run = PolicyDocumentRetrievalRun(
            adapter_name="metlife_gmm_portal_adapter",
            insurer_id="metlife",
            product_branch="GMM",
            status="started",
            queued_at_start=db.query(PolicyDocumentRetrievalTask).filter(
                PolicyDocumentRetrievalTask.status == "queued",
                PolicyDocumentRetrievalTask.insurer_id == "metlife",
                PolicyDocumentRetrievalTask.product_branch == "GMM",
            ).count(),
            selected_count=1,
            summary_email_to="alberto.alfaro@taiico.com",
            metadata_json={
                "task_id": task.id,
                "policy_number": task.policy_number,
                "rfc": task.rfc,
                "stop_after": stop_after,
                "headless": headless,
                "upload_to_drive": upload_to_drive,
                "mutate_queue": mutate_queue,
            },
        )
        db.add(run)
        db.flush()
        session_profile_dir = stable_chrome_profile_dir()
        run.metadata_json = {
            **(run.metadata_json or {}),
            "session_profile_dir": str(session_profile_dir),
        }
        run_id = run.id
        task_db_id = task.id
        db.commit()

        if mutate_queue:
            task.status = "in_progress"
            task.attempt_count = (task.attempt_count or 0) + 1
            task.last_attempt_at = datetime.utcnow()
            task.retrieval_adapter = "metlife_gmm_portal_adapter"
            task.updated_at = datetime.utcnow()
            db.commit()

        adapter = MetLifeGmmPortalAdapter(
            headless=headless,
            session_profile_dir=session_profile_dir,
        )
        result = await run_in_threadpool(
            adapter.run,
            adapter_task,
            stop_after=stop_after,
            upload_to_drive=upload_to_drive,
            target_drive_folder_id=os.getenv("GOOGLE_DRIVE_RENEWALS_METLIFE_GMM_FOLDER_ID"),
        )
        result_payload = result_to_dict(result)
        run = db.query(PolicyDocumentRetrievalRun).filter(PolicyDocumentRetrievalRun.id == run_id).one()
        task = db.query(PolicyDocumentRetrievalTask).filter(PolicyDocumentRetrievalTask.id == task_db_id).one()
        persist_adapter_steps(db, run.id, task.id, result_payload["steps"])

        run.processed_count = 0 if result.status == "mfa_required" else 1
        run.succeeded_count = 1 if result.status in {"matched", "completed"} or result.status.startswith("stopped_after_") else 0
        run.failed_count = 1 if result.status == "failed" else 0
        run.escalated_count = 1 if result.status == "failed" else 0
        if result.status == "mfa_required":
            run.status = "waiting_for_mfa"
            run.completed_at = None
        else:
            run.status = "completed" if run.failed_count == 0 else "completed_with_escalations"
            run.completed_at = datetime.utcnow()

        if mutate_queue:
            if result.status == "completed":
                task.status = "retrieved"
                task.document_status = "linked"
                task.completed_at = datetime.utcnow()
                task.last_error = None
                task.expediente_link = result.drive_folder_link or task.expediente_link
            elif result.status == "failed":
                task.status = "escalated"
                task.last_error = result.error_message
            else:
                task.status = "queued"
            task.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(run)

        return {
            "run": serialize_retrieval_run(run),
            "task": serialize_retrieval_task(task),
            "adapter_result": result_payload,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to run MetLife GMM portal adapter: {e}")
    finally:
        db.close()

@router.post("/metlife/gmm/retrieval-adapter/runs/{run_id}/continue-mfa")
async def continue_metlife_gmm_retrieval_adapter_mfa(
    run_id: str,
    mfa_code: Optional[str] = Body(None, embed=True),
    stop_after: str = Body("confirm_policy_match", embed=True),
):
    """Resume a dry-run retrieval in the persisted browser session; never stores the MFA code."""
    db = SessionLocal()
    try:
        run = db.query(PolicyDocumentRetrievalRun).filter(
            PolicyDocumentRetrievalRun.id == run_id,
        ).first()
        if not run or run.adapter_name != "metlife_gmm_portal_adapter":
            raise HTTPException(status_code=404, detail="MetLife GMM retrieval run not found")
        if run.status != "waiting_for_mfa":
            raise HTTPException(status_code=409, detail=f"Run is not waiting for MFA (status={run.status})")

        metadata = run.metadata_json or {}
        task = get_retrieval_task_for_adapter(db, task_id=metadata.get("task_id"))
        session_profile_dir = metadata.get("session_profile_dir")
        if not session_profile_dir or not Path(session_profile_dir).exists():
            raise HTTPException(status_code=410, detail="The preserved MFA browser session is no longer available")

        adapter_task = MetLifeGmmPortalTask(
            id=task.id,
            policy_number=task.policy_number,
            rfc=task.rfc,
            client_name=task.client_name,
            renewal_deadline=task.renewal_deadline,
        )
        task_db_id = task.id
        db.commit()
        adapter = MetLifeGmmPortalAdapter(
            headless=bool(metadata.get("headless", False)),
            session_profile_dir=session_profile_dir,
        )
        result = await run_in_threadpool(
            adapter.run,
            adapter_task,
            stop_after=stop_after,
            upload_to_drive=False,
            resume_mfa=True,
            mfa_code=mfa_code,
        )
        result_payload = result_to_dict(result)
        run = db.query(PolicyDocumentRetrievalRun).filter(PolicyDocumentRetrievalRun.id == run_id).one()
        task = db.query(PolicyDocumentRetrievalTask).filter(PolicyDocumentRetrievalTask.id == task_db_id).one()
        persist_adapter_steps(db, run.id, task.id, result_payload["steps"])

        run.processed_count = 0 if result.status == "mfa_required" else 1
        run.succeeded_count = 1 if result.status in {"matched", "completed"} or result.status.startswith("stopped_after_") else 0
        run.failed_count = 1 if result.status == "failed" else 0
        run.escalated_count = run.failed_count
        if result.status == "mfa_required":
            run.status = "waiting_for_mfa"
            run.completed_at = None
        else:
            run.status = "completed" if run.failed_count == 0 else "completed_with_escalations"
            run.completed_at = datetime.utcnow()
        run.metadata_json = {
            **metadata,
            "continued_at": datetime.utcnow().isoformat(),
            "continuation_stop_after": stop_after,
            "mfa_code_supplied": bool(mfa_code),
        }
        db.commit()
        db.refresh(run)
        return {
            "run": serialize_retrieval_run(run),
            "task": serialize_retrieval_task(task),
            "adapter_result": result_payload,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to continue MetLife GMM MFA: {e}")
    finally:
        db.close()

@router.get("/retrieval-runs")
async def list_policy_document_retrieval_runs(
    limit: int = Query(25, ge=1, le=100),
):
    db = SessionLocal()
    try:
        runs = db.query(PolicyDocumentRetrievalRun).order_by(
            PolicyDocumentRetrievalRun.started_at.desc(),
        ).limit(limit).all()
        return {
            "count": len(runs),
            "runs": [serialize_retrieval_run(run) for run in runs],
        }
    finally:
        db.close()

@router.get("/retrieval-runs/{run_id}")
async def get_policy_document_retrieval_run(run_id: str):
    db = SessionLocal()
    try:
        run = db.query(PolicyDocumentRetrievalRun).filter(
            PolicyDocumentRetrievalRun.id == run_id,
        ).first()
        if not run:
            raise HTTPException(status_code=404, detail="Retrieval run not found")

        steps = db.query(PolicyDocumentRetrievalStep).filter(
            PolicyDocumentRetrievalStep.run_id == run.id,
        ).order_by(
            PolicyDocumentRetrievalStep.started_at.asc(),
            PolicyDocumentRetrievalStep.step_name.asc(),
        ).all()

        return {
            "run": serialize_retrieval_run(run),
            "steps": [serialize_retrieval_step(step) for step in steps],
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
        gmm_agents: dict[tuple[str, str], dict[str, str]] = {}
        vida_agents: dict[tuple[str, str], dict[str, str]] = {}
        promoterias: dict[str, str] = {}
        if insurer.lower() == "metlife" and type.upper() in {"ALL", "GMM"}:
            gmm_agents = await run_in_threadpool(metlife_gmm_agents)
        if insurer.lower() == "metlife" and type.upper() in {"ALL", "VIDA"}:
            vida_agents = await run_in_threadpool(metlife_vida_agents)
        if insurer.lower() == "metlife":
            promoterias = await run_in_threadpool(promotoria_by_agent_key)
        
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
                    agent = vida_agents.get(
                        (str(pol.policy_number).strip(), format_date(ren.renewal_deadline)),
                        vida_agents.get((str(pol.policy_number).strip(), ""), {}),
                    )
                    agent_code = agent.get("AGENTE", "")
                    results.append({
                        "POLIZA_ACTUAL": pol.policy_number,
                        "CONTRATANTE": pol.client.full_name if pol.client else "",
                        "INI_VIG": format_date(pol.effective_start_date),
                        "FIN_VIG": format_date(ren.renewal_deadline),
                        "FORMA_PAGO": pol.payment_frequency.upper(),
                        "CONDUCTO_COBRO": "Conducto de Cobro",
                        "AGENTE": agent_code,
                        "NOMBRE": agent.get("NOMBRE", ""),
                        "PROMOTORIA": promoterias.get(normalize_agent_key(agent_code), ""),
                        "PRIMA_ANUAL": float(pol.premium_amount) if pol.premium_amount else 0.0,
                        "PRIMA_MODAL": float(pol.premium_amount / 12) if pol.premium_amount else 0.0,
                        "PAGADO_HASTA": format_date(pol.effective_end_date),
                        "ESTATUS_DE_RENOVACION": ren.insurer_response,
                        "EXPEDIENTE": pol.document_link,
                        "Email": pol.client.email if pol.client else None
                    })
                else:
                    agent = gmm_agents.get(
                        (str(pol.policy_number).strip(), format_date(ren.renewal_deadline)),
                        gmm_agents.get((str(pol.policy_number).strip(), ""), {}),
                    )
                    agent_code = agent.get("AGENTE", "")
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
                        "AGENTE": agent_code,
                        "NOMBRE": agent.get("NOMBRE", ""),
                        "PROMOTORIA": promoterias.get(normalize_agent_key(agent_code), ""),
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
    expediente: Optional[str] = Body(None, embed=True),
    username: str = Depends(current_username),
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
        if insurer.lower() == "metlife" and type.upper() == "GMM":
            subject = f"Renovación Metlife GMM - {policy.client.full_name}"
            body = build_metlife_gmm_renewal_email_body(
                policy.client.full_name,
                recipient_email,
                policy_str,
                end_date,
            )
        else:
            body = (
                f"Buen día,\n"
                f"Comparto póliza {policy_str} con fecha Fin de Vigencia {end_date}.\n\n"
                f"La renovacion se encuentra adjunta en el correo o disponible en el sistema.\n"
                f"Nos mantenemos en contacto para cualquier duda\n\n"
                f"Atentamente Taiico Life Advisors"
            )
        
        # Attach every file from a local folder or a Google Drive folder.
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
            elif drive_file_id_from_url(exp_path):
                attachments = drive_folder_attachments(exp_path)
            elif exp_path.startswith("http"):
                body += f"\n\nLink al expediente: {exp_path}"
                
        # Send Email
        recipients = renewal_email_recipients(recipient_email)
        user_smtp_settings = smtp_settings_for(username)
        send_email_smtp(subject, body, recipients, attachments, settings=user_smtp_settings)
        
        # Update database status
        renewal = db.query(Renewal).filter(Renewal.original_policy_id == policy.id).first()
        if renewal:
            renewal.insurer_response = "Enviado"
            db.commit()
            
        return {
            "message": "Correo de renovación enviado",
            "actual_recipients": recipients,
            "cc_recipients": renewal_email_cc_recipients(recipients),
            "intended_client_email": recipient_email,
            "internal_only": os.getenv("RENEWAL_EMAIL_INTERNAL_ONLY", "true").lower() in {"1", "true", "yes"},
            "sender_source": "user_configuration" if user_smtp_settings else "server_fallback",
            "attachment_count": len(attachments),
        }
        
    except HTTPException:
        raise
    except DriveAttachmentError as e:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(e)) from e
    except SmtpDeliveryUncertainError as e:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(e)) from e
    except smtplib.SMTPAuthenticationError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=(
                "Gmail rechazó la cuenta remitente. Vuelve a guardar la contraseña de "
                "aplicación y usa Probar conexión."
            ),
        ) from e
    except Exception as e:
        print(f"Error sending email: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al enviar correo: {str(e)}")
    finally:
        db.close()
