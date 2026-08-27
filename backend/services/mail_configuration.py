from __future__ import annotations

import os
import smtplib
import ssl
from datetime import datetime
from pathlib import Path

import certifi
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from database import SessionLocal, UserMailConfiguration
from services.session_auth import current_username


router = APIRouter(prefix="/mail-configuration", tags=["mail-configuration"])
KEY_PATH = Path(__file__).resolve().parents[2] / "local-secrets" / "mail-credentials.key"


def smtp_ssl_context() -> ssl.SSLContext:
    """Use certifi so launchd Python processes have a reliable CA trust store."""
    return ssl.create_default_context(cafile=certifi.where())


class MailConfigurationInput(BaseModel):
    email_address: str
    app_password: str = Field(min_length=8, max_length=128)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = Field(default=587, ge=1, le=65535)
    use_starttls: bool = True

    @field_validator("email_address")
    @classmethod
    def validate_email_address(cls, value: str) -> str:
        cleaned = value.strip().casefold()
        if "@" not in cleaned or cleaned.startswith("@") or cleaned.endswith("@"):
            raise ValueError("Ingresa una dirección de correo válida")
        return cleaned


def _fernet() -> Fernet:
    configured = os.getenv("MAIL_CREDENTIALS_ENCRYPTION_KEY", "").encode()
    if configured:
        key = configured
    else:
        KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not KEY_PATH.exists():
            KEY_PATH.write_bytes(Fernet.generate_key())
            KEY_PATH.chmod(0o600)
        key = KEY_PATH.read_bytes().strip()
    return Fernet(key)


def encrypt_password(password: str) -> str:
    return _fernet().encrypt(password.replace(" ", "").encode()).decode()


def decrypt_password(encrypted_password: str) -> str:
    try:
        return _fernet().decrypt(encrypted_password.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Unable to decrypt the stored mail credential") from exc


def configuration_for(username: str) -> UserMailConfiguration | None:
    db = SessionLocal()
    try:
        item = db.query(UserMailConfiguration).filter(UserMailConfiguration.username == username).first()
        if item:
            db.expunge(item)
        return item
    finally:
        db.close()


def smtp_settings_for(username: str) -> dict | None:
    item = configuration_for(username)
    return _smtp_settings(item)


def smtp_settings_for_email_address(email_address: str) -> dict | None:
    """Resolve a stored SMTP account by its actual From address."""
    normalized = str(email_address or "").strip().casefold()
    if not normalized:
        return None
    db = SessionLocal()
    try:
        item = (
            db.query(UserMailConfiguration)
            .filter(UserMailConfiguration.email_address == normalized)
            .first()
        )
        if item:
            db.expunge(item)
    finally:
        db.close()
    return _smtp_settings(item)


def _smtp_settings(item: UserMailConfiguration | None) -> dict | None:
    if not item:
        return None
    return {
        "host": item.smtp_host,
        "port": item.smtp_port,
        "user": item.email_address,
        "sender": item.email_address,
        "password": decrypt_password(item.encrypted_password),
        "use_starttls": item.use_starttls,
    }


def _public(item: UserMailConfiguration | None) -> dict:
    if not item:
        return {"configured": False}
    return {
        "configured": True,
        "email_address": item.email_address,
        "smtp_host": item.smtp_host,
        "smtp_port": item.smtp_port,
        "use_starttls": item.use_starttls,
        "last_verified_at": item.last_verified_at.isoformat() if item.last_verified_at else None,
    }


@router.get("")
def get_configuration(username: str = Depends(current_username)):
    return _public(configuration_for(username))


@router.put("")
def save_configuration(payload: MailConfigurationInput, username: str = Depends(current_username)):
    db = SessionLocal()
    try:
        item = db.query(UserMailConfiguration).filter(UserMailConfiguration.username == username).first()
        if not item:
            item = UserMailConfiguration(username=username)
            db.add(item)
        item.email_address = str(payload.email_address).strip().casefold()
        item.smtp_host = payload.smtp_host.strip()
        item.smtp_port = payload.smtp_port
        item.use_starttls = payload.use_starttls
        item.encrypted_password = encrypt_password(payload.app_password)
        item.last_verified_at = None
        db.commit()
        db.refresh(item)
        return _public(item)
    finally:
        db.close()


@router.post("/test")
def test_configuration(username: str = Depends(current_username)):
    settings = smtp_settings_for(username)
    if not settings:
        raise HTTPException(status_code=404, detail="Configura primero tu cuenta de correo")
    try:
        with smtplib.SMTP(settings["host"], settings["port"], timeout=15) as server:
            if settings["use_starttls"]:
                server.starttls(context=smtp_ssl_context())
            server.login(settings["user"], settings["password"])
    except (smtplib.SMTPException, OSError) as exc:
        raise HTTPException(status_code=400, detail=f"Gmail rechazó la conexión: {exc}") from exc

    db = SessionLocal()
    try:
        item = db.query(UserMailConfiguration).filter(UserMailConfiguration.username == username).first()
        item.last_verified_at = datetime.utcnow()
        db.commit()
        return {"success": True, "message": "Conexión autenticada; no se envió ningún correo"}
    finally:
        db.close()
