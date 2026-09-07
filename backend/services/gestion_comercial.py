from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func

from database import (
    Client,
    CommercialOpportunity,
    CommercialOpportunityQuote,
    CommercialOpportunityStageHistory,
    CommercialOpportunityTask,
    CommercialStage,
    CommercialStageTaskRule,
    Product,
    SessionLocal,
    Task,
    User,
)
from services.auth import AccessProfile
from services.authorization import current_access_profile, require_module_access


router = APIRouter(prefix="/gestion-comercial", tags=["gestion-comercial"])

DEFAULT_STAGES = (
    ("stage_prospecting", "prospecting", "Prospección", 1, Decimal("10")),
    ("stage_approach", "approach", "Acercamiento", 2, Decimal("20")),
    ("stage_needs", "needs_detection", "Detección de necesidades", 3, Decimal("35")),
    ("stage_solution", "solution_design", "Diseño de solución", 4, Decimal("50")),
    ("stage_presentation", "presentation", "Presentación de solución", 5, Decimal("65")),
    ("stage_closing", "closing", "Cierre", 6, Decimal("85")),
    ("stage_issuance", "issuance_payment", "Emisión / Pago", 7, Decimal("100")),
    ("stage_after_sales", "after_sales", "Postventa", 8, Decimal("100")),
)

DEFAULT_TASK_RULES = (
    (
        "rule_prepare_solution",
        "solution_design",
        "Preparar propuesta de solución",
        "Preparar y cargar la propuesta necesaria para que la oportunidad pueda avanzar.",
        "Responsable de propuestas",
        2,
    ),
    (
        "rule_prepare_presentation",
        "presentation",
        "Elaborar presentación comercial",
        "Preparar la presentación comercial vinculada con la oportunidad.",
        "Responsable de presentaciones",
        2,
    ),
)


class OpportunityCreate(BaseModel):
    client_id: str | None = None
    prospect_name: str | None = Field(default=None, max_length=255)
    product_id: str | None = None
    product_name: str = Field(min_length=1, max_length=255)
    business_line: str | None = Field(default=None, max_length=80)
    owner_agent_rfc: str = Field(min_length=1, max_length=50)
    owner_agent_name: str = Field(min_length=1, max_length=255)
    owner_promotoria: str = Field(min_length=1, max_length=100)
    potential_premium: Decimal = Field(default=Decimal("0"), ge=0)
    currency: str = Field(default="MXN", min_length=3, max_length=10)
    stage_code: str = Field(default="prospecting", max_length=80)
    priority: str = Field(default="medium", pattern="^(low|medium|high)$")
    source: str | None = Field(default=None, max_length=100)
    estimated_close_date: date | None = None
    detected_need: str | None = None
    description: str | None = None


class StageChangeRequest(BaseModel):
    stage_code: str = Field(min_length=1, max_length=80)
    reason: str | None = Field(default=None, max_length=2000)
    override_blocking_tasks: bool = False


class CommercialTaskUpdate(BaseModel):
    status: str = Field(pattern="^(pending|in_progress|completed)$")


def _add_business_days(start: datetime, days: int) -> datetime:
    result = start
    remaining = max(0, days)
    while remaining:
        result += timedelta(days=1)
        if result.weekday() < 5:
            remaining -= 1
    return result


def ensure_commercial_catalog(db) -> None:
    stages = {stage.code: stage for stage in db.query(CommercialStage).all()}
    for stage_id, code, name, position, rate in DEFAULT_STAGES:
        if code not in stages:
            stage = CommercialStage(
                id=stage_id,
                code=code,
                name=name,
                position=position,
                base_conversion_rate=rate,
                is_active=True,
                metadata_json={},
            )
            db.add(stage)
            stages[code] = stage
    db.flush()
    existing_rules = {rule.id for rule in db.query(CommercialStageTaskRule).all()}
    for rule_id, stage_code, title, description, role, sla in DEFAULT_TASK_RULES:
        if rule_id in existing_rules:
            continue
        db.add(CommercialStageTaskRule(
            id=rule_id,
            stage_id=stages[stage_code].id,
            title=title,
            description=description,
            responsible_role=role,
            sla_business_days=sla,
            is_required=True,
            blocks_stage_change=True,
            is_active=True,
        ))
    db.flush()


def _profile_can_access(profile: AccessProfile, opportunity: CommercialOpportunity) -> bool:
    if profile.is_central_admin:
        return True
    if profile.is_agent:
        return bool(profile.rfc) and profile.rfc.casefold() == opportunity.owner_agent_rfc.casefold()
    return opportunity.owner_promotoria.strip().upper() in set(profile.promotorias)


def _serialize_task(task: Task, link: CommercialOpportunityTask | None = None) -> dict:
    metadata = dict(task.metadata_json or {})
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description or "",
        "status": task.status,
        "priority": task.priority,
        "assigned_user_id": task.assigned_user_id,
        "assigned_to": task.assigned_user.email if task.assigned_user else "",
        "responsible_role": metadata.get("responsible_role", ""),
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "is_required": bool(metadata.get("is_required")),
        "blocks_stage_change": bool(metadata.get("blocks_stage_change")),
        "opportunity_id": link.opportunity_id if link else task.related_entity_id,
    }


def _opportunity_tasks(db, opportunity_id: str) -> list[tuple[Task, CommercialOpportunityTask]]:
    return (
        db.query(Task, CommercialOpportunityTask)
        .join(CommercialOpportunityTask, CommercialOpportunityTask.task_id == Task.id)
        .filter(CommercialOpportunityTask.opportunity_id == opportunity_id)
        .order_by(Task.created_at.desc())
        .all()
    )


def serialize_opportunity(db, opportunity: CommercialOpportunity) -> dict:
    quote_ids = [
        row.quote_id
        for row in db.query(CommercialOpportunityQuote)
        .filter(CommercialOpportunityQuote.opportunity_id == opportunity.id)
        .all()
    ]
    tasks = [_serialize_task(task, link) for task, link in _opportunity_tasks(db, opportunity.id)]
    rate = Decimal(str(opportunity.stage.base_conversion_rate or 0))
    expected = Decimal(str(opportunity.potential_premium or 0)) * rate / Decimal("100")
    return {
        "id": opportunity.id,
        "client_id": opportunity.client_id,
        "client_name": opportunity.client_name,
        "product_id": opportunity.product_id,
        "product_name": opportunity.product_name,
        "business_line": opportunity.business_line or "",
        "owner_agent_rfc": opportunity.owner_agent_rfc,
        "owner_agent_name": opportunity.owner_agent_name,
        "owner_promotoria": opportunity.owner_promotoria,
        "potential_premium": float(opportunity.potential_premium or 0),
        "currency": opportunity.currency,
        "stage": {
            "id": opportunity.stage.id,
            "code": opportunity.stage.code,
            "name": opportunity.stage.name,
            "position": opportunity.stage.position,
            "conversion_rate": float(rate),
        },
        "expected_value": float(expected),
        "status": opportunity.status,
        "priority": opportunity.priority,
        "source": opportunity.source or "",
        "estimated_close_date": opportunity.estimated_close_date.isoformat() if opportunity.estimated_close_date else None,
        "detected_need": opportunity.detected_need or "",
        "description": opportunity.description or "",
        "next_activity_at": opportunity.next_activity_at.isoformat() if opportunity.next_activity_at else None,
        "quote_ids": quote_ids,
        "tasks": tasks,
        "blocking_tasks": sum(1 for task in tasks if task["blocks_stage_change"] and task["status"] != "completed"),
        "created_at": opportunity.created_at.isoformat() if opportunity.created_at else None,
    }


def _create_stage_tasks(db, opportunity: CommercialOpportunity, history: CommercialOpportunityStageHistory) -> list[Task]:
    rules = (
        db.query(CommercialStageTaskRule)
        .filter(
            CommercialStageTaskRule.stage_id == opportunity.stage_id,
            CommercialStageTaskRule.is_active.is_(True),
        )
        .all()
    )
    created = []
    for rule in rules:
        exists = db.query(CommercialOpportunityTask).filter(
            CommercialOpportunityTask.stage_history_id == history.id,
            CommercialOpportunityTask.rule_id == rule.id,
        ).first()
        if exists:
            continue
        task = Task(
            title=rule.title,
            description=rule.description,
            status="pending",
            priority="high" if rule.blocks_stage_change else "medium",
            assigned_user_id=rule.assigned_user_id,
            related_entity_type="commercial_opportunity",
            related_entity_id=opportunity.id,
            due_date=_add_business_days(datetime.utcnow(), rule.sla_business_days),
            metadata_json={
                "responsible_role": rule.responsible_role,
                "is_required": rule.is_required,
                "blocks_stage_change": rule.blocks_stage_change,
                "stage_code": opportunity.stage.code,
            },
        )
        db.add(task)
        db.flush()
        db.add(CommercialOpportunityTask(
            opportunity_id=opportunity.id,
            stage_history_id=history.id,
            rule_id=rule.id,
            task_id=task.id,
        ))
        created.append(task)
    return created


def create_opportunity_record(db, payload: OpportunityCreate, actor: str) -> CommercialOpportunity:
    ensure_commercial_catalog(db)
    client = db.query(Client).filter(Client.id == payload.client_id).first() if payload.client_id else None
    if payload.client_id and not client:
        raise ValueError("El cliente seleccionado ya no existe")
    client_name = (client.full_name if client else payload.prospect_name or "").strip()
    if len(client_name) < 2:
        raise ValueError("Selecciona un cliente o captura el nombre del prospecto")
    product = db.query(Product).filter(Product.id == payload.product_id).first() if payload.product_id else None
    stage = db.query(CommercialStage).filter(CommercialStage.code == payload.stage_code).first()
    if not stage:
        raise ValueError("La etapa comercial no existe")
    opportunity = CommercialOpportunity(
        client_id=client.id if client else None,
        client_name=client_name,
        product_id=product.id if product else None,
        product_name=(product.name if product else payload.product_name).strip(),
        business_line=(payload.business_line or "").strip() or None,
        owner_agent_rfc=payload.owner_agent_rfc.strip().upper(),
        owner_agent_name=payload.owner_agent_name.strip(),
        owner_promotoria=payload.owner_promotoria.strip().upper(),
        potential_premium=payload.potential_premium,
        currency=payload.currency.strip().upper(),
        stage_id=stage.id,
        status="active",
        priority=payload.priority,
        source=(payload.source or "").strip() or None,
        estimated_close_date=payload.estimated_close_date,
        detected_need=(payload.detected_need or "").strip() or None,
        description=(payload.description or "").strip() or None,
        created_by=actor,
    )
    db.add(opportunity)
    db.flush()
    history = CommercialOpportunityStageHistory(
        opportunity_id=opportunity.id,
        stage_id=stage.id,
        changed_by=actor,
        reason="Creación de oportunidad",
        metadata_json={},
    )
    db.add(history)
    db.flush()
    _create_stage_tasks(db, opportunity, history)
    return opportunity


def _blocking_tasks(db, opportunity: CommercialOpportunity) -> list[Task]:
    return [
        task for task, _link in _opportunity_tasks(db, opportunity.id)
        if task.status != "completed" and bool((task.metadata_json or {}).get("blocks_stage_change"))
    ]


def move_opportunity_stage(
    db,
    opportunity: CommercialOpportunity,
    target: CommercialStage,
    *,
    actor: str,
    reason: str | None = None,
    override: bool = False,
) -> CommercialOpportunity:
    if opportunity.stage_id == target.id:
        return opportunity
    blockers = _blocking_tasks(db, opportunity)
    if blockers and not override:
        raise ValueError("La oportunidad tiene pendientes obligatorios abiertos: " + ", ".join(task.title for task in blockers))
    current_history = (
        db.query(CommercialOpportunityStageHistory)
        .filter(
            CommercialOpportunityStageHistory.opportunity_id == opportunity.id,
            CommercialOpportunityStageHistory.exited_at.is_(None),
        )
        .order_by(CommercialOpportunityStageHistory.entered_at.desc())
        .first()
    )
    if current_history:
        current_history.exited_at = datetime.utcnow()
    opportunity.stage_id = target.id
    history = CommercialOpportunityStageHistory(
        opportunity_id=opportunity.id,
        stage_id=target.id,
        changed_by=actor,
        reason=reason,
        metadata_json={"override": bool(override), "blocking_task_ids": [task.id for task in blockers]},
    )
    db.add(history)
    db.flush()
    _create_stage_tasks(db, opportunity, history)
    return opportunity


def ensure_opportunity_for_quote(
    quote: dict[str, str],
    *,
    actor: str,
    agent_rfc: str,
    client_id: str | None = None,
) -> str:
    db = SessionLocal()
    try:
        ensure_commercial_catalog(db)
        link = db.query(CommercialOpportunityQuote).filter(CommercialOpportunityQuote.quote_id == quote["id"]).first()
        if link:
            return link.opportunity_id
        client = db.query(Client).filter(Client.id == client_id).first() if client_id else None
        if not client and quote.get("rfc"):
            client = db.query(Client).filter(func.upper(Client.rfc) == quote["rfc"].strip().upper()).first()
        payload = OpportunityCreate(
            client_id=client.id if client else None,
            prospect_name=None if client else quote.get("cliente") or "Prospecto",
            product_name=quote.get("producto") or "Producto por definir",
            business_line=quote.get("ramo") or None,
            owner_agent_rfc=agent_rfc or quote.get("clave_agente") or "SIN-RFC",
            owner_agent_name=quote.get("agente") or "Agente por definir",
            owner_promotoria=quote.get("promotoria") or "TAIICO",
            stage_code="solution_design",
            source="Cotizaciones",
        )
        opportunity = create_opportunity_record(db, payload, actor)
        db.add(CommercialOpportunityQuote(opportunity_id=opportunity.id, quote_id=quote["id"]))
        db.commit()
        return opportunity.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def opportunity_id_for_quote(quote_id: str) -> str | None:
    db = SessionLocal()
    try:
        link = db.query(CommercialOpportunityQuote).filter(CommercialOpportunityQuote.quote_id == quote_id).first()
        return link.opportunity_id if link else None
    finally:
        db.close()


def opportunity_ids_for_quotes(quote_ids: list[str]) -> dict[str, str]:
    normalized_ids = [str(quote_id or "").strip() for quote_id in quote_ids if str(quote_id or "").strip()]
    if not normalized_ids:
        return {}
    db = SessionLocal()
    try:
        return {
            row.quote_id: row.opportunity_id
            for row in db.query(CommercialOpportunityQuote)
            .filter(CommercialOpportunityQuote.quote_id.in_(normalized_ids))
            .all()
        }
    finally:
        db.close()


def advance_opportunity_for_quote(quote_id: str, stage_code: str, *, actor: str) -> str | None:
    db = SessionLocal()
    try:
        ensure_commercial_catalog(db)
        link = db.query(CommercialOpportunityQuote).filter(CommercialOpportunityQuote.quote_id == quote_id).first()
        if not link:
            return None
        opportunity = db.query(CommercialOpportunity).filter(CommercialOpportunity.id == link.opportunity_id).first()
        target = db.query(CommercialStage).filter(CommercialStage.code == stage_code).first()
        if not opportunity or not target or opportunity.stage.position >= target.position:
            return opportunity.id if opportunity else None
        # A real quote event is evidence that the work required in the prior
        # stage was completed; close those generated tasks before advancing.
        for task in _blocking_tasks(db, opportunity):
            task.status = "completed"
            task.completed_at = datetime.utcnow()
        move_opportunity_stage(db, opportunity, target, actor=actor, reason=f"Evento de cotización: {stage_code}")
        db.commit()
        return opportunity.id
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("")
def get_commercial_pipeline(profile: AccessProfile = Depends(current_access_profile)):
    db = SessionLocal()
    try:
        ensure_commercial_catalog(db)
        db.commit()
        stages = db.query(CommercialStage).filter(CommercialStage.is_active.is_(True)).order_by(CommercialStage.position).all()
        opportunities = [
            opportunity for opportunity in db.query(CommercialOpportunity).all()
            if _profile_can_access(profile, opportunity)
        ]
        serialized = [serialize_opportunity(db, opportunity) for opportunity in opportunities]
        active = [item for item in serialized if item["status"] == "active"]
        paid = sum(float(opportunity.paid_premium or 0) for opportunity in opportunities)
        potential = sum(item["potential_premium"] for item in active)
        expected = sum(item["expected_value"] for item in active)
        return {
            "stages": [{
                "id": stage.id,
                "code": stage.code,
                "name": stage.name,
                "position": stage.position,
                "conversion_rate": float(stage.base_conversion_rate or 0),
            } for stage in stages],
            "opportunities": serialized,
            "summary": {
                "paid_sales": paid,
                "potential_funnel": potential,
                "expected_funnel": expected,
                "projection": paid + expected,
                "active_opportunities": len(active),
            },
        }
    finally:
        db.close()


@router.get("/config")
def get_commercial_config(profile: AccessProfile = Depends(current_access_profile)):
    from services.cotizaciones import agents_for_profile

    db = SessionLocal()
    try:
        ensure_commercial_catalog(db)
        db.commit()
        return {
            "agents": agents_for_profile(profile),
            "products": [{"id": product.id, "name": product.name, "branch": product.branch} for product in db.query(Product).order_by(Product.branch, Product.name).all()],
            "can_operate": profile.can_operate("gestion_comercial"),
        }
    finally:
        db.close()


@router.post("/opportunities", status_code=201)
def create_opportunity(
    payload: OpportunityCreate,
    profile: AccessProfile = Depends(require_module_access("gestion_comercial", operation=True)),
):
    from services.cotizaciones import assigned_agent

    db = SessionLocal()
    try:
        agent = assigned_agent(profile, payload.owner_agent_rfc, payload.owner_promotoria)
        validated_payload = payload.model_copy(update={
            "owner_agent_rfc": agent["rfc"],
            "owner_agent_name": agent["name"],
            "owner_promotoria": agent["promotoria"],
        })
        opportunity = create_opportunity_record(db, validated_payload, profile.username)
        db.commit()
        db.refresh(opportunity)
        return {"opportunity": serialize_opportunity(db, opportunity)}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.patch("/opportunities/{opportunity_id}/stage")
def change_opportunity_stage(
    opportunity_id: str,
    payload: StageChangeRequest,
    profile: AccessProfile = Depends(require_module_access("gestion_comercial", operation=True)),
):
    db = SessionLocal()
    try:
        opportunity = db.query(CommercialOpportunity).filter(CommercialOpportunity.id == opportunity_id).first()
        target = db.query(CommercialStage).filter(CommercialStage.code == payload.stage_code).first()
        if not opportunity or not _profile_can_access(profile, opportunity):
            raise HTTPException(status_code=404, detail="Oportunidad no encontrada")
        if not target:
            raise HTTPException(status_code=422, detail="Etapa no válida")
        if payload.override_blocking_tasks and not profile.is_admin:
            raise HTTPException(status_code=403, detail="Sólo un administrador puede omitir pendientes obligatorios")
        if payload.override_blocking_tasks and not (payload.reason or "").strip():
            raise HTTPException(status_code=422, detail="Captura el motivo del override")
        move_opportunity_stage(
            db,
            opportunity,
            target,
            actor=profile.username,
            reason=(payload.reason or "").strip() or None,
            override=payload.override_blocking_tasks,
        )
        db.commit()
        db.refresh(opportunity)
        return {"opportunity": serialize_opportunity(db, opportunity)}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    finally:
        db.close()


def list_commercial_pending(profile: AccessProfile) -> dict:
    db = SessionLocal()
    try:
        query = (
            db.query(Task, CommercialOpportunityTask, CommercialOpportunity)
            .join(CommercialOpportunityTask, CommercialOpportunityTask.task_id == Task.id)
            .join(CommercialOpportunity, CommercialOpportunity.id == CommercialOpportunityTask.opportunity_id)
        )
        rows = []
        for task, link, opportunity in query.order_by(Task.due_date).all():
            if not _profile_can_access(profile, opportunity) and not (
                task.assigned_user and task.assigned_user.email.casefold() == profile.username.casefold()
            ):
                continue
            rows.append({
                **_serialize_task(task, link),
                "client_name": opportunity.client_name,
                "product_name": opportunity.product_name,
                "stage_name": opportunity.stage.name,
                "owner_agent_name": opportunity.owner_agent_name,
                "owner_promotoria": opportunity.owner_promotoria,
            })
        return {"source": "commercial", "title": "Comerciales", "rows": rows}
    finally:
        db.close()


def update_commercial_task(task_id: str, status: str, profile: AccessProfile) -> dict:
    db = SessionLocal()
    try:
        row = (
            db.query(Task, CommercialOpportunityTask, CommercialOpportunity)
            .join(CommercialOpportunityTask, CommercialOpportunityTask.task_id == Task.id)
            .join(CommercialOpportunity, CommercialOpportunity.id == CommercialOpportunityTask.opportunity_id)
            .filter(Task.id == task_id)
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Pendiente comercial no encontrado")
        task, link, opportunity = row
        assigned_to_profile = task.assigned_user and task.assigned_user.email.casefold() == profile.username.casefold()
        if not assigned_to_profile and not profile.is_admin:
            raise HTTPException(status_code=403, detail="No puedes actualizar este pendiente")
        task.status = status
        task.completed_at = datetime.utcnow() if status == "completed" else None
        db.commit()
        return {
            **_serialize_task(task, link),
            "client_name": opportunity.client_name,
            "product_name": opportunity.product_name,
            "stage_name": opportunity.stage.name,
            "owner_agent_name": opportunity.owner_agent_name,
            "owner_promotoria": opportunity.owner_promotoria,
        }
    finally:
        db.close()
