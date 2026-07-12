from __future__ import annotations

import os
import re
import time

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import AgentAction, SessionLocal


router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


class RenewalWhatsAppRequest(BaseModel):
    client_name: str
    policy_number: str
    period_start: int
    period_end: int
    agent_name: str


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D+", "", value or "")
    if len(digits) < 10 or len(digits) > 15:
        raise ValueError("Phone must contain between 10 and 15 digits")
    return digits


def renewal_message(request: RenewalWhatsAppRequest) -> str:
    return (
        f"Hola, {request.client_name}. Ya está disponible la renovación de tu póliza "
        f"MetLife GMM {request.policy_number} para el periodo "
        f"{request.period_start}–{request.period_end}. Tu agente {request.agent_name} "
        "dará seguimiento contigo. Por seguridad, no compartimos documentos sensibles "
        "directamente sin validación."
    )


def whatsapp_settings() -> dict[str, str]:
    names = {
        "access_token": "WHATSAPP_ACCESS_TOKEN",
        "phone_number_id": "WHATSAPP_PHONE_NUMBER_ID",
        "api_version": "WHATSAPP_API_VERSION",
        "template_name": "WHATSAPP_RENEWAL_TEMPLATE_NAME",
        "test_recipient": "WHATSAPP_TEST_RECIPIENT",
    }
    settings = {key: os.getenv(env_name, "").strip() for key, env_name in names.items()}
    missing = [names[key] for key, value in settings.items() if not value]
    if missing:
        raise RuntimeError(f"Missing WhatsApp configuration: {', '.join(missing)}")
    if os.getenv("WHATSAPP_TEST_MODE", "").lower() not in {"1", "true", "yes"}:
        raise RuntimeError("WHATSAPP_TEST_MODE must be true")
    return settings


def template_payload(request: RenewalWhatsAppRequest, recipient: str, template_name: str) -> dict:
    return {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": "es_MX"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": request.client_name},
                        {"type": "text", "text": request.policy_number},
                        {"type": "text", "text": str(request.period_start)},
                        {"type": "text", "text": str(request.period_end)},
                        {"type": "text", "text": request.agent_name},
                    ],
                }
            ],
        },
    }


def record_action(status: str, request: RenewalWhatsAppRequest, output: dict, duration_ms: int) -> None:
    db = SessionLocal()
    try:
        db.add(AgentAction(
            agent_name="renewal_agent",
            action_type="whatsapp_test_message",
            status=status,
            description=f"WhatsApp renewal test for policy {request.policy_number}",
            input_payload={
                "policy_number": request.policy_number,
                "client_name": request.client_name,
                "test_mode": True,
            },
            output_payload=output,
            duration_ms=duration_ms,
        ))
        db.commit()
    finally:
        db.close()


@router.post("/renewal/preview")
async def preview_renewal_whatsapp(request: RenewalWhatsAppRequest):
    return {
        "test_mode": True,
        "message": renewal_message(request),
        "template_parameters": [
            request.client_name,
            request.policy_number,
            str(request.period_start),
            str(request.period_end),
            request.agent_name,
        ],
    }


@router.post("/renewal/send-test")
async def send_test_renewal_whatsapp(request: RenewalWhatsAppRequest):
    started = time.monotonic()
    try:
        settings = whatsapp_settings()
        recipient = normalize_phone(settings["test_recipient"])
        allowlist = {
            normalize_phone(value)
            for value in os.getenv("WHATSAPP_TEST_ALLOWLIST", "").split(",")
            if value.strip()
        }
        if recipient not in allowlist:
            raise RuntimeError("WHATSAPP_TEST_RECIPIENT is not in WHATSAPP_TEST_ALLOWLIST")

        payload = template_payload(request, recipient, settings["template_name"])
        url = (
            f"https://graph.facebook.com/{settings['api_version']}/"
            f"{settings['phone_number_id']}/messages"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings['access_token']}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        response_data = response.json()
        response.raise_for_status()
        duration_ms = int((time.monotonic() - started) * 1000)
        output = {
            "recipient": recipient,
            "template_name": settings["template_name"],
            "message_id": (response_data.get("messages") or [{}])[0].get("id"),
        }
        record_action("completed", request, output, duration_ms)
        return {"test_mode": True, **output}
    except Exception as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        record_action("failed", request, {"error": str(exc)}, duration_ms)
        raise HTTPException(status_code=502, detail=f"WhatsApp test send failed: {exc}")
