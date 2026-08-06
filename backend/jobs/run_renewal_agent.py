from __future__ import annotations

import argparse
import fcntl
import json
import mimetypes
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env", override=True)

from adapters.metlife_gmm_portal import (  # noqa: E402
    MetLifeGmmPortalAdapter,
    MetLifeGmmPortalTask,
    result_to_dict,
)
from database import (  # noqa: E402
    AgentAction,
    PolicyDocumentRetrievalRun,
    PolicyDocumentRetrievalTask,
    SessionLocal,
)
from services.client_email_directory import lookup_client_email  # noqa: E402
from services.renovaciones import (  # noqa: E402
    SmtpDeliveryUncertainError,
    build_metlife_gmm_renewal_email_body,
    persist_adapter_steps,
    renewal_email_cc_recipients,
    renewal_email_recipients,
    send_email_smtp,
)


DEFAULT_TIMEZONE = "America/Mexico_City"
DEFAULT_HOUR = 9
DEFAULT_WINDOW_DAYS = 30
DEFAULT_MAX_CONSECUTIVE_PORTAL_FAILURES = 7
DEFAULT_TARGET_DRIVE_FOLDER_ID = "1UthkPpr5_pvX5SszrCuIm546XKZh4Z_R"
DEFAULT_INTERNAL_RECIPIENTS = (
    "alberto.alfaro@taiico.com,"
    "pamela.alfaro@taiico.com,"
    "veronica.alfaro@taiico.com"
)
MAX_ATTACHMENT_BYTES = 18 * 1024 * 1024
MAX_ATTACHMENT_COUNT = 100

# This daily job intentionally has no WhatsApp dependency. Re-enabling WhatsApp
# requires an explicit code change and review, not merely refreshing a token.
WHATSAPP_ENABLED = False


def emit(event: str, **payload) -> None:
    print(json.dumps({"event": event, **payload}, ensure_ascii=False), flush=True)


def local_now() -> datetime:
    timezone = ZoneInfo(
        os.getenv("RENEWAL_AGENT_AUTOMATION_TIMEZONE", DEFAULT_TIMEZONE)
    )
    return datetime.now(timezone)


def scheduled_hour() -> int:
    return int(
        os.getenv("RENEWAL_AGENT_AUTOMATION_HOUR", str(DEFAULT_HOUR))
    )


def window_days() -> int:
    return int(
        os.getenv(
            "RENEWAL_AGENT_AUTOMATION_WINDOW_DAYS",
            str(DEFAULT_WINDOW_DAYS),
        )
    )


def should_run(now: datetime, last_started_date: str | None) -> bool:
    return (
        now.hour >= scheduled_hour()
        and last_started_date != now.date().isoformat()
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
    configured = os.getenv(
        "RENEWAL_AGENT_AUTOMATION_RECIPIENTS",
        DEFAULT_INTERNAL_RECIPIENTS,
    )
    result: list[str] = []
    seen: set[str] = set()
    for value in configured.split(","):
        email = value.strip()
        normalized = email.casefold()
        if email and normalized not in seen:
            result.append(email)
            seen.add(normalized)
    return result


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
                PolicyDocumentRetrievalTask.status == "queued",
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
        for task in tasks:
            db.expunge(task)
        eligible_tasks = [
            task for task in tasks if task.id not in protected_task_ids
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
            adapter_name="metlife_gmm_portal",
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
            task.status = "retrieved"
            task.document_status = "retrieved"
            task.expediente_link = result_data.get("drive_folder_link")
            task.target_drive_folder_id = result_data.get("drive_folder_id")
            task.target_drive_folder_path = result_data.get("drive_folder_link")
            task.retrieval_adapter = "metlife_gmm_portal"
            task.completed_at = datetime.utcnow()
            task.last_error = error
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
    send_email_smtp(
        subject=(
            f"{subject_prefix}Cierre renovaciones MetLife GMM - "
            f"{process_date.isoformat()}"
        ),
        body="\n".join(lines),
        recipients=internal_recipients(),
        cc_recipients=[],
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
    adapter = MetLifeGmmPortalAdapter(headless=False)
    result = adapter.run(
        MetLifeGmmPortalTask(
            id=task.id,
            policy_number=task.policy_number,
            rfc=task.rfc or "",
            client_name=task.client_name,
            renewal_deadline=task.renewal_deadline,
        ),
        stop_after="upload_to_drive",
        upload_to_drive=True,
        target_drive_folder_id=target_drive_folder_id(),
    )
    data = result_to_dict(result)
    if result.status != "completed":
        detail = result.error_message or result.status
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
            output={"adapter_result": result.status, "error": detail},
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        emit("task_failed", policy=task.policy_number, detail=detail)
        return {
            "policy": task.policy_number,
            "client": task.client_name or "-",
            "status": "failed",
            "detail": detail,
        }, is_portal_failure(data)

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
        if not client_email:
            raise RuntimeError(
                "No se encontró un correo único del cliente en la base canónica"
            )
        recipients = renewal_email_recipients(client_email)
        if recipients != [client_email]:
            raise RuntimeError(
                "La configuración de correo no está habilitada para el cliente real"
            )
        delivery_steps.append(
            step(
                "resolve_client_email",
                "completed",
                started_at=step_started,
                metadata={"client_email": client_email},
            )
        )

        email_body = build_metlife_gmm_renewal_email_body(
            task.client_name or "Cliente",
            client_email,
            task.policy_number,
            task.renewal_deadline.isoformat(),
        )
        period_start = task.renewal_deadline.year
        step_started = datetime.utcnow()
        cc_recipients = renewal_email_cc_recipients(recipients)
        send_email_smtp(
            subject=(
                f"Renovación MetLife GMM - {task.client_name} - "
                f"{period_start} - {period_start + 1}"
            ),
            body=email_body,
            recipients=recipients,
            attachments=attachments,
            cc_recipients=cc_recipients,
        )
        delivery_steps.append(
            step(
                "send_client_email",
                "completed",
                started_at=step_started,
                metadata={
                    "recipient": client_email,
                    "cc_recipients": cc_recipients,
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
        )
        output = {
            "drive_folder_id": result.drive_folder_id,
            "drive_folder_link": result.drive_folder_link,
            "client_email": client_email,
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
            f"Correo a {client_email}; {len(attachments)} adjuntos; "
            "WhatsApp omitido"
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
                "send_client_email",
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


def execute_batch(now: datetime) -> dict:
    cutoff = renewal_cutoff(now)
    tasks = selected_tasks(cutoff, process_date=now.date())
    run_id = create_run(tasks, cutoff)
    send_email_smtp(
        subject=f"Inicio renovaciones MetLife GMM - {now.date().isoformat()}",
        body=summary_body(
            "Inicia el proceso diario de renovaciones MetLife GMM.", tasks, now.date()
        ),
        recipients=internal_recipients(),
        cc_recipients=[],
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
        item, portal_failure = process_one(run_id, task.id)
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


def run(*, force: bool = False, dry_run: bool = False) -> int:
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
            result = execute_batch(now)
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
    arguments = parser.parse_args()
    return run(force=arguments.force, dry_run=arguments.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
