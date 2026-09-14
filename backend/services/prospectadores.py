from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

from database import Client, Policy, PolicyProspectorAssignment, Prospector, SessionLocal
from services.authorization import require_module_access
from services.auth import AccessProfile
from services.prospector_merge import merge_prospectors


router = APIRouter(prefix="/prospectadores", tags=["prospectadores"])


def normalize_name(value: object) -> str:
    text = " ".join(str(value or "").strip().split()).upper()
    return "".join(
        character for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )


def normalize_rfc(value: object) -> str | None:
    text = re.sub(r"[^A-Z0-9&Ñ]", "", str(value or "").strip().upper())
    return text or None


def normalize_rate(value: object) -> Decimal:
    rate = Decimal(str(value or 0))
    if rate > 1:
        rate /= Decimal("100")
    if rate < 0 or rate > 1:
        raise ValueError("El porcentaje debe estar entre 0% y 100%")
    return rate.quantize(Decimal("0.000001"))


def first_anniversary(start: date) -> date:
    try:
        return start.replace(year=start.year + 1)
    except ValueError:
        return start.replace(year=start.year + 1, day=28)


def _date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def _prospector_text(policy: Policy) -> str:
    policy_metadata = policy.metadata_json if isinstance(policy.metadata_json, dict) else {}
    client_metadata = policy.client.metadata_json if policy.client and isinstance(policy.client.metadata_json, dict) else {}
    return " ".join(str(
        policy_metadata.get("prospector")
        or policy_metadata.get("prospectador")
        or client_metadata.get("prospectador")
        or client_metadata.get("prospector")
        or ""
    ).strip().split())


def parse_split_prospectors(value: str) -> list[tuple[str, Decimal]]:
    if value.count("%") < 2:
        return []
    before = re.findall(r"(\d+(?:[.,]\d+)?)\s*%\s*([^,;|]+)", value)
    matches = [(name.strip(" ,-"), normalize_rate(number.replace(",", "."))) for number, name in before]
    if len(matches) < 2:
        after = re.findall(r"([^,;|%\d]+?)\s+(\d+(?:[.,]\d+)?)\s*%", value)
        matches = [(name.strip(" ,-"), normalize_rate(number.replace(",", "."))) for name, number in after]
    matches = [(name, rate) for name, rate in matches if normalize_name(name)]
    if len(matches) < 2 or sum((rate for _, rate in matches), Decimal("0")) > 1:
        return []
    return matches


class ProspectorPayload(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    rfc: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=320)
    additional_emails: list[str] = Field(default_factory=list)
    payment_scheme: str = "factura"
    is_active: bool = True
    linked_username: str | None = Field(default=None, max_length=320)

    @field_validator("payment_scheme")
    @classmethod
    def payment_scheme_allowed(cls, value: str) -> str:
        value = value.strip().casefold().replace(" ", "_")
        if value not in {"factura", "asimilados_salarios"}:
            raise ValueError("El esquema debe ser factura o asimilados a salarios")
        return value


class AssignmentPayload(BaseModel):
    policy_id: str
    prospector_id: str
    commission_percentage: Decimal = Field(ge=0, le=100)
    effective_from: date
    effective_to: date | None = None


class MergePayload(BaseModel):
    target_id: str = Field(min_length=1, max_length=36)


def _serialize_prospector(row: Prospector, assignment_count: int = 0) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "rfc": row.rfc or "",
        "email": row.email or "",
        "additional_emails": row.additional_emails or [],
        "payment_scheme": row.payment_scheme,
        "invoice_required": row.invoice_required,
        "is_active": row.is_active,
        "linked_username": row.linked_username or "",
        "assignment_count": int(assignment_count or 0),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("")
def list_prospectors(search: str = ""):
    db = SessionLocal()
    try:
        count_query = (
            db.query(PolicyProspectorAssignment.prospector_id, func.count(PolicyProspectorAssignment.id).label("count"))
            .filter(PolicyProspectorAssignment.is_active.is_(True))
            .group_by(PolicyProspectorAssignment.prospector_id)
            .subquery()
        )
        query = db.query(Prospector, count_query.c.count).outerjoin(
            count_query, count_query.c.prospector_id == Prospector.id
        )
        term = search.strip()
        if term:
            like = f"%{term}%"
            query = query.filter(or_(Prospector.name.ilike(like), Prospector.rfc.ilike(like), Prospector.email.ilike(like)))
        rows = query.order_by(Prospector.is_active.desc(), Prospector.name).all()
        return {"prospectors": [_serialize_prospector(row, count) for row, count in rows]}
    finally:
        db.close()


@router.get("/summary")
def prospector_summary():
    db = SessionLocal()
    try:
        return {
            "total": db.query(Prospector).count(),
            "active": db.query(Prospector).filter(Prospector.is_active.is_(True)).count(),
            "with_assignments": db.query(func.count(func.distinct(PolicyProspectorAssignment.prospector_id))).filter(
                PolicyProspectorAssignment.is_active.is_(True)
            ).scalar() or 0,
            "active_assignments": db.query(PolicyProspectorAssignment).filter(
                PolicyProspectorAssignment.is_active.is_(True)
            ).count(),
        }
    finally:
        db.close()


@router.post("", status_code=201)
def create_prospector(payload: ProspectorPayload, profile: AccessProfile = Depends(require_module_access("prospectadores", operation=True))):
    db = SessionLocal()
    try:
        rfc = normalize_rfc(payload.rfc)
        if rfc and db.query(Prospector).filter(Prospector.rfc == rfc).first():
            raise HTTPException(status_code=409, detail="Ya existe un prospectador con ese RFC")
        row = Prospector(
            name=" ".join(payload.name.strip().split()), normalized_name=normalize_name(payload.name), rfc=rfc,
            email=(payload.email or "").strip().casefold() or None,
            additional_emails=sorted({email.strip().casefold() for email in payload.additional_emails if email.strip()}),
            payment_scheme=payload.payment_scheme,
            invoice_required=payload.payment_scheme == "factura",
            is_active=payload.is_active,
            linked_username=(payload.linked_username or "").strip().casefold() or None,
            created_by=profile.username,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"prospector": _serialize_prospector(row)}
    finally:
        db.close()


@router.put("/{prospector_id}")
def update_prospector(prospector_id: str, payload: ProspectorPayload, profile: AccessProfile = Depends(require_module_access("prospectadores", operation=True))):
    db = SessionLocal()
    try:
        row = db.query(Prospector).filter(Prospector.id == prospector_id).first()
        if not row:
            raise HTTPException(status_code=404, detail="Prospectador no encontrado")
        rfc = normalize_rfc(payload.rfc)
        duplicate = db.query(Prospector).filter(Prospector.rfc == rfc, Prospector.id != row.id).first() if rfc else None
        if duplicate:
            raise HTTPException(status_code=409, detail="Ya existe un prospectador con ese RFC")
        row.name = " ".join(payload.name.strip().split())
        row.normalized_name = normalize_name(payload.name)
        row.rfc = rfc
        row.email = (payload.email or "").strip().casefold() or None
        row.additional_emails = sorted({email.strip().casefold() for email in payload.additional_emails if email.strip()})
        row.payment_scheme = payload.payment_scheme
        row.invoice_required = payload.payment_scheme == "factura"
        row.is_active = payload.is_active
        row.linked_username = (payload.linked_username or "").strip().casefold() or None
        db.commit()
        return {"prospector": _serialize_prospector(row)}
    finally:
        db.close()


@router.post("/{prospector_id}/merge")
def merge_prospector(
    prospector_id: str,
    payload: MergePayload,
    profile: AccessProfile = Depends(require_module_access("prospectadores", operation=True)),
):
    db = SessionLocal()
    try:
        try:
            result = merge_prospectors(
                db,
                source_id=prospector_id,
                target_id=payload.target_id,
                actor=profile.username,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"No fue posible consolidar los prospectadores: {exc}") from exc
    finally:
        db.close()


@router.post("/assignments", status_code=201)
def create_assignment(payload: AssignmentPayload, profile: AccessProfile = Depends(require_module_access("prospectadores", operation=True))):
    if payload.effective_to and payload.effective_to < payload.effective_from:
        raise HTTPException(status_code=400, detail="La vigencia final no puede preceder a la inicial")
    db = SessionLocal()
    try:
        policy = db.get(Policy, payload.policy_id)
        prospector = db.get(Prospector, payload.prospector_id)
        if not policy or not prospector:
            raise HTTPException(status_code=404, detail="Póliza o prospectador no encontrado")
        rate = normalize_rate(payload.commission_percentage)
        overlapping = db.query(PolicyProspectorAssignment).filter(
            PolicyProspectorAssignment.policy_id == policy.id,
            PolicyProspectorAssignment.is_active.is_(True),
            PolicyProspectorAssignment.effective_from <= (payload.effective_to or date.max),
            or_(PolicyProspectorAssignment.effective_to.is_(None), PolicyProspectorAssignment.effective_to >= payload.effective_from),
        ).all()
        if sum((Decimal(str(row.commission_rate)) for row in overlapping), rate) > 1:
            raise HTTPException(status_code=409, detail="Los porcentajes vigentes de la póliza excederían 100%")
        row = PolicyProspectorAssignment(
            policy_id=policy.id, prospector_id=prospector.id, commission_rate=rate,
            effective_from=payload.effective_from, effective_to=payload.effective_to,
            source="manual", created_by=profile.username,
        )
        db.add(row)
        db.commit()
        return {"assignment_id": row.id}
    finally:
        db.close()


def migration_preview(db) -> dict:
    policies = db.query(Policy).options(joinedload(Policy.client)).all()
    candidates = []
    split_rows = 0
    for policy in policies:
        text = _prospector_text(policy)
        if not text:
            continue
        splits = parse_split_prospectors(text)
        if splits:
            split_rows += 1
            names = [name for name, _ in splits]
        else:
            names = [text]
        candidates.extend(normalize_name(name) for name in names)
    existing_policy_ids = {
        row[0] for row in db.query(PolicyProspectorAssignment.policy_id).filter(
            PolicyProspectorAssignment.source == "cartera_migration"
        ).all()
    }
    return {
        "policies_with_prospector": len({policy.id for policy in policies if _prospector_text(policy)}),
        "policies_pending": len({policy.id for policy in policies if _prospector_text(policy) and policy.id not in existing_policy_ids}),
        "unique_prospectors": len(set(candidates)),
        "split_policies": split_rows,
    }


@router.get("/migration-preview")
def preview_cartera_migration():
    db = SessionLocal()
    try:
        return migration_preview(db)
    finally:
        db.close()


@router.post("/migrate-cartera")
def migrate_cartera(profile: AccessProfile = Depends(require_module_access("prospectadores", operation=True))):
    db = SessionLocal()
    created_prospectors = 0
    created_assignments = 0
    skipped = 0
    try:
        rows_by_name = {row.normalized_name: row for row in db.query(Prospector).all()}
        policies = db.query(Policy).options(joinedload(Policy.client)).all()
        for policy in policies:
            text = _prospector_text(policy)
            if not text:
                continue
            metadata = policy.metadata_json if isinstance(policy.metadata_json, dict) else {}
            starts_on = _date(metadata.get("payment_start_date")) or policy.effective_start_date
            if not starts_on:
                skipped += 1
                continue
            splits = parse_split_prospectors(text)
            entries = splits or [(text, normalize_rate(policy.commission_percentage))]
            for name, rate in entries:
                normalized = normalize_name(name)
                prospector = rows_by_name.get(normalized)
                if not prospector:
                    prospector = Prospector(
                        name=" ".join(name.strip().split()), normalized_name=normalized,
                        payment_scheme="factura", invoice_required=True, is_active=True,
                        metadata_json={"migrated_from": "cartera"}, created_by=profile.username,
                    )
                    db.add(prospector)
                    db.flush()
                    rows_by_name[normalized] = prospector
                    created_prospectors += 1
                exists = db.query(PolicyProspectorAssignment).filter(
                    PolicyProspectorAssignment.policy_id == policy.id,
                    PolicyProspectorAssignment.prospector_id == prospector.id,
                    PolicyProspectorAssignment.effective_from == starts_on,
                    PolicyProspectorAssignment.source == "cartera_migration",
                ).first()
                if exists:
                    continue
                db.add(PolicyProspectorAssignment(
                    policy_id=policy.id, prospector_id=prospector.id,
                    commission_rate=rate, effective_from=starts_on,
                    effective_to=first_anniversary(starts_on), source="cartera_migration",
                    metadata_json={"legacy_value": text}, created_by=profile.username,
                ))
                created_assignments += 1
        db.commit()
        return {
            "created_prospectors": created_prospectors,
            "created_assignments": created_assignments,
            "skipped": skipped,
            "preview": migration_preview(db),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
