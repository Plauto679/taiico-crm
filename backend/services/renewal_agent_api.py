from __future__ import annotations

import hmac
import os
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from database import AgentAction, PolicyDocumentRetrievalTask, SessionLocal


router = APIRouter(prefix="/renewal-agent", tags=["renewal-agent"])

TAIICO_AGENT_CODES = frozenset({"16200", "18412", "73640"})
DEFAULT_WINDOW_DAYS = 30
PROCESS_TIMEZONE = ZoneInfo("America/Mexico_City")
ALLOWED_CLAIM_STATUSES = frozenset({"queued"})
ALLOWED_COLLECTION_STATUSES = frozenset({"claimed", "collection_blocked"})
ALLOWED_APPROVAL_STATUSES = frozenset({"collection_approved"})


class ClaimRequest(BaseModel):
    worker_id: str = Field(min_length=1, max_length=100)


class CollectionCheckRequest(BaseModel):
    paid_until: date
    payment_status: str | None = Field(default=None, max_length=100)
    checked_at: datetime | None = None
    evidence: str | None = Field(default=None, max_length=2000)


class ApprovalRequest(BaseModel):
    reviewed_by: str = Field(min_length=3, max_length=320)
    note: str | None = Field(default=None, max_length=1000)


def require_service_token(
    authorization: str | None = Header(default=None),
) -> str:
    expected = os.getenv("RENEWAL_AGENT_API_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Renewal agent API is not configured",
        )
    scheme, _, supplied = (authorization or "").partition(" ")
    if scheme.casefold() != "bearer" or not hmac.compare_digest(
        supplied.strip(), expected
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid service token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "renewal_agent_service"


def _agent_code(task: PolicyDocumentRetrievalTask) -> str:
    payload = task.normalized_payload or {}
    value = payload.get("agent_code")
    if value is None:
        value = (task.source_payload or {}).get("AGENTE")
    text = str(value or "").strip()
    return text[:-2] if text.endswith(".0") else text


def _task_payload(task: PolicyDocumentRetrievalTask) -> dict:
    normalized = task.normalized_payload or {}
    return {
        "id": task.id,
        "status": task.status,
        "insurer_id": task.insurer_id,
        "product_branch": task.product_branch,
        "policy_number": task.policy_number,
        "original_policy_number": task.original_policy_number,
        "client_name": task.client_name,
        "rfc": task.rfc,
        "finivig": normalized.get("effective_start_date"),
        "ffinvig": task.renewal_deadline.isoformat(),
        "agent_code": _agent_code(task),
        "agent_name": normalized.get("agent_name"),
        "promotoria": normalized.get("promotoria"),
        "days_until_renewal": task.days_until_renewal,
        "priority": task.priority,
        "attempt_count": task.attempt_count,
    }


def _record_action(
    db,
    *,
    task: PolicyDocumentRetrievalTask,
    action_type: str,
    action_status: str,
    input_payload: dict,
    output_payload: dict,
) -> AgentAction:
    action = AgentAction(
        agent_name="renewal_agent_api",
        action_type=action_type,
        status=action_status,
        description=f"{action_type} for MetLife policy {task.policy_number}",
        input_payload={"task_id": task.id, **input_payload},
        output_payload=output_payload,
    )
    db.add(action)
    return action


def _get_taiico_task(db, task_id: str) -> PolicyDocumentRetrievalTask:
    task = db.get(PolicyDocumentRetrievalTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Renewal task not found")
    if (
        task.insurer_id != "metlife"
        or task.product_branch != "GMM"
        or _agent_code(task) not in TAIICO_AGENT_CODES
    ):
        raise HTTPException(status_code=403, detail="Task is outside TAIICO scope")
    return task


def _process_date() -> date:
    return datetime.now(PROCESS_TIMEZONE).date()


@router.get("/candidates", dependencies=[Depends(require_service_token)])
def candidates(
    task_status: Literal["queued", "claimed", "collection_approved", "approved"] = Query(
        default="queued", alias="status"
    ),
    days: int = Query(default=DEFAULT_WINDOW_DAYS, ge=0, le=30),
    limit: int = Query(default=25, ge=1, le=100),
):
    today = _process_date()
    cutoff = today + timedelta(days=days)
    db = SessionLocal()
    try:
        tasks = (
            db.query(PolicyDocumentRetrievalTask)
            .filter(
                PolicyDocumentRetrievalTask.insurer_id == "metlife",
                PolicyDocumentRetrievalTask.product_branch == "GMM",
                PolicyDocumentRetrievalTask.status == task_status,
                PolicyDocumentRetrievalTask.renewal_deadline <= cutoff,
            )
            .order_by(
                PolicyDocumentRetrievalTask.renewal_deadline.asc(),
                PolicyDocumentRetrievalTask.priority.asc(),
                PolicyDocumentRetrievalTask.policy_number.asc(),
            )
            .all()
        )
        scoped = [task for task in tasks if _agent_code(task) in TAIICO_AGENT_CODES]
        scoped = scoped[:limit]
        return {
            "count": len(scoped),
            "process_date": today.isoformat(),
            "cutoff_date": cutoff.isoformat(),
            "agent_codes": sorted(TAIICO_AGENT_CODES),
            "tasks": [_task_payload(task) for task in scoped],
        }
    finally:
        db.close()


@router.post("/tasks/{task_id}/claim", dependencies=[Depends(require_service_token)])
def claim_task(task_id: str, payload: ClaimRequest):
    db = SessionLocal()
    try:
        task = _get_taiico_task(db, task_id)
        if task.status not in ALLOWED_CLAIM_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=f"Task cannot be claimed from status {task.status}",
            )
        updated = (
            db.query(PolicyDocumentRetrievalTask)
            .filter(
                PolicyDocumentRetrievalTask.id == task.id,
                PolicyDocumentRetrievalTask.status == "queued",
            )
            .update(
                {
                    PolicyDocumentRetrievalTask.status: "claimed",
                    PolicyDocumentRetrievalTask.updated_at: datetime.utcnow(),
                },
                synchronize_session=False,
            )
        )
        if updated != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="Task was claimed concurrently")
        task.status = "claimed"
        action = _record_action(
            db,
            task=task,
            action_type="renewal_claim",
            action_status="completed",
            input_payload={"worker_id": payload.worker_id},
            output_payload={"status": "claimed"},
        )
        db.commit()
        return {"task": _task_payload(task), "action_id": action.id}
    finally:
        db.close()


@router.post(
    "/tasks/{task_id}/collection-check",
    dependencies=[Depends(require_service_token)],
)
def record_collection_check(task_id: str, payload: CollectionCheckRequest):
    db = SessionLocal()
    try:
        task = _get_taiico_task(db, task_id)
        if task.status not in ALLOWED_COLLECTION_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=f"Collection check is not allowed from status {task.status}",
            )
        eligible = payload.paid_until >= task.renewal_deadline
        next_status = "collection_approved" if eligible else "collection_blocked"
        checked_at = payload.checked_at or datetime.utcnow()
        task.status = next_status
        task.updated_at = datetime.utcnow()
        action = _record_action(
            db,
            task=task,
            action_type="renewal_collection_check",
            action_status="completed",
            input_payload={
                "paid_until": payload.paid_until.isoformat(),
                "payment_status": payload.payment_status,
                "checked_at": checked_at.isoformat(),
                "evidence": payload.evidence,
            },
            output_payload={
                "ffinvig": task.renewal_deadline.isoformat(),
                "eligible": eligible,
                "status": next_status,
            },
        )
        db.commit()
        return {
            "task": _task_payload(task),
            "collection": {
                "paid_until": payload.paid_until.isoformat(),
                "ffinvig": task.renewal_deadline.isoformat(),
                "eligible": eligible,
                "checked_at": checked_at.isoformat(),
            },
            "action_id": action.id,
        }
    finally:
        db.close()


@router.post("/tasks/{task_id}/approve", dependencies=[Depends(require_service_token)])
def approve_task(task_id: str, payload: ApprovalRequest):
    db = SessionLocal()
    try:
        task = _get_taiico_task(db, task_id)
        if task.status not in ALLOWED_APPROVAL_STATUSES:
            raise HTTPException(
                status_code=409,
                detail=f"Task cannot be approved from status {task.status}",
            )
        task.status = "approved"
        task.updated_at = datetime.utcnow()
        action = _record_action(
            db,
            task=task,
            action_type="renewal_human_approval",
            action_status="completed",
            input_payload={
                "reviewed_by": payload.reviewed_by.strip().casefold(),
                "note": payload.note,
            },
            output_payload={"status": "approved"},
        )
        db.commit()
        return {"task": _task_payload(task), "action_id": action.id}
    finally:
        db.close()
