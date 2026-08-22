from __future__ import annotations

import io
import imaplib
import os
import re
import smtplib
from email import policy
from email.parser import BytesParser
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from collections import Counter

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from googleapiclient.http import MediaIoBaseDownload
from pydantic import BaseModel, Field
from sqlalchemy import desc

from database import Campaign, CampaignDelivery, Client, SessionLocal
from drive.client import build_drive_service
from services.auth import AccessProfile
from services.authorization import require_module_access
from services.client_email_directory import load_email_directory, normalize_client_name
from services.client_folders import normalize_rfc
from services.data_cache import data_cache
from services.mail_configuration import smtp_settings_for
from services.mail_configuration import smtp_ssl_context
from services.renovaciones import SmtpDeliveryUncertainError, send_email_smtp


router = APIRouter(prefix="/campanas", tags=["campanas"])

DEFAULT_GMM_SOURCE_FILE_ID = "1e1fL1qH4jBJLSNdSO-izTg2eDjYV6VNn"
SAFE_VARIABLES = (
    "nombre_cliente",
    "numero_poliza",
    "deducible_actual",
    "agente",
    "nombre_producto",
    "fecha_fin_vigencia",
)
VARIABLE_RE = re.compile(r"{{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*}}")
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
BOUNCE_SENDER_MARKERS = ("mailer-daemon", "postmaster")
BOUNCE_SUBJECT_MARKERS = ("delivery status", "undeliver", "no se ha podido entregar", "mail delivery")


class CampaignInput(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    asunto: str = Field(min_length=1, max_length=500)
    cuerpo: str = Field(min_length=1, max_length=20000)
    deducible_minimo: Decimal = Field(default=Decimal("1000000"), ge=0)


class CampaignTestRequest(BaseModel):
    recipient_key: str = Field(min_length=1, max_length=500)
    test_email: str = Field(min_length=3, max_length=320)


class CampaignSendRequest(BaseModel):
    confirmation: str = Field(min_length=1, max_length=255)
    batch_size: int = Field(default=20, ge=1, le=25)


def _optional_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _money(value: object) -> Decimal | None:
    text = re.sub(r"[^0-9.\-]", "", str(value or ""))
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _source_date(value: object) -> date | None:
    text = _optional_text(value)
    if not text:
        return None
    for pattern in ("%Y%m%d", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    parsed = pd.to_datetime(text, errors="coerce")
    return None if pd.isna(parsed) else parsed.date()


def _display_agent(value: object) -> str:
    return " ".join(str(value or "").replace("/", " ").split())


def _download_source() -> bytes:
    file_id = os.getenv("GOOGLE_DRIVE_CAMPAIGNS_GMM_FILE_ID", DEFAULT_GMM_SOURCE_FILE_ID).strip()
    output = io.BytesIO()
    request = build_drive_service().files().get_media(fileId=file_id, supportsAllDrives=True)
    downloader = MediaIoBaseDownload(output, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return output.getvalue()


def parse_gmm_campaign_source(workbook: bytes) -> list[dict[str, object]]:
    table = pd.read_excel(io.BytesIO(workbook), sheet_name="GMM", dtype=str, keep_default_na=False)
    required = {"CONTRATANTE", "RFC", "PRODUCTO", "NPOLIZA", "FFINVIG", "DEDUCIBLE", "NOMBRE"}
    missing = required.difference(table.columns)
    if missing:
        raise ValueError("La fuente GMM no contiene: " + ", ".join(sorted(missing)))
    rows: list[dict[str, object]] = []
    for index, row in table.iterrows():
        end_date = _source_date(row.get("FFINVIG"))
        deductible = _money(row.get("DEDUCIBLE"))
        if not end_date or deductible is None:
            continue
        policy_number = _optional_text(row.get("NPOLIZA"))
        rfc = normalize_rfc(row.get("RFC"))
        client_name = _optional_text(row.get("CONTRATANTE"))
        rows.append({
            "source_row": int(index) + 2,
            "key": f"{policy_number}:{rfc}:{int(index) + 2}",
            "numero_poliza": policy_number,
            "rfc": rfc,
            "nombre_cliente": client_name,
            "nombre_producto": _optional_text(row.get("PRODUCTO")),
            "fecha_fin_vigencia": end_date.isoformat(),
            # PersistentDataCache stores JSON, so keep the parsed source
            # payload JSON-serializable from the start.
            "deducible": float(deductible),
            "agente": _display_agent(row.get("NOMBRE")) or _optional_text(row.get("AGENTE")),
            "source_email": _optional_text(row.get("Email")).casefold(),
        })
    return rows


def _source_rows() -> list[dict[str, object]]:
    return data_cache.get_or_load(
        "campanas:gmm-source",
        lambda: parse_gmm_campaign_source(_download_source()),
        ttl_seconds=max(60, int(os.getenv("CAMPAIGNS_SOURCE_CACHE_SECONDS", "300"))),
    ).value


def _client_directories() -> tuple[dict[str, Client], dict[str, str]]:
    db = SessionLocal()
    try:
        clients = db.query(Client).all()
        by_rfc = {normalize_rfc(client.rfc): client for client in clients if normalize_rfc(client.rfc)}
    finally:
        db.close()
    try:
        by_name, _ = load_email_directory()
    except Exception:
        by_name = {}
    return by_rfc, by_name


def build_gmm_audience(minimum_deductible: Decimal, *, today: date | None = None) -> dict[str, object]:
    today = today or date.today()
    client_by_rfc, email_by_name = _client_directories()
    selected = [
        dict(row)
        for row in _source_rows()
        if row["fecha_fin_vigencia"] >= today.isoformat()
        and Decimal(str(row["deducible"])) >= minimum_deductible
    ]
    identity_counts: dict[str, int] = {}
    for row in selected:
        identity = str(row["rfc"] or normalize_client_name(str(row["nombre_cliente"])))
        identity_counts[identity] = identity_counts.get(identity, 0) + 1

    client_email_state: dict[str, bool] = {}
    for row in selected:
        rfc = str(row["rfc"])
        client = client_by_rfc.get(rfc)
        email = _optional_text(client.email if client else "").casefold()
        if not EMAIL_RE.match(email):
            source_email = str(row.get("source_email") or "").casefold()
            email = source_email if EMAIL_RE.match(source_email) else ""
        if not email:
            email = email_by_name.get(normalize_client_name(str(row["nombre_cliente"])), "")
        if not EMAIL_RE.match(email):
            email = ""
        identity = rfc or normalize_client_name(str(row["nombre_cliente"]))
        client_email_state[identity] = client_email_state.get(identity, False) or bool(email)
        row["email"] = email
        row["multiple_policies"] = identity_counts.get(identity, 0) > 1
        row["deducible"] = float(row["deducible"])

    return {
        "rows": selected,
        "summary": {
            "policies": len(selected),
            "unique_clients": len(client_email_state),
            "clients_with_email": sum(client_email_state.values()),
            "clients_missing_email": sum(not value for value in client_email_state.values()),
            "clients_with_multiple_policies": sum(count > 1 for count in identity_counts.values()),
            "rows_without_rfc": sum(not bool(row["rfc"]) for row in selected),
        },
        "generated_on": today.isoformat(),
        "segment": {
            "source": "MetLife GMM",
            "vigencia": "FFINVIG vigente",
            "deducible_minimo": float(minimum_deductible),
        },
    }


def _validate_template(subject: str, body: str) -> None:
    used = set(VARIABLE_RE.findall(subject + "\n" + body))
    unsupported = sorted(used.difference(SAFE_VARIABLES))
    if unsupported:
        raise HTTPException(status_code=422, detail="Variables no permitidas: " + ", ".join(unsupported))


def render_template(template: str, row: dict[str, object]) -> tuple[str, list[str]]:
    values = {
        "nombre_cliente": _optional_text(row.get("nombre_cliente")),
        "numero_poliza": _optional_text(row.get("numero_poliza")),
        "deducible_actual": f"${float(row.get('deducible') or 0):,.2f}",
        "agente": _optional_text(row.get("agente")),
        "nombre_producto": _optional_text(row.get("nombre_producto")),
        "fecha_fin_vigencia": _format_display_date(row.get("fecha_fin_vigencia")),
    }
    missing: list[str] = []
    def replacement(match: re.Match[str]) -> str:
        variable = match.group(1)
        value = values.get(variable, "")
        if variable in SAFE_VARIABLES and not value:
            missing.append(variable)
        return value if variable in SAFE_VARIABLES else match.group(0)
    return VARIABLE_RE.sub(replacement, template), sorted(set(missing))


def _format_display_date(value: object) -> str:
    parsed = _source_date(value)
    return parsed.strftime("%d/%m/%Y") if parsed else ""


def _serialize_campaign(campaign: Campaign) -> dict[str, object]:
    segment = campaign.segment_json or {}
    return {
        "id": campaign.id,
        "nombre": campaign.name,
        "asunto": campaign.subject,
        "cuerpo": campaign.body,
        "estatus": campaign.status,
        "deducible_minimo": float(segment.get("deducible_minimo", 1000000)),
        "creado_por": campaign.created_by,
        "created_at": campaign.created_at.isoformat(),
        "updated_at": campaign.updated_at.isoformat(),
    }


def _serialize_delivery(delivery: CampaignDelivery) -> dict[str, object]:
    return {
        "id": delivery.id,
        "recipient_key": delivery.recipient_key,
        "numero_poliza": delivery.policy_number or "",
        "rfc": delivery.rfc or "",
        "nombre_cliente": delivery.client_name,
        "email": delivery.email or "",
        "estatus": delivery.status,
        "error": delivery.error_detail or "",
        "intentos": delivery.attempts,
        "sent_at": delivery.sent_at.isoformat() if delivery.sent_at else None,
    }


def _delivery_report(db, campaign_id: str) -> dict[str, object]:
    deliveries = (
        db.query(CampaignDelivery)
        .filter(CampaignDelivery.campaign_id == campaign_id)
        .order_by(CampaignDelivery.created_at, CampaignDelivery.client_name)
        .all()
    )
    counts = Counter(item.status for item in deliveries)
    return {
        "deliveries": [_serialize_delivery(item) for item in deliveries],
        "summary": {
            "total": len(deliveries),
            "pendientes": counts["pendiente"],
            "enviando": counts["enviando"],
            "enviados": counts["enviado"],
            "sin_correo": counts["sin_correo"],
            "variables_incompletas": counts["variables_incompletas"],
            "rechazados": counts["rechazado"],
            "errores": counts["error"],
            "entrega_incierta": counts["entrega_incierta"],
            "rebotados": counts["rebotado"],
        },
    }


def prepare_campaign_deliveries(db, campaign: Campaign) -> dict[str, object]:
    existing = db.query(CampaignDelivery).filter(CampaignDelivery.campaign_id == campaign.id).count()
    if existing:
        return _delivery_report(db, campaign.id)
    audience = _campaign_audience(campaign)
    for row in audience["rows"]:
        subject, missing_subject = render_template(campaign.subject, row)
        body, missing_body = render_template(campaign.body, row)
        missing = sorted(set(missing_subject + missing_body))
        email = str(row.get("email") or "").strip().casefold()
        if not email:
            status, error = "sin_correo", "El cliente no tiene un correo válido registrado."
        elif missing:
            status, error = "variables_incompletas", "Faltan variables: " + ", ".join(missing)
        else:
            status, error = "pendiente", None
        db.add(CampaignDelivery(
            campaign_id=campaign.id,
            recipient_key=str(row["key"]),
            policy_number=str(row.get("numero_poliza") or ""),
            rfc=str(row.get("rfc") or ""),
            client_name=str(row.get("nombre_cliente") or ""),
            email=email or None,
            rendered_subject=subject,
            rendered_body=body,
            status=status,
            error_detail=error,
        ))
    campaign.status = "preparada"
    campaign.updated_at = datetime.utcnow()
    db.commit()
    return _delivery_report(db, campaign.id)


def _finish_campaign_status(db, campaign_id: str) -> None:
    campaign = _campaign_or_404(db, campaign_id)
    counts = Counter(
        row[0] for row in db.query(CampaignDelivery.status).filter(CampaignDelivery.campaign_id == campaign_id).all()
    )
    if counts["pendiente"] or counts["enviando"]:
        campaign.status = "envío parcial" if counts["enviado"] else "preparada"
    elif counts["error"] or counts["rechazado"] or counts["entrega_incierta"] or counts["rebotado"]:
        campaign.status = "completada con incidencias"
    else:
        campaign.status = "completada"
    campaign.updated_at = datetime.utcnow()
    db.commit()


def process_campaign_batch(campaign_id: str, delivery_ids: list[str], sender_username: str) -> None:
    settings = smtp_settings_for(sender_username)
    for delivery_id in delivery_ids:
        db = SessionLocal()
        try:
            delivery = db.query(CampaignDelivery).filter(CampaignDelivery.id == delivery_id).first()
            if not delivery or delivery.campaign_id != campaign_id or delivery.status != "enviando":
                continue
            try:
                send_email_smtp(
                    delivery.rendered_subject or "",
                    delivery.rendered_body or "",
                    [delivery.email or ""],
                    [],
                    cc_recipients=[],
                    settings=settings,
                )
                delivery.status = "enviado"
                delivery.sent_at = datetime.utcnow()
                delivery.error_detail = None
            except smtplib.SMTPRecipientsRefused as exc:
                delivery.status = "rechazado"
                delivery.error_detail = str(exc)[:2000]
            except SmtpDeliveryUncertainError as exc:
                delivery.status = "entrega_incierta"
                delivery.error_detail = str(exc)[:2000]
            except Exception as exc:
                delivery.status = "error"
                delivery.error_detail = f"{type(exc).__name__}: {exc}"[:2000]
            delivery.updated_at = datetime.utcnow()
            db.commit()
        finally:
            db.close()
    db = SessionLocal()
    try:
        _finish_campaign_status(db, campaign_id)
    finally:
        db.close()


def bounce_recipients(raw_message: bytes, candidates: set[str]) -> tuple[set[str], str]:
    """Return only candidate addresses from a delivery-status notification."""
    message = BytesParser(policy=policy.default).parsebytes(raw_message)
    sender = str(message.get("From", "")).casefold()
    subject = str(message.get("Subject", "")).casefold()
    if not any(marker in sender for marker in BOUNCE_SENDER_MARKERS) and not any(
        marker in subject for marker in BOUNCE_SUBJECT_MARKERS
    ):
        return set(), ""
    chunks = [str(message)]
    for part in message.walk():
        try:
            content = part.get_content()
        except Exception:
            continue
        if isinstance(content, str):
            chunks.append(content)
    text = "\n".join(chunks)
    lowered = text.casefold()
    matched = {email for email in candidates if email.casefold() in lowered}
    diagnostic_match = re.search(r"(?:Diagnostic-Code|Remote-MTA|Status):\s*([^\r\n]+)", text, re.IGNORECASE)
    diagnostic = diagnostic_match.group(1).strip() if diagnostic_match else "Gmail reportó un rebote posterior al envío."
    return matched, diagnostic[:1000]


def reconcile_campaign_bounces(campaign_id: str, username: str) -> dict[str, object]:
    settings = smtp_settings_for(username)
    if not settings:
        raise HTTPException(status_code=422, detail="Configura primero tu cuenta en Configuración de Mail")
    db = SessionLocal()
    try:
        deliveries = db.query(CampaignDelivery).filter(
            CampaignDelivery.campaign_id == campaign_id,
            CampaignDelivery.status == "enviado",
            CampaignDelivery.email.isnot(None),
        ).all()
        candidates = {str(item.email).casefold() for item in deliveries if item.email}
        if not candidates:
            return {"matched": 0, "scanned": 0, **_delivery_report(db, campaign_id)}
        earliest = min((item.sent_at or item.created_at) for item in deliveries)
        by_email: dict[str, list[CampaignDelivery]] = {}
        for item in deliveries:
            by_email.setdefault(str(item.email).casefold(), []).append(item)
        matched_diagnostics: dict[str, str] = {}
        scanned = 0
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=smtp_ssl_context(), timeout=30) as mailbox:
                mailbox.login(settings["user"], settings["password"])
                status, _ = mailbox.select("INBOX", readonly=True)
                if status != "OK":
                    raise RuntimeError("Gmail no permitió abrir la bandeja de entrada")
                status, data = mailbox.search(None, "SINCE", earliest.strftime("%d-%b-%Y"))
                if status != "OK":
                    raise RuntimeError("Gmail no permitió buscar notificaciones de entrega")
                message_ids = (data[0].split() if data and data[0] else [])[-1000:]
                for message_id in message_ids:
                    status, payload = mailbox.fetch(message_id, "(BODY.PEEK[])")
                    if status != "OK" or not payload:
                        continue
                    raw = next((item[1] for item in payload if isinstance(item, tuple) and isinstance(item[1], bytes)), None)
                    if not raw:
                        continue
                    scanned += 1
                    matched, diagnostic = bounce_recipients(raw, candidates)
                    for email in matched:
                        matched_diagnostics[email] = diagnostic
        except (imaplib.IMAP4.error, OSError, RuntimeError) as exc:
            raise HTTPException(status_code=422, detail=f"No se pudo consultar Gmail: {exc}") from exc
        now = datetime.utcnow()
        for email, diagnostic in matched_diagnostics.items():
            for delivery in by_email.get(email, []):
                delivery.status = "rebotado"
                delivery.error_detail = diagnostic
                delivery.updated_at = now
        db.commit()
        _finish_campaign_status(db, campaign_id)
        return {"matched": len(matched_diagnostics), "scanned": scanned, **_delivery_report(db, campaign_id)}
    finally:
        db.close()


def _campaign_or_404(db, campaign_id: str) -> Campaign:
    campaign = db.query(Campaign).filter(Campaign.id == campaign_id).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaña no encontrada")
    return campaign


def _campaign_audience(campaign: Campaign) -> dict[str, object]:
    minimum = Decimal(str((campaign.segment_json or {}).get("deducible_minimo", 1000000)))
    return build_gmm_audience(minimum)


def _recipient(audience: dict[str, object], recipient_key: str) -> dict[str, object]:
    row = next((item for item in audience["rows"] if item["key"] == recipient_key), None)
    if not row:
        raise HTTPException(status_code=404, detail="Destinatario no encontrado en la audiencia actual")
    return row


@router.get("")
def list_campaigns(_profile: AccessProfile = Depends(require_module_access("campanas"))):
    db = SessionLocal()
    try:
        rows = db.query(Campaign).order_by(desc(Campaign.updated_at)).all()
        return {"campaigns": [_serialize_campaign(row) for row in rows], "safe_variables": list(SAFE_VARIABLES)}
    finally:
        db.close()


@router.post("")
def create_campaign(
    payload: CampaignInput,
    profile: AccessProfile = Depends(require_module_access("campanas", operation=True)),
):
    _validate_template(payload.asunto, payload.cuerpo)
    db = SessionLocal()
    try:
        campaign = Campaign(
            name=_optional_text(payload.nombre),
            subject=payload.asunto.strip(),
            body=payload.cuerpo.strip(),
            status="borrador",
            segment_json={"tipo": "gmm_deducible", "deducible_minimo": float(payload.deducible_minimo)},
            created_by=profile.username,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return {"campaign": _serialize_campaign(campaign)}
    finally:
        db.close()


@router.put("/{campaign_id}")
def update_campaign(
    campaign_id: str,
    payload: CampaignInput,
    _profile: AccessProfile = Depends(require_module_access("campanas", operation=True)),
):
    _validate_template(payload.asunto, payload.cuerpo)
    db = SessionLocal()
    try:
        campaign = _campaign_or_404(db, campaign_id)
        if campaign.status != "borrador":
            raise HTTPException(status_code=409, detail="Solo se pueden editar campañas en borrador")
        campaign.name = _optional_text(payload.nombre)
        campaign.subject = payload.asunto.strip()
        campaign.body = payload.cuerpo.strip()
        campaign.segment_json = {"tipo": "gmm_deducible", "deducible_minimo": float(payload.deducible_minimo)}
        campaign.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(campaign)
        return {"campaign": _serialize_campaign(campaign)}
    finally:
        db.close()


@router.get("/{campaign_id}/audience")
def campaign_audience(
    campaign_id: str,
    _profile: AccessProfile = Depends(require_module_access("campanas")),
):
    db = SessionLocal()
    try:
        return _campaign_audience(_campaign_or_404(db, campaign_id))
    finally:
        db.close()


@router.get("/{campaign_id}/preview/{recipient_key}")
def campaign_preview(
    campaign_id: str,
    recipient_key: str,
    _profile: AccessProfile = Depends(require_module_access("campanas")),
):
    db = SessionLocal()
    try:
        campaign = _campaign_or_404(db, campaign_id)
        row = _recipient(_campaign_audience(campaign), recipient_key)
        subject, missing_subject = render_template(campaign.subject, row)
        body, missing_body = render_template(campaign.body, row)
        return {
            "recipient": row,
            "subject": subject,
            "body": body,
            "missing_variables": sorted(set(missing_subject + missing_body)),
        }
    finally:
        db.close()


@router.post("/{campaign_id}/send-test")
def send_campaign_test(
    campaign_id: str,
    payload: CampaignTestRequest,
    profile: AccessProfile = Depends(require_module_access("campanas", operation=True)),
):
    email = payload.test_email.strip().casefold()
    if not EMAIL_RE.match(email) or not email.endswith("@taiico.com"):
        raise HTTPException(status_code=422, detail="En la etapa 1 las pruebas solo pueden enviarse a correos @taiico.com")
    db = SessionLocal()
    try:
        campaign = _campaign_or_404(db, campaign_id)
        row = _recipient(_campaign_audience(campaign), payload.recipient_key)
        subject, missing_subject = render_template(campaign.subject, row)
        body, missing_body = render_template(campaign.body, row)
    finally:
        db.close()
    missing = sorted(set(missing_subject + missing_body))
    if missing:
        raise HTTPException(status_code=422, detail="No se puede enviar la prueba; faltan: " + ", ".join(missing))
    settings = smtp_settings_for(profile.username)
    if not settings:
        raise HTTPException(status_code=422, detail="Configura primero tu cuenta en Configuración de Mail")
    send_email_smtp(
        f"[PRUEBA CAMPAÑA] {subject}",
        body,
        [email],
        [],
        cc_recipients=[],
        settings=settings,
    )
    return {"sent": True, "recipient": email, "campaign_recipient": row}


@router.post("/{campaign_id}/prepare")
def prepare_campaign(
    campaign_id: str,
    _profile: AccessProfile = Depends(require_module_access("campanas", operation=True)),
):
    db = SessionLocal()
    try:
        campaign = _campaign_or_404(db, campaign_id)
        if campaign.status not in {"borrador", "preparada"}:
            raise HTTPException(status_code=409, detail="Esta campaña ya inició su envío y no puede regenerarse")
        return prepare_campaign_deliveries(db, campaign)
    finally:
        db.close()


@router.get("/{campaign_id}/deliveries")
def campaign_deliveries(
    campaign_id: str,
    _profile: AccessProfile = Depends(require_module_access("campanas")),
):
    db = SessionLocal()
    try:
        _campaign_or_404(db, campaign_id)
        return _delivery_report(db, campaign_id)
    finally:
        db.close()


@router.post("/{campaign_id}/send-batch")
def send_campaign_batch(
    campaign_id: str,
    payload: CampaignSendRequest,
    background_tasks: BackgroundTasks,
    profile: AccessProfile = Depends(require_module_access("campanas", operation=True)),
):
    db = SessionLocal()
    try:
        campaign = _campaign_or_404(db, campaign_id)
        if payload.confirmation.strip() != campaign.name:
            raise HTTPException(status_code=422, detail="Escribe exactamente el nombre de la campaña para confirmar")
        if campaign.status not in {"preparada", "envío parcial"}:
            raise HTTPException(status_code=409, detail="Prepara primero la audiencia o revisa el estado de la campaña")
        if not smtp_settings_for(profile.username):
            raise HTTPException(status_code=422, detail="Configura primero tu cuenta en Configuración de Mail")
        deliveries = (
            db.query(CampaignDelivery)
            .filter(CampaignDelivery.campaign_id == campaign_id, CampaignDelivery.status == "pendiente")
            .order_by(CampaignDelivery.created_at)
            .limit(payload.batch_size)
            .all()
        )
        if not deliveries:
            raise HTTPException(status_code=409, detail="No hay correos pendientes de envío")
        delivery_ids = []
        for delivery in deliveries:
            delivery.status = "enviando"
            delivery.attempts += 1
            delivery.updated_at = datetime.utcnow()
            delivery_ids.append(delivery.id)
        campaign.status = "envío parcial"
        campaign.updated_at = datetime.utcnow()
        db.commit()
        background_tasks.add_task(process_campaign_batch, campaign_id, delivery_ids, profile.username)
        return {"accepted": len(delivery_ids), "batch_size": payload.batch_size}
    finally:
        db.close()


@router.post("/{campaign_id}/reconcile-bounces")
def reconcile_bounces(
    campaign_id: str,
    profile: AccessProfile = Depends(require_module_access("campanas", operation=True)),
):
    db = SessionLocal()
    try:
        _campaign_or_404(db, campaign_id)
    finally:
        db.close()
    return reconcile_campaign_bounces(campaign_id, profile.username)
