from __future__ import annotations

import fcntl
import json
import os
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from services.auth import AccessProfile
from services.authorization import current_access_profile


router = APIRouter(prefix="/automatic-mails", tags=["automatic-mails"])
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TIMEZONE = "America/Mexico_City"
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _emails_from_env(name: str, fallback: tuple[str, ...]) -> list[str]:
    raw = os.getenv(name, "").strip()
    values = re.split(r"[,;\n]+", raw) if raw else list(fallback)
    return normalize_emails(values)


def normalize_emails(values: list[str] | tuple[str, ...]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw or "").strip().casefold()
        if not value:
            continue
        if not EMAIL_PATTERN.match(value):
            raise ValueError(f"Correo inválido: {raw}")
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def default_automations() -> dict[str, dict]:
    pending_recipients = _emails_from_env(
        "PENDING_REPORT_AUTOMATION_RECIPIENTS",
        (
            "pamela.alfaro@taiico.com",
            "veronica.alfaro@taiico.com",
            "alberto.alfaro@taiico.com",
            "florgabriela.flores@taiico.com",
            "juan.ibarraran@taiico.com",
            "gilberto.gonzalez@taiico.com",
        ),
    )
    renewal_recipients = _emails_from_env(
        "RENEWAL_AGENT_AUTOMATION_RECIPIENTS",
        (
            "alberto.alfaro@taiico.com",
            "veronica.alfaro@taiico.com",
        ),
    )
    renewal_cc = _emails_from_env(
        "RENEWAL_EMAIL_CC_RECIPIENTS",
        (
            "alberto.alfaro@taiico.com",
            "veronica.alfaro@taiico.com",
        ),
    )
    pending_sender = os.getenv(
        "PENDING_REPORT_AUTOMATION_SENDER_USERNAME",
        "alberto.alfaro@taiico.com",
    ).strip().casefold()
    return {
        "client_birthdays": {
            "id": "client_birthdays",
            "name": "Cumpleaños de clientes",
            "description": "Envía a cada agente los cumpleaños próximos de sus clientes.",
            "enabled": True,
            "cadence": "daily",
            "hour": int(os.getenv("BIRTHDAY_AUTOMATION_HOUR", "11")),
            "minute": 0,
            "timezone": os.getenv("BIRTHDAY_AUTOMATION_TIMEZONE", DEFAULT_TIMEZONE),
            "day_of_week": None,
            "day_of_month": None,
            "sender": os.getenv(
                "BIRTHDAY_AUTOMATION_SENDER_USERNAME",
                "alberto.alfaro@taiico.com",
            ).strip().casefold(),
            "recipient_mode": "dynamic",
            "recipient_description": "Correo personal de cada agente con clientes que cumplen años",
            "recipients": [],
            "cc_recipients": [],
        },
        "pending_daily": {
            "id": "pending_daily",
            "name": "Resumen diario de pendientes",
            "description": "Informe general del módulo de Pendientes.",
            "enabled": True,
            "cadence": "daily",
            "hour": int(os.getenv("PENDING_REPORT_AUTOMATION_HOUR", "19")),
            "minute": 0,
            "timezone": os.getenv("PENDING_REPORT_AUTOMATION_TIMEZONE", DEFAULT_TIMEZONE),
            "day_of_week": None,
            "day_of_month": None,
            "sender": pending_sender,
            "recipient_mode": "manual",
            "recipient_description": "Lista interna",
            "recipients": pending_recipients,
            "cc_recipients": [],
        },
        "pending_promotoria_abbondanza": {
            "id": "pending_promotoria_abbondanza",
            "name": "Pendientes · ABBONDANZA",
            "description": "Informe diario de pendientes exclusivo de la promotoría ABBONDANZA.",
            "enabled": True,
            "cadence": "daily",
            "hour": int(os.getenv("PENDING_REPORT_AUTOMATION_HOUR", "19")),
            "minute": 0,
            "timezone": os.getenv("PENDING_REPORT_AUTOMATION_TIMEZONE", DEFAULT_TIMEZONE),
            "day_of_week": None,
            "day_of_month": None,
            "sender": pending_sender,
            "recipient_mode": "manual",
            "recipient_description": "Destinatario de ABBONDANZA",
            "recipients": ["19eryk@gmail.com"],
            "cc_recipients": [],
            "promotoria": "ABBONDANZA",
        },
        "pending_promotoria_ekilibra": {
            "id": "pending_promotoria_ekilibra",
            "name": "Pendientes · EKILIBRA",
            "description": "Informe diario de pendientes exclusivo de la promotoría EKILIBRA.",
            "enabled": True,
            "cadence": "daily",
            "hour": int(os.getenv("PENDING_REPORT_AUTOMATION_HOUR", "19")),
            "minute": 0,
            "timezone": os.getenv("PENDING_REPORT_AUTOMATION_TIMEZONE", DEFAULT_TIMEZONE),
            "day_of_week": None,
            "day_of_month": None,
            "sender": pending_sender,
            "recipient_mode": "manual",
            "recipient_description": "Destinatario de EKILIBRA",
            "recipients": ["mauricio@ekilibra.me"],
            "cc_recipients": [],
            "promotoria": "EKILIBRA",
        },
        "pending_promotoria_fenix_prevision": {
            "id": "pending_promotoria_fenix_prevision",
            "name": "Pendientes · FENIX PRE-VISION",
            "description": "Informe diario de pendientes exclusivo de la promotoría FENIX PRE-VISION.",
            "enabled": True,
            "cadence": "daily",
            "hour": int(os.getenv("PENDING_REPORT_AUTOMATION_HOUR", "19")),
            "minute": 0,
            "timezone": os.getenv("PENDING_REPORT_AUTOMATION_TIMEZONE", DEFAULT_TIMEZONE),
            "day_of_week": None,
            "day_of_month": None,
            "sender": pending_sender,
            "recipient_mode": "manual",
            "recipient_description": "Destinatario de FENIX PRE-VISION",
            "recipients": ["vic.villanueva@hotmail.com"],
            "cc_recipients": [],
            "promotoria": "FENIX PRE-VISION",
        },
        "pending_weekly_reminder": {
            "id": "pending_weekly_reminder",
            "name": "Recordatorio semanal de pendientes",
            "description": "Recordatorio de seguimientos próximos del módulo de Pendientes.",
            "enabled": True,
            "cadence": "weekly",
            "hour": int(os.getenv("PENDING_REMINDER_AUTOMATION_HOUR", "10")),
            "minute": 0,
            "timezone": os.getenv("PENDING_REPORT_AUTOMATION_TIMEZONE", DEFAULT_TIMEZONE),
            "day_of_week": 0,
            "day_of_month": None,
            "sender": pending_sender,
            "recipient_mode": "manual",
            "recipient_description": "Lista interna",
            "recipients": pending_recipients,
            "cc_recipients": [],
        },
        "agent_license_expiration": {
            "id": "agent_license_expiration",
            "name": "Vencimiento de cédulas de agentes",
            "description": "Lista de agentes cuya cédula vence dentro de los próximos tres meses.",
            "enabled": True,
            "cadence": "monthly",
            "hour": int(os.getenv("AGENT_LICENSE_AUTOMATION_HOUR", "10")),
            "minute": 0,
            "timezone": os.getenv("AGENT_LICENSE_AUTOMATION_TIMEZONE", DEFAULT_TIMEZONE),
            "day_of_week": None,
            "day_of_month": 1,
            "sender": (
                os.getenv("AGENT_LICENSE_AUTOMATION_SENDER_USERNAME", "").strip()
                or pending_sender
            ).casefold(),
            "recipient_mode": "manual",
            "recipient_description": "Lista interna",
            "recipients": pending_recipients,
            "cc_recipients": [],
        },
        "renewal_agent": {
            "id": "renewal_agent",
            "name": "Agente de renovaciones MetLife GMM",
            "description": "Ejecuta renovaciones y envía avisos internos de inicio y cierre.",
            "enabled": True,
            "cadence": "daily",
            "hour": int(os.getenv("RENEWAL_AGENT_AUTOMATION_HOUR", "9")),
            "minute": 0,
            "timezone": os.getenv("RENEWAL_AGENT_AUTOMATION_TIMEZONE", DEFAULT_TIMEZONE),
            "day_of_week": None,
            "day_of_month": None,
            "sender": os.getenv(
                "RENEWAL_EMAIL_SENDER_ADDRESS",
                "clientes@taiico.com",
            ).strip().casefold(),
            "recipient_mode": "manual",
            "recipient_description": "Avisos internos de inicio y cierre",
            "recipients": renewal_recipients,
            "cc_recipients": renewal_cc,
            "cc_description": "Copias internas de las renovaciones enviadas al cliente",
        },
    }


def config_path() -> Path:
    configured = os.getenv("AUTOMATIC_MAILS_CONFIG_FILE", "").strip()
    return (
        Path(configured).expanduser()
        if configured
        else REPOSITORY_ROOT / ".runtime" / "automatic-mails-config.json"
    )


def _read_overrides_unlocked(path: Path) -> dict[str, dict]:
    try:
        payload = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def all_automation_configs() -> list[dict]:
    defaults = default_automations()
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_SH)
        overrides = _read_overrides_unlocked(path)
    result: list[dict] = []
    for automation_id, default in defaults.items():
        item = deepcopy(default)
        stored = overrides.get(automation_id)
        if isinstance(stored, dict):
            for key in (
                "enabled", "cadence", "hour", "minute", "timezone",
                "day_of_week", "day_of_month", "sender", "recipients",
                "cc_recipients",
            ):
                if key in stored:
                    item[key] = stored[key]
        result.append(item)
    return result


def automation_config(automation_id: str) -> dict:
    item = next(
        (item for item in all_automation_configs() if item["id"] == automation_id),
        None,
    )
    if item is None:
        raise KeyError(automation_id)
    return item


class AutomaticMailUpdate(BaseModel):
    enabled: bool
    cadence: str
    hour: int = Field(ge=0, le=23)
    minute: int = Field(ge=0, le=59)
    timezone: str = Field(min_length=1, max_length=100)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    sender: str = Field(min_length=3, max_length=320)
    recipients: list[str] = Field(default_factory=list, max_length=100)
    cc_recipients: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("cadence")
    @classmethod
    def validate_cadence(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if normalized not in {"daily", "weekly", "monthly"}:
            raise ValueError("Periodicidad no válida")
        return normalized

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        normalized = value.strip()
        try:
            ZoneInfo(normalized)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Zona horaria no válida") from exc
        return normalized

    @field_validator("sender")
    @classmethod
    def validate_sender(cls, value: str) -> str:
        return normalize_emails([value])[0]

    @field_validator("recipients", "cc_recipients")
    @classmethod
    def validate_recipients(cls, values: list[str]) -> list[str]:
        return normalize_emails(values)


def save_automation_config(automation_id: str, payload: AutomaticMailUpdate) -> dict:
    defaults = default_automations()
    if automation_id not in defaults:
        raise KeyError(automation_id)
    if payload.cadence == "weekly" and payload.day_of_week is None:
        raise ValueError("Selecciona un día de la semana")
    if payload.cadence == "monthly" and payload.day_of_month is None:
        raise ValueError("Selecciona un día del mes")
    if defaults[automation_id]["recipient_mode"] == "manual" and not payload.recipients:
        raise ValueError("Captura al menos un destinatario")

    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        overrides = _read_overrides_unlocked(path)
        overrides[automation_id] = payload.model_dump()
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(overrides, ensure_ascii=False, indent=2) + "\n"
        )
        temporary.replace(path)
    return automation_config(automation_id)


def local_now_for(automation_id: str) -> datetime:
    config = automation_config(automation_id)
    return datetime.now(ZoneInfo(config["timezone"]))


def schedule_matches(config: dict, now: datetime) -> bool:
    if not config.get("enabled", True):
        return False
    scheduled_minutes = int(config["hour"]) * 60 + int(config.get("minute", 0))
    current_minutes = now.hour * 60 + now.minute
    if current_minutes < scheduled_minutes:
        return False
    cadence = config["cadence"]
    if cadence == "weekly":
        return now.weekday() == int(config["day_of_week"])
    if cadence == "monthly":
        return now.day == int(config["day_of_month"])
    return True


def schedule_period_key(config: dict, now: datetime) -> str:
    if config["cadence"] == "monthly":
        return now.strftime("%Y-%m")
    if config["cadence"] == "weekly":
        iso_year, iso_week, _ = now.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    return now.date().isoformat()


@router.get("")
def list_automatic_mails(profile: AccessProfile = Depends(current_access_profile)):
    return {
        "can_operate": profile.can_operate("configuracion_mail"),
        "automations": all_automation_configs(),
    }


@router.put("/{automation_id}")
def update_automatic_mail(
    automation_id: str,
    payload: AutomaticMailUpdate,
    profile: AccessProfile = Depends(current_access_profile),
):
    if not profile.can_operate("configuracion_mail"):
        raise HTTPException(status_code=403, detail="No tienes permiso para editar esta configuración")
    try:
        return save_automation_config(automation_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Automatización no encontrada") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
