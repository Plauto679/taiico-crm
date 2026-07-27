from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta

from database import PasswordResetToken, SessionLocal
from services import auth
from services.mail_configuration import smtp_settings_for
from services.renovaciones import send_email_smtp


RESET_TOKEN_MINUTES = 15


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_reset_token(username: str) -> str:
    normalized = username.strip().casefold()
    token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        db.query(PasswordResetToken).filter(
            PasswordResetToken.username == normalized,
            PasswordResetToken.used_at.is_(None),
        ).update({"used_at": now}, synchronize_session=False)
        db.add(
            PasswordResetToken(
                username=normalized,
                token_hash=_token_hash(token),
                expires_at=now + timedelta(minutes=RESET_TOKEN_MINUTES),
            )
        )
        db.commit()
    finally:
        db.close()
    return token


def send_reset_email(username: str, token: str) -> None:
    public_url = os.getenv("PUBLIC_APP_URL", "https://taiico-crm.com").rstrip("/")
    reset_url = f"{public_url}/restablecer-password?token={token}"
    subject = "Restablece tu contraseña de TAIICO CRM"
    body = (
        "Recibimos una solicitud para restablecer tu contraseña de TAIICO CRM.\n\n"
        f"Abre este enlace dentro de los próximos {RESET_TOKEN_MINUTES} minutos:\n"
        f"{reset_url}\n\n"
        "El enlace funciona una sola vez. Si no solicitaste el cambio, ignora este correo."
    )
    html_body = (
        "<p>Recibimos una solicitud para restablecer tu contraseña de TAIICO CRM.</p>"
        f'<p><a href="{reset_url}">Restablecer contraseña</a></p>'
        f"<p>El enlace funciona una sola vez y vence en {RESET_TOKEN_MINUTES} minutos.</p>"
        "<p>Si no solicitaste el cambio, ignora este correo.</p>"
    )
    send_email_smtp(
        subject,
        body,
        [username],
        cc_recipients=[],
        settings=smtp_settings_for(username),
        html_body=html_body,
    )


def request_password_reset(username: str) -> None:
    normalized = username.strip().casefold()
    if not auth.registered_user(normalized):
        return
    token = create_reset_token(normalized)
    send_reset_email(normalized, token)


def consume_reset_token(token: str, new_password: str) -> str:
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        item = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == _token_hash(token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at >= now,
        ).first()
        if not item:
            raise ValueError("El enlace no es válido o ya venció")

        auth.update_password(item.username, new_password)
        item.used_at = now
        db.commit()
        return item.username
    finally:
        db.close()


def change_password(username: str, current_password: str, new_password: str) -> None:
    if not auth.verify_credentials(username, current_password):
        raise ValueError("La contraseña actual no es correcta")
    auth.update_password(username, new_password)
