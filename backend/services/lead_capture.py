"""Taiico website intake and scoped distribution; no outbound messages."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import threading
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Literal
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from database import Candidate, CommercialOpportunity, Lead, SessionLocal
from services.auth import AccessProfile
from services.authorization import current_access_profile
from services.gestion_comercial import OpportunityCreate, create_opportunity_record, ensure_commercial_catalog
from services.login_security import client_address
from services.metlife_agent_directory import load_agent_directory

router = APIRouter(prefix="/captacion", tags=["captacion"])
Kind = Literal["clientes", "agentes"]
KINDS = {"clientes": "policy", "agentes": "agent_recruitment"}
MODULES = {"clientes": "gestion_comercial", "agentes": "recluta"}
_lock = threading.RLock()
_attempts: dict[str, deque] = {}


class Intake(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)
    nombre: str = Field(min_length=2, max_length=150)
    telefono: str = Field(min_length=10, max_length=30)
    correo: str = Field(default="", max_length=254)
    ciudad: str = Field(min_length=2, max_length=120)
    interes: str = Field(min_length=2, max_length=100)
    consentimiento: str
    whatsapp: str = "no"
    utm_source: str = Field(default="", max_length=100)
    utm_medium: str = Field(default="", max_length=100)
    utm_campaign: str = Field(default="", max_length=100)
    utm_content: str = Field(default="", max_length=100)
    website: str = Field(default="", max_length=200)

    @field_validator("telefono")
    @classmethod
    def phone(cls, value):
        clean = re.sub(r"[\s().-]", "", value)
        if re.fullmatch(r"\d{10}", clean):
            clean = "+52" + clean
        if not re.fullmatch(r"\+[1-9]\d{9,14}", clean):
            raise ValueError("Usa 10 dígitos para México o el prefijo internacional con +")
        return clean

    @field_validator("correo")
    @classmethod
    def email(cls, value):
        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Correo inválido")
        return value.casefold()

    @field_validator("consentimiento")
    @classmethod
    def consent(cls, value):
        if value != "si":
            raise ValueError("Se requiere autorización de contacto")
        return value

    @field_validator("whatsapp")
    @classmethod
    def whatsapp_choice(cls, value):
        if value not in {"si", "no", ""}:
            raise ValueError("Preferencia de WhatsApp inválida")
        return value


def check_access(profile: AccessProfile, kind: str, *, write=False):
    module = MODULES[kind]
    can_write = profile.can_operate(module) or (profile.is_agent and kind == "clientes" and profile.can_read(module))
    if not (can_write if write else profile.can_read(module)):
        raise HTTPException(403, "No tienes permiso para este módulo")
    if not profile.is_central_admin and "TAIICO" not in profile.promotorias:
        raise HTTPException(403, "Esta bandeja pertenece a Taiico")


def visible(profile: AccessProfile, lead: Lead):
    meta = lead.metadata_json or {}
    return meta.get("promotoria") == "TAIICO" and (
        not profile.is_agent or (bool(profile.rfc) and meta.get("agent_rfc") == profile.rfc.strip().upper())
    )


def eligible_agents():
    rows = load_agent_directory()
    counts = {}
    for row in rows:
        rfc = row.get("rfc", "").strip().upper()
        counts[rfc] = counts.get(rfc, 0) + 1
    return [row for row in rows if row.get("promotoria", "").strip().upper() == "TAIICO"
            and row.get("rfc") and counts[row["rfc"]] == 1
            and row.get("status", "").strip().upper() not in {"BAJA", "INACTIVO", "INACTIVA", "CANCELADO", "CANCELADA"}]


def save_intake(db, kind: str, payload: Intake):
    now = datetime.utcnow()
    # Within a kind and a 24-hour retry window, require BOTH contacts to match.
    # Never overwrite an existing person's name, assignment or consent on retry.
    key = hashlib.sha256(f"{kind}|{payload.telefono}|{payload.correo}".encode()).hexdigest()
    previous = db.query(Lead).filter(Lead.interest_type == KINDS[kind], Lead.phone == payload.telefono,
                                    Lead.created_at >= now - timedelta(hours=24)).all()
    for lead in previous:
        if (lead.metadata_json or {}).get("intake_key") == key:
            return lead, False
    meta = {"promotoria": "TAIICO", "city": payload.ciudad, "interest": payload.interes,
            "intake_key": key, "privacy_url": "https://taiico.com/aviso-de-privacidad/",
            "contact_consent": True, "consent_at": now.isoformat(), "consent_version": "taiico-contact-2026-11",
            "whatsapp_consent": payload.whatsapp == "si", "agent_rfc": "", "agent_name": "",
            "first_contact_due_at": (now + timedelta(hours=24)).isoformat(),
            "attribution": {key: getattr(payload, key) for key in ("utm_source", "utm_medium", "utm_campaign", "utm_content")},
            "history": [{"at": now.isoformat(), "action": "received", "actor": "taiico.com"}]}
    lead = Lead(name=payload.nombre, phone=payload.telefono, email=payload.correo or None,
                interest_type=KINDS[kind], source_channel=payload.utm_source or "taiico.com",
                pipeline_stage="new", metadata_json=meta)
    db.add(lead)
    db.flush()
    if kind == "agentes":
        db.add(Candidate(lead_id=lead.id, metadata_json={"promotoria": "TAIICO", "source": "taiico.com"}))
    else:
        ensure_commercial_catalog(db)
        opportunity = create_opportunity_record(db, OpportunityCreate(
            prospect_name=payload.nombre, product_name=payload.interes, owner_agent_rfc="POR-ASIGNAR",
            owner_agent_name="Mesa Taiico · por asignar", owner_promotoria="TAIICO", source=lead.source_channel,
            detected_need=payload.interes, description="Solicitud web. Contacto y consentimiento en la bandeja de leads."), "taiico.com")
        opportunity.description = f"Solicitud web {lead.id}. Contacto y consentimiento en la bandeja de leads."
        lead.metadata_json = {**meta, "opportunity_id": opportunity.id}
    db.flush()
    return lead, True


def flatten_fields(raw: dict) -> dict:
    """Accept only declared fields forwarded by the Taiico WordPress bridge."""
    fields = raw.get("fields", raw)
    result = {}
    if isinstance(fields, list):
        fields = {str(item.get("id", "")): item for item in fields if isinstance(item, dict)}
    for key, value in fields.items():
        if isinstance(value, dict):
            key = value.get("id") or key
            value = value.get("value", value.get("raw_value", ""))
        semantic = str(key)
        if semantic in Intake.model_fields:
            result[semantic] = str(value) if value is not None else ""
    return result


@router.post("/elementor/{kind}")
async def elementor_intake(kind: Kind, request: Request):
    secret = os.getenv("TAIICO_WEBSITE_WEBHOOK_KEY", "")
    if not secret or not hmac.compare_digest(request.query_params.get("key", ""), secret):
        raise HTTPException(401, "Conexión no autorizada")
    # Atomic per-process limiter; one authorized WordPress server can carry many visitors.
    now = time.monotonic()
    address = client_address(request)
    with _lock:
        for key in list(_attempts):
            if not _attempts[key] or _attempts[key][-1] < now - 60:
                del _attempts[key]
        queue = _attempts.setdefault(address, deque())
        while queue and queue[0] < now - 60:
            queue.popleft()
        if len(queue) >= 60:
            raise HTTPException(429, "Intenta nuevamente en un minuto", headers={"Retry-After": "60"})
        queue.append(now)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 32768:
            raise HTTPException(413, "Formulario demasiado grande")
    try:
        if "application/json" in request.headers.get("content-type", ""):
            raw = json.loads(body)
        else:
            raw = {k: v[-1] for k, v in parse_qs(body.decode(), keep_blank_values=True).items()}
            if isinstance(raw.get("fields"), str):
                raw["fields"] = json.loads(raw["fields"])
        payload = Intake.model_validate(flatten_fields(raw))
    except (ValueError, TypeError, AttributeError, ValidationError):
        raise HTTPException(422, "Revisa nombre, teléfono, ciudad, interés y autorización de contacto")
    if payload.website:
        raise HTTPException(422, "No se pudo enviar el formulario")
    # Serialize retries on this single-worker deployment, commit lead + workflow together.
    with _lock, SessionLocal() as db:
        save_intake(db, kind, payload)
        db.commit()
    return {"success": True}


def serialize(lead):
    m = lead.metadata_json or {}
    return {"id": lead.id, "name": lead.name, "phone": lead.phone, "email": lead.email,
            "stage": lead.pipeline_stage, "source": lead.source_channel, "created_at": lead.created_at.isoformat(),
            **{key: m.get(key) for key in ("city", "interest", "agent_rfc", "agent_name", "attribution",
                                         "first_contact_due_at", "next_followup_at", "whatsapp_consent", "opportunity_id", "note")}}


@router.get("/leads/{kind}")
def list_leads(kind: Kind, profile: AccessProfile = Depends(current_access_profile)):
    check_access(profile, kind)
    with SessionLocal() as db:
        query = db.query(Lead).filter(Lead.interest_type == KINDS[kind], Lead.metadata_json["promotoria"].as_string() == "TAIICO")
        if profile.is_agent:
            query = query.filter(Lead.metadata_json["agent_rfc"].as_string() == (profile.rfc.strip().upper() or "__none__"))
        leads = query.order_by(Lead.created_at.desc()).limit(500).all()
        can_edit = profile.can_operate(MODULES[kind]) or (profile.is_agent and kind == "clientes" and profile.can_read(MODULES[kind]))
        return {"leads": [serialize(x) for x in leads], "can_edit": can_edit,
                "can_assign": can_edit and not profile.is_agent and kind == "clientes"}


@router.get("/agents")
def agents(profile: AccessProfile = Depends(current_access_profile)):
    check_access(profile, "clientes", write=True)
    if profile.is_agent:
        raise HTTPException(403, "La asignación corresponde a la mesa Taiico")
    return {"agents": [{"rfc": x["rfc"], "name": x["name"]} for x in eligible_agents()]}


class LeadUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: Literal["new", "contacted", "qualified", "closed", "lost"] | None = None
    agent_rfc: str | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=2000)
    next_followup_at: datetime | None = None


@router.patch("/leads/{kind}/{lead_id}")
def update_lead(kind: Kind, lead_id: str, payload: LeadUpdate, profile: AccessProfile = Depends(current_access_profile)):
    check_access(profile, kind, write=True)
    with SessionLocal() as db:
        lead = db.get(Lead, lead_id)
        if not lead or lead.interest_type != KINDS[kind] or not visible(profile, lead):
            raise HTTPException(404, "Lead no encontrado")
        meta = dict(lead.metadata_json or {})
        if payload.agent_rfc is not None:
            if profile.is_agent or kind != "clientes":
                raise HTTPException(403, "La asignación corresponde a la mesa Taiico")
            matches = [x for x in eligible_agents() if x["rfc"] == payload.agent_rfc.strip().upper()]
            if len(matches) != 1:
                raise HTTPException(422, "Selecciona un agente activo y único de Taiico")
            agent = matches[0]
            meta.update(agent_rfc=agent["rfc"], agent_name=agent["name"])
            opportunity = db.get(CommercialOpportunity, meta.get("opportunity_id")) if meta.get("opportunity_id") else None
            if opportunity:
                opportunity.owner_agent_rfc = agent["rfc"]
                opportunity.owner_agent_name = agent["name"]
        if payload.stage:
            lead.pipeline_stage = payload.stage
        if payload.note is not None:
            meta["note"] = payload.note.strip()
        if "next_followup_at" in payload.model_fields_set:
            meta["next_followup_at"] = payload.next_followup_at.isoformat() if payload.next_followup_at else None
        meta["history"] = (meta.get("history", []) + [{"at": datetime.utcnow().isoformat(), "actor": profile.username,
                            "action": "updated", "changes": payload.model_dump(mode="json", exclude_unset=True)}])[-100:]
        lead.metadata_json = meta
        db.commit()
        return {"lead": serialize(lead)}
