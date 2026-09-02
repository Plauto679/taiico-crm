from __future__ import annotations

import argparse
import fcntl
import json
import mimetypes
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from sqlalchemy import and_, or_


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env", override=True)

from adapters.metlife_gmm_portal import (  # noqa: E402
    MetLifeGmmPortalTask,
    chrome_cdp_port,
    chrome_server_ready,
    ensure_persistent_chrome,
    result_to_dict,
    stable_chrome_profile_dir,
)
from adapters.metlife_gmm_collection import (  # noqa: E402
    COLLECTION_FAILURE_DATE,
    check_metlife_gmm_collection,
    collection_result_to_dict,
)
from adapters.metlife_gmm_old_portal import (  # noqa: E402
    OLD_PORTAL_ADAPTER_NAME,
    MetLifeGmmOldPortalAdapter,
)
from database import (  # noqa: E402
    AgentAction,
    Policy,
    PolicyDocumentRetrievalRun,
    PolicyDocumentRetrievalTask,
    Renewal,
    SessionLocal,
)
from services.client_email_directory import lookup_client_email  # noqa: E402
from services.metlife_agent_directory import (  # noqa: E402
    AgentContactResolutionError,
    resolve_agent_contact,
)
from services.automatic_mails import (  # noqa: E402
    automation_config,
    local_now_for,
    schedule_matches,
)
from services.renewal_agent_api import TAIICO_AGENT_CODES  # noqa: E402
from services.renovaciones import (  # noqa: E402
    SmtpDeliveryUncertainError,
    build_metlife_gmm_agent_email_body,
    build_metlife_gmm_renewal_email_body,
    persist_adapter_steps,
    renewal_agent_email_cc_recipients,
    renewal_email_cc_recipients,
    renewal_email_recipients,
    renewal_smtp_settings,
    send_email_smtp,
)


DEFAULT_TIMEZONE = "America/Mexico_City"
DEFAULT_HOUR = 7
DEFAULT_WINDOW_DAYS = 45
DEFAULT_MAX_CONSECUTIVE_PORTAL_FAILURES = 7
DEFAULT_TARGET_DRIVE_FOLDER_ID = "1UthkPpr5_pvX5SszrCuIm546XKZh4Z_R"
DEFAULT_INTERNAL_RECIPIENTS = (
    "alberto.alfaro@taiico.com,"
    "veronica.alfaro@taiico.com"
)
MAX_ATTACHMENT_BYTES = 18 * 1024 * 1024
MAX_ATTACHMENT_COUNT = 100

# This daily job intentionally has no WhatsApp dependency. Re-enabling WhatsApp
# requires an explicit code change and review, not merely refreshing a token.
WHATSAPP_ENABLED = False

AUTOMATION_PROTECTED_RENEWAL_STATUSES = {
    "renovado automatico",
    "renovada automaticamente",
    "renovada manual",
    "enviada manual",
    "enviada al cliente",
    "enviado al cliente",
    "enviado a cliente",
    "enviado automaticamente",
    "enviado al agente",
    "enviado",
    "revision manual necesaria",
}


def renewal_status_blocks_automation(value: str | None) -> bool:
    normalized = str(value or "").strip().lower()
    normalized = normalized.translate(str.maketrans("áéíóúüñ", "aeiouun"))
    return normalized in AUTOMATION_PROTECTED_RENEWAL_STATUSES


def should_check_collection_after_failure(detail: str | None) -> bool:
    normalized = str(detail or "").strip().lower()
    normalized = normalized.translate(str.maketrans("áéíóúüñ", "aeiouun"))
    return (
        "timeout 90000ms exceeded" in normalized
        or "se espero una poliza original" in normalized
    )


def emit(event: str, **payload) -> None:
    print(json.dumps({"event": event, **payload}, ensure_ascii=False), flush=True)


def local_now() -> datetime:
    return local_now_for("renewal_agent")


def scheduled_hour() -> int:
    return int(automation_config("renewal_agent")["hour"])


def window_days() -> int:
    return int(
        os.getenv(
            "RENEWAL_AGENT_AUTOMATION_WINDOW_DAYS",
            str(DEFAULT_WINDOW_DAYS),
        )
    )


def should_run(now: datetime, last_started_date: str | None) -> bool:
    return schedule_matches(automation_config("renewal_agent"), now) and (
        last_started_date != now.date().isoformat()
    )


def renewal_cutoff(now: datetime) -> date:
    return now.date() + timedelta(days=window_days())


def state_path() -> Path:
    configured = os.getenv("RENEWAL_AGENT_AUTOMATION_STATE_FILE", "").strip()
    return (
        Path(configured).expanduser()
        if configured
        else REPOSITORY_ROOT / ".runtime" / "renewal-agent-state.json"
    )


def read_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def internal_recipients() -> list[str]:
    return list(automation_config("renewal_agent")["recipients"])


def send_internal_renewal_email(*, subject: str, body: str) -> None:
    """Send batch lifecycle notices from the dedicated renewals mailbox."""
    send_email_smtp(
        subject=subject,
        body=body,
        recipients=internal_recipients(),
        cc_recipients=[],
        settings=renewal_smtp_settings(),
    )


def target_drive_folder_id() -> str:
    return (
        os.getenv("GOOGLE_DRIVE_RENEWALS_METLIFE_GMM_FOLDER_ID", "").strip()
        or DEFAULT_TARGET_DRIVE_FOLDER_ID
    )


def max_consecutive_portal_failures() -> int:
    return int(
        os.getenv(
            "RENEWAL_AGENT_MAX_CONSECUTIVE_PORTAL_FAILURES",
            str(DEFAULT_MAX_CONSECUTIVE_PORTAL_FAILURES),
        )
    )


def attachment_payloads(folder: str | None) -> list[dict]:
    if not folder:
        raise RuntimeError("La descarga no produjo una carpeta de documentos")
    paths = sorted(path for path in Path(folder).rglob("*") if path.is_file())
    if not paths:
        raise RuntimeError("La descarga no produjo documentos para adjuntar")
    if len(paths) > MAX_ATTACHMENT_COUNT:
        raise RuntimeError(
            f"El expediente contiene {len(paths)} archivos; "
            f"máximo {MAX_ATTACHMENT_COUNT}"
        )
    total = sum(path.stat().st_size for path in paths)
    if total > MAX_ATTACHMENT_BYTES:
        raise RuntimeError(
            f"Los adjuntos pesan {total} bytes y exceden el límite seguro"
        )
    return [
        {
            "name": path.name,
            "content": path.read_bytes(),
            "mime_type": mimetypes.guess_type(path.name)[0]
            or "application/octet-stream",
        }
        for path in paths
    ]


def step(
    step_name: str,
    status: str,
    *,
    started_at: datetime,
    error_message: str | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "step_name": step_name,
        "status": status,
        "started_at": started_at.isoformat(),
        "completed_at": datetime.utcnow().isoformat(),
        "error_message": error_message,
        "metadata": metadata or {},
    }


def summary_body(
    title: str,
    tasks: list[PolicyDocumentRetrievalTask],
    process_date: date,
) -> str:
    lines = [
        "Equipo,",
        "",
        title,
        "",
        f"Fecha de proceso: {process_date.isoformat()}",
        f"Pólizas en cola: {len(tasks)}",
        "",
        "Póliza | Vencimiento | Cliente | RFC",
    ]
    lines.extend(
        f"{task.policy_number} | {task.renewal_deadline} | "
        f"{task.client_name or '-'} | {task.rfc or '-'}"
        for task in tasks
    )
    lines.extend(
        [
            "",
            "WhatsApp: desactivado para esta automatización.",
            "",
            "Saludos,",
            "TAIICO OS",
        ]
    )
    return "\n".join(lines)


def missing_client_email_body(
    *,
    client_name: str,
    policy_number: str,
    renewal_deadline: date,
) -> str:
    client_body = build_metlife_gmm_renewal_email_body(
        client_name,
        "",
        policy_number,
        renewal_deadline.isoformat(),
    )
    return "No tenemos un correo de cliente registrado.\n\n" + client_body


def update_crm_renewal_fields(
    db,
    task: PolicyDocumentRetrievalTask,
    expediente_link: str | None,
    renewal_status: str | None = None,
) -> None:
    if not expediente_link:
        return
    policy = db.query(Policy).filter(
        Policy.policy_number == str(task.policy_number).strip()
    ).first()
    if policy is None:
        return
    policy.document_link = expediente_link
    renewal = db.query(Renewal).filter(
        Renewal.original_policy_id == policy.id
    ).first()
    if renewal is None:
        renewal = Renewal(
            original_policy_id=policy.id,
            client_id=policy.client_id,
            renewal_deadline=policy.effective_end_date,
            status="in_progress",
        )
        db.add(renewal)
        db.flush()
    if renewal_status:
        renewal.insurer_response = renewal_status
    renewal.updated_at = datetime.utcnow()


def persist_collection_check(
    task_id: str,
    *,
    paid_until: date,
    succeeded: bool,
    error: str | None = None,
) -> bool:
    """Store collection evidence and return whether manual review was assigned."""
    db = SessionLocal()
    try:
        task = db.get(PolicyDocumentRetrievalTask, task_id)
        if task is None:
            raise RuntimeError(f"No existe la tarea de renovación {task_id}")
        payload = dict(task.normalized_payload or {})
        payload["paid_until_date"] = paid_until.isoformat()
        payload["collection_check"] = {
            "status": "completed" if succeeded else "failed",
            "paid_until": paid_until.isoformat(),
            "error": error,
            "checked_at": datetime.utcnow().isoformat(),
        }
        task.normalized_payload = payload

        policy = db.query(Policy).filter(
            Policy.policy_number == str(task.policy_number).strip()
        ).first()
        manual_review_assigned = False
        if policy is not None:
            renewal = db.query(Renewal).filter(
                Renewal.original_policy_id == policy.id
            ).first()
            if renewal is None:
                renewal = Renewal(
                    original_policy_id=policy.id,
                    client_id=policy.client_id,
                    renewal_deadline=policy.effective_end_date,
                    status="in_progress",
                )
                db.add(renewal)
                db.flush()
            renewal.paid_until = paid_until
            if (
                succeeded
                and paid_until >= task.renewal_deadline
                and not str(renewal.insurer_response or "").strip()
            ):
                renewal.insurer_response = "Revision Manual Necesaria"
                manual_review_assigned = True
            renewal.updated_at = datetime.utcnow()
        db.commit()
        return manual_review_assigned
    finally:
        db.close()


def record_action(
    *,
    task: PolicyDocumentRetrievalTask,
    status: str,
    output: dict,
    duration_ms: int,
) -> None:
    db = SessionLocal()
    try:
        db.add(
            AgentAction(
                agent_name="renewal_agent",
                action_type="renewal_delivery",
                status=status,
                description=(
                    "MetLife GMM renewal delivery for policy "
                    f"{task.policy_number}"
                ),
                input_payload={
                    "task_id": task.id,
                    "policy_number": task.policy_number,
                },
                output_payload=output,
                duration_ms=duration_ms,
            )
        )
        db.commit()
    finally:
        db.close()


def task_processing_order(
    task: PolicyDocumentRetrievalTask,
    process_date: date,
) -> tuple:
    """Prioritize the active renewal window and leave overdue tasks last."""
    deadline = task.renewal_deadline or date.max
    is_overdue = deadline < process_date
    return (
        is_overdue,
        deadline,
        task.attempt_count or 0,
        task.policy_number or "",
    )


def task_agent_code(task: PolicyDocumentRetrievalTask) -> str:
    payload = task.normalized_payload or {}
    value = payload.get("agent_code")
    if value is None:
        value = (task.source_payload or {}).get("AGENTE")
    text = str(value or "").strip()
    return text[:-2] if text.endswith(".0") else text


def selected_tasks(
    cutoff: date,
    *,
    process_date: date | None = None,
) -> list[PolicyDocumentRetrievalTask]:
    db = SessionLocal()
    try:
        tasks = (
            db.query(PolicyDocumentRetrievalTask)
            .filter(
                PolicyDocumentRetrievalTask.insurer_id == "metlife",
                PolicyDocumentRetrievalTask.product_branch == "GMM",
                or_(
                    PolicyDocumentRetrievalTask.status == "approved",
                    and_(
                        PolicyDocumentRetrievalTask.status == "queued",
                        PolicyDocumentRetrievalTask.attempt_count > 0,
                    ),
                ),
                PolicyDocumentRetrievalTask.renewal_deadline <= cutoff,
            )
            .order_by(
                PolicyDocumentRetrievalTask.renewal_deadline.asc(),
                PolicyDocumentRetrievalTask.attempt_count.asc(),
                PolicyDocumentRetrievalTask.policy_number.asc(),
            )
            .all()
        )
        protected_task_ids = {
            str(action.input_payload.get("task_id"))
            for action in db.query(AgentAction)
            .filter(
                AgentAction.action_type == "renewal_delivery",
                AgentAction.status.in_(["completed", "delivery_uncertain"]),
            )
            .all()
            if action.input_payload and action.input_payload.get("task_id")
        }
        protected_policy_numbers = {
            str(policy_number).strip()
            for policy_number, renewal_status in (
                db.query(Policy.policy_number, Renewal.insurer_response)
                .join(Renewal, Renewal.original_policy_id == Policy.id)
                .filter(Renewal.insurer_response.isnot(None))
                .all()
            )
            if renewal_status_blocks_automation(renewal_status)
        }
        for task in tasks:
            db.expunge(task)
        eligible_tasks = [
            task
            for task in tasks
            if task.id not in protected_task_ids
            and str(task.policy_number).strip() not in protected_policy_numbers
        ]
        effective_process_date = process_date or local_now().date()
        return sorted(
            eligible_tasks,
            key=lambda task: task_processing_order(
                task,
                effective_process_date,
            ),
        )
    finally:
        db.close()


def create_run(
    tasks: list[PolicyDocumentRetrievalTask],
    cutoff: date,
) -> str:
    db = SessionLocal()
    try:
        run = PolicyDocumentRetrievalRun(
            adapter_name=OLD_PORTAL_ADAPTER_NAME,
            insurer_id="metlife",
            product_branch="GMM",
            status="started",
            queued_at_start=len(tasks),
            selected_count=len(tasks),
            summary_email_to=",".join(internal_recipients()),
            metadata_json={
                "production_client_email": True,
                "whatsapp_enabled": WHATSAPP_ENABLED,
                "window_days": window_days(),
                "cutoff_date": cutoff.isoformat(),
                "includes_overdue_queued_tasks": True,
            },
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run.id
    finally:
        db.close()


def undo_transient_retry_accounting(run_id: str) -> None:
    db = SessionLocal()
    try:
        run = db.get(PolicyDocumentRetrievalRun, run_id)
        if run is None:
            return
        run.processed_count = max((run.processed_count or 0) - 1, 0)
        run.failed_count = max((run.failed_count or 0) - 1, 0)
        db.commit()
    finally:
        db.close()


def update_task_attempt(task_id: str) -> PolicyDocumentRetrievalTask:
    db = SessionLocal()
    try:
        task = db.get(PolicyDocumentRetrievalTask, task_id)
        if task is None:
            raise RuntimeError(f"No existe la tarea de renovación {task_id}")
        task.status = "in_progress"
        task.attempt_count = (task.attempt_count or 0) + 1
        task.last_attempt_at = datetime.utcnow()
        task.last_error = None
        db.commit()
        db.refresh(task)
        db.expunge(task)
        return task
    finally:
        db.close()


def persist_result(
    run_id: str,
    task_id: str,
    result_data: dict,
    *,
    retrieval_succeeded: bool,
    delivery_succeeded: bool,
    renewal_status: str | None = None,
    error: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        task = db.get(PolicyDocumentRetrievalTask, task_id)
        run = db.get(PolicyDocumentRetrievalRun, run_id)
        if task is None or run is None:
            raise RuntimeError("No se encontró la corrida o tarea a actualizar")
        persist_adapter_steps(
            db,
            run_id,
            task_id,
            result_data.get("steps") or [],
        )
        run.processed_count += 1
        if delivery_succeeded:
            run.succeeded_count += 1
        else:
            run.failed_count += 1

        if retrieval_succeeded:
            expediente_link = result_data.get("drive_folder_link")
            task.status = "retrieved"
            task.document_status = "retrieved"
            task.expediente_link = expediente_link
            task.target_drive_folder_id = result_data.get("drive_folder_id")
            task.target_drive_folder_path = expediente_link
            task.retrieval_adapter = OLD_PORTAL_ADAPTER_NAME
            task.completed_at = datetime.utcnow()
            task.last_error = error
            update_crm_renewal_fields(db, task, expediente_link, renewal_status)
        else:
            task.status = "queued"
            task.last_error = (
                error
                or result_data.get("error_message")
                or "Error desconocido"
            )
        db.commit()
    finally:
        db.close()


def finish_run(
    run_id: str,
    results: list[dict],
    *,
    aborted: bool,
    process_date: date,
) -> dict:
    db = SessionLocal()
    try:
        run = db.get(PolicyDocumentRetrievalRun, run_id)
        if run is None:
            raise RuntimeError(f"No se encontró la corrida {run_id}")
        run.status = (
            "aborted"
            if aborted
            else (
                "completed_with_errors"
                if any(item["status"] != "completed" for item in results)
                else "completed"
            )
        )
        run.completed_at = datetime.utcnow()
        run.metadata_json = {
            **(run.metadata_json or {}),
            "results": results,
        }
        db.commit()
        summary = {
            "run_id": run.id,
            "status": run.status,
            "selected": run.selected_count,
            "succeeded": run.succeeded_count,
            "failed": run.failed_count,
            "aborted": aborted,
        }
    finally:
        db.close()

    lines = [
        "Equipo,",
        "",
        "Finalizó el proceso de renovaciones MetLife GMM.",
        "",
        f"Fecha de proceso: {process_date.isoformat()}",
        f"Pólizas planeadas: {summary['selected']}",
        f"Renovaciones completadas: {summary['succeeded']}",
        f"Errores / pendientes: {summary['failed']}",
        f"Proceso abortado: {'sí' if aborted else 'no'}",
        "WhatsApp: desactivado; no se intentaron mensajes.",
        "",
        "Resultado:",
    ]
    for item in results:
        lines.append(
            f"{item['policy']} | {item['client']} | {item['status']} | "
            f"{item.get('detail', '')}"
        )
    lines.extend(["", "Saludos,", "TAIICO OS"])
    subject_prefix = "ALERTA: " if aborted else ""
    send_internal_renewal_email(
        subject=(
            f"{subject_prefix}Cierre renovaciones MetLife GMM - "
            f"{process_date.isoformat()}"
        ),
        body="\n".join(lines),
    )
    emit("batch_finished", **summary)
    return summary


def is_portal_failure(result_data: dict) -> bool:
    failed_steps = [
        item.get("step_name")
        for item in result_data.get("steps") or []
        if item.get("status") not in {"completed", "skipped"}
    ]
    return any(
        name
        in {
            "open_browser",
            "authenticate_portal",
            "clientes_beta",
            "search_policy",
            "confirm_policy_match",
            "download_policy_document",
            "open_old_portal",
            "authenticate_old_portal",
            "open_contractual_search",
            "search_rfc",
            "download_documents",
        }
        for name in failed_steps
    )


def process_one(run_id: str, task_id: str) -> tuple[dict, bool]:
    task = update_task_attempt(task_id)
    started = time.monotonic()
    emit(
        "task_started",
        policy=task.policy_number,
        client=task.client_name,
        deadline=str(task.renewal_deadline),
        attempt=task.attempt_count,
    )
    adapter = MetLifeGmmOldPortalAdapter(headless=False)
    result = adapter.run(
        MetLifeGmmPortalTask(
            id=task.id,
            policy_number=task.policy_number,
            rfc=task.rfc or "",
            client_name=task.client_name,
            renewal_deadline=task.renewal_deadline,
            original_policy_number=task.original_policy_number,
        ),
        stop_after=None,
        upload_to_drive=True,
    )
    data = result_to_dict(result)
    if result.status != "completed":
        detail = result.error_message or result.status
        collection_data = None
        collection_handled_failure = False
        manual_review_assigned = False
        if should_check_collection_after_failure(detail):
            emit(
                "collection_check_started",
                policy=task.policy_number,
                rfc=task.rfc,
            )
            collection_result = check_metlife_gmm_collection(
                MetLifeGmmPortalTask(
                    id=task.id,
                    policy_number=task.policy_number,
                    original_policy_number=task.original_policy_number,
                    rfc=task.rfc or "",
                    client_name=task.client_name,
                    renewal_deadline=task.renewal_deadline,
                ),
                headless=False,
            )
            collection_data = collection_result_to_dict(collection_result)
            data["steps"] = [
                *(data.get("steps") or []),
                *(collection_data.get("steps") or []),
            ]
            paid_until = collection_result.paid_until or COLLECTION_FAILURE_DATE
            collection_handled_failure = collection_result.status == "completed"
            manual_review_assigned = persist_collection_check(
                task.id,
                paid_until=paid_until,
                succeeded=collection_handled_failure,
                error=collection_result.error_message,
            )
            if collection_handled_failure:
                detail = (
                    f"{detail} | Cobranza: Pagado Hasta "
                    f"{paid_until.strftime('%d/%m/%Y')}"
                )
                if manual_review_assigned:
                    detail += " | CRM: Revision Manual Necesaria"
            else:
                detail = (
                    f"{detail} | Falló consulta de cobranza: "
                    f"{collection_result.error_message or 'error desconocido'} | "
                    "Pagado Hasta: 01/01/2000"
                )
            emit(
                "collection_check_finished",
                policy=task.policy_number,
                status=collection_result.status,
                paid_until=paid_until.isoformat(),
                manual_review=manual_review_assigned,
            )
        persist_result(
            run_id,
            task.id,
            data,
            retrieval_succeeded=False,
            delivery_succeeded=False,
            error=detail,
        )
        record_action(
            task=task,
            status="failed",
            output={
                "adapter_result": result.status,
                "error": detail,
                "collection_check": collection_data,
                "manual_review_assigned": manual_review_assigned,
            },
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        emit("task_failed", policy=task.policy_number, detail=detail)
        return {
            "policy": task.policy_number,
            "client": task.client_name or "-",
            "status": "failed",
            "detail": detail,
        }, is_portal_failure(data) and not collection_handled_failure

    delivery_steps: list[dict] = []
    try:
        step_started = datetime.utcnow()
        attachments = attachment_payloads(result.extracted_folder_path)
        delivery_steps.append(
            step(
                "prepare_email_attachments",
                "completed",
                started_at=step_started,
                metadata={"attachment_count": len(attachments)},
            )
        )

        step_started = datetime.utcnow()
        client_email = lookup_client_email(task.client_name)
        agent_code = task_agent_code(task)
        missing_client_email = not client_email
        if agent_code not in TAIICO_AGENT_CODES:
            contact = resolve_agent_contact(agent_code)
            agent_email = contact["email"]
            recipients = renewal_email_recipients(agent_email)
            if recipients != [agent_email]:
                raise RuntimeError(
                    "La configuración de correo no está habilitada para el agente real"
                )
            cc_recipients = renewal_agent_email_cc_recipients(recipients)
            email_body = build_metlife_gmm_agent_email_body(
                contact.get("name", "Agente"),
                task.client_name or "Cliente",
                client_email or "",
                task.policy_number,
                task.renewal_deadline.isoformat(),
            )
            period_start = task.renewal_deadline.year
            subject = (
                f"Renovación MetLife GMM - {task.client_name} - "
                f"{period_start} - {period_start + 1}"
            )
            delivery_mode = "agent"
            renewal_status = "Enviado al agente"
        elif missing_client_email:
            recipients = internal_recipients()
            cc_recipients = []
            email_body = missing_client_email_body(
                client_name=task.client_name or "Cliente",
                policy_number=task.policy_number,
                renewal_deadline=task.renewal_deadline,
            )
            subject = (
                "ACCIÓN REQUERIDA: Sin correo de cliente - "
                f"Renovación MetLife GMM - {task.client_name}"
            )
            delivery_mode = "internal_missing_client_email"
            renewal_status = "Revision Manual Necesaria"
        else:
            recipients = renewal_email_recipients(client_email)
            if recipients != [client_email]:
                raise RuntimeError(
                    "La configuración de correo no está habilitada para el cliente real"
                )
            cc_recipients = renewal_email_cc_recipients(recipients)
            email_body = build_metlife_gmm_renewal_email_body(
                task.client_name or "Cliente",
                client_email,
                task.policy_number,
                task.renewal_deadline.isoformat(),
            )
            period_start = task.renewal_deadline.year
            subject = (
                f"Renovación MetLife GMM - {task.client_name} - "
                f"{period_start} - {period_start + 1}"
            )
            delivery_mode = "client"
            renewal_status = "Enviado Automáticamente"
        delivery_steps.append(
            step(
                "resolve_client_email",
                "completed",
                started_at=step_started,
                metadata={
                    "client_email": client_email,
                    "agent_code": agent_code,
                    "delivery_mode": delivery_mode,
                    "recipients": recipients,
                },
            )
        )

        step_started = datetime.utcnow()
        send_email_smtp(
            subject=subject,
            body=email_body,
            recipients=recipients,
            attachments=attachments,
            cc_recipients=cc_recipients,
            settings=renewal_smtp_settings(),
        )
        delivery_steps.append(
            step(
                "send_renewal_email",
                "completed",
                started_at=step_started,
                metadata={
                    "recipient": recipients[0],
                    "cc_recipients": cc_recipients,
                    "delivery_mode": delivery_mode,
                },
            )
        )
        delivery_steps.append(
            step(
                "send_whatsapp",
                "skipped",
                started_at=datetime.utcnow(),
                metadata={"reason": "disabled_by_automation_policy"},
            )
        )
        data["steps"] = [*(data.get("steps") or []), *delivery_steps]
        persist_result(
            run_id,
            task.id,
            data,
            retrieval_succeeded=True,
            delivery_succeeded=True,
            renewal_status=renewal_status,
        )
        output = {
            "drive_folder_id": result.drive_folder_id,
            "drive_folder_link": result.drive_folder_link,
            "client_email": client_email,
            "agent_code": agent_code,
            "delivery_mode": delivery_mode,
            "recipients": recipients,
            "cc": cc_recipients,
            "attachments": len(attachments),
            "adapter_result": result.status,
            "whatsapp": {
                "enabled": WHATSAPP_ENABLED,
                "status": "skipped",
            },
        }
        record_action(
            task=task,
            status="completed",
            output=output,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        detail = (
            (
                f"Sin correo cliente; expediente a equipo interno; "
                f"{len(attachments)} adjuntos; WhatsApp omitido"
            )
            if delivery_mode == "internal_missing_client_email"
            else (
                f"Correo al agente {recipients[0]}; {len(attachments)} adjuntos; "
                "WhatsApp omitido"
            )
            if delivery_mode == "agent"
            else (
                f"Correo a {client_email}; {len(attachments)} adjuntos; "
                "WhatsApp omitido"
            )
        )
        emit("task_completed", policy=task.policy_number, detail=detail)
        return {
            "policy": task.policy_number,
            "client": task.client_name or "-",
            "status": "completed",
            "detail": detail,
        }, False
    except SmtpDeliveryUncertainError as exc:
        detail = f"ENTREGA INCIERTA: {exc}"
        delivery_steps.append(
            step(
                "send_renewal_email",
                "delivery_uncertain",
                started_at=datetime.utcnow(),
                error_message=detail,
            )
        )
        data["steps"] = [*(data.get("steps") or []), *delivery_steps]
        persist_result(
            run_id,
            task.id,
            data,
            retrieval_succeeded=True,
            delivery_succeeded=False,
            error=detail,
        )
        record_action(
            task=task,
            status="delivery_uncertain",
            output={
                "drive_folder_id": result.drive_folder_id,
                "error": detail,
                "whatsapp": {"enabled": False, "status": "skipped"},
            },
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        emit("task_uncertain", policy=task.policy_number, detail=detail)
        return {
            "policy": task.policy_number,
            "client": task.client_name or "-",
            "status": "delivery_uncertain",
            "detail": detail,
        }, False
    except Exception as exc:
        detail = str(exc)
        delivery_steps.append(
            step(
                "renewal_delivery",
                "failed",
                started_at=datetime.utcnow(),
                error_message=detail,
            )
        )
        data["steps"] = [*(data.get("steps") or []), *delivery_steps]
        persist_result(
            run_id,
            task.id,
            data,
            retrieval_succeeded=True,
            delivery_succeeded=False,
            renewal_status=(
                "Revision Manual Necesaria"
                if isinstance(exc, AgentContactResolutionError)
                else None
            ),
            error=detail,
        )
        record_action(
            task=task,
            status="failed",
            output={
                "drive_folder_id": result.drive_folder_id,
                "error": detail,
                "whatsapp": {"enabled": False, "status": "skipped"},
            },
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        emit("delivery_failed", policy=task.policy_number, detail=detail)
        return {
            "policy": task.policy_number,
            "client": task.client_name or "-",
            "status": "delivery_failed",
            "detail": detail,
        }, False


def process_one_subprocess(run_id: str, task_id: str) -> tuple[dict, bool]:
    return _process_one_subprocess(run_id, task_id, allow_chrome_restart=True)


def restart_persistent_chrome() -> None:
    subprocess.run(
        [
            "pkill",
            "-f",
            f"--remote-debugging-port={chrome_cdp_port()}",
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        if not chrome_server_ready():
            break
        time.sleep(0.25)
    ensure_persistent_chrome(stable_chrome_profile_dir())


def _process_one_subprocess(
    run_id: str,
    task_id: str,
    *,
    allow_chrome_restart: bool,
) -> tuple[dict, bool]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--process-task-run-id",
        run_id,
        "--process-task-id",
        task_id,
    ]
    completed = subprocess.run(
        command,
        cwd=str(REPOSITORY_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )
    result_payload = None
    for line in completed.stdout.splitlines():
        print(line, flush=True)
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if payload.get("event") == "process_task_result":
            result_payload = payload
    for line in completed.stderr.splitlines():
        print(line, file=sys.stderr, flush=True)
    if result_payload is None:
        detail = completed.stderr.strip() or completed.stdout.strip() or (
            f"Subproceso terminó con código {completed.returncode}"
        )
        item = {
            "policy": task_id,
            "client": "-",
            "status": "failed",
            "detail": detail,
        }
        portal_failure = True
    else:
        item = result_payload["item"]
        portal_failure = bool(result_payload["portal_failure"])
    if (
        allow_chrome_restart
        and item.get("status") == "failed"
        and "event loop is already running" in item.get("detail", "").lower()
    ):
        emit("task_retrying", task_id=task_id, reason="restart_persistent_chrome")
        undo_transient_retry_accounting(run_id)
        restart_persistent_chrome()
        return _process_one_subprocess(
            run_id,
            task_id,
            allow_chrome_restart=False,
        )
    return item, portal_failure


def execute_batch(now: datetime, *, limit: int | None = None) -> dict:
    cutoff = renewal_cutoff(now)
    tasks = selected_tasks(cutoff, process_date=now.date())
    if limit is not None:
        tasks = tasks[:limit]
    run_id = create_run(tasks, cutoff)
    send_internal_renewal_email(
        subject=f"Inicio renovaciones MetLife GMM - {now.date().isoformat()}",
        body=summary_body(
            "Inicia el proceso diario de renovaciones MetLife GMM.",
            tasks,
            now.date(),
        ),
    )
    emit(
        "batch_started",
        run_id=run_id,
        selected=len(tasks),
        cutoff_date=cutoff.isoformat(),
        whatsapp_enabled=WHATSAPP_ENABLED,
    )

    results: list[dict] = []
    consecutive_portal_failures = 0
    aborted = False
    for task in tasks:
        item, portal_failure = process_one_subprocess(run_id, task.id)
        results.append(item)
        consecutive_portal_failures = (
            consecutive_portal_failures + 1 if portal_failure else 0
        )
        detail_lower = item.get("detail", "").lower()
        if item["status"] == "failed" and (
            "mfa_required" in detail_lower
            or "operator_action_required" in detail_lower
        ):
            aborted = True
            emit("batch_aborted", reason=item["detail"])
            break
        if (
            consecutive_portal_failures
            >= max_consecutive_portal_failures()
        ):
            aborted = True
            emit(
                "batch_aborted",
                reason=(
                    "El portal de MetLife falló de forma consecutiva; "
                    "se abortó para evitar intentos innecesarios"
                ),
            )
            break

    return finish_run(
        run_id,
        results,
        aborted=aborted,
        process_date=now.date(),
    )


def run(
    *,
    force: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
) -> int:
    if limit is not None and limit < 1:
        raise ValueError("El límite debe ser mayor a cero")
    now = local_now()
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(".lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        due = force or should_run(now, state.get("last_started_date"))
        if dry_run:
            tasks = selected_tasks(
                renewal_cutoff(now),
                process_date=now.date(),
            )
            if limit is not None:
                tasks = tasks[:limit]
            print(
                json.dumps(
                    {
                        "due": due,
                        "now": now.isoformat(),
                        "scheduled_hour": scheduled_hour(),
                        "timezone": str(now.tzinfo),
                        "last_started_date": state.get("last_started_date"),
                        "cutoff_date": renewal_cutoff(now).isoformat(),
                        "selected_count": len(tasks),
                        "recipients": internal_recipients(),
                        "whatsapp_enabled": WHATSAPP_ENABLED,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if not due:
            return 0

        started_state = {
            **state,
            "last_started_date": now.date().isoformat(),
            "last_started_at": now.isoformat(),
            "status": "running",
            "whatsapp_enabled": WHATSAPP_ENABLED,
        }
        write_state(path, started_state)
        try:
            result = execute_batch(now, limit=limit)
        except Exception as exc:
            failed_state = {
                **started_state,
                "status": "failed",
                "failed_at": local_now().isoformat(),
                "error": str(exc),
            }
            write_state(path, failed_state)
            try:
                send_email_smtp(
                    subject=(
                        "ALERTA: Falló el proceso diario de renovaciones "
                        f"{now.date().isoformat()}"
                    ),
                    body=(
                        "Equipo,\n\n"
                        "El proceso diario de renovaciones falló y no se "
                        "reintentará automáticamente hoy para evitar duplicados.\n\n"
                        f"Detalle: {exc}\n\n"
                        "WhatsApp permaneció desactivado.\n\n"
                        "Saludos,\nTAIICO OS"
                    ),
                    recipients=internal_recipients(),
                    cc_recipients=[],
                )
            except Exception as alert_error:
                emit(
                    "alert_failed",
                    original_error=str(exc),
                    alert_error=str(alert_error),
                )
            raise

        write_state(
            path,
            {
                **started_state,
                "status": result["status"],
                "completed_at": local_now().isoformat(),
                "run_id": result["run_id"],
                "selected": result["selected"],
                "succeeded": result["succeeded"],
                "failed": result["failed"],
                "aborted": result["aborted"],
            },
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--process-task-run-id")
    parser.add_argument("--process-task-id")
    arguments = parser.parse_args()
    if arguments.process_task_run_id and arguments.process_task_id:
        item, portal_failure = process_one(
            arguments.process_task_run_id,
            arguments.process_task_id,
        )
        emit("process_task_result", item=item, portal_failure=portal_failure)
        return 0 if item.get("status") == "completed" else 1
    return run(
        force=arguments.force,
        dry_run=arguments.dry_run,
        limit=arguments.limit,
    )


if __name__ == "__main__":
    raise SystemExit(main())
