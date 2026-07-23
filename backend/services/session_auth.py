from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

from fastapi import Cookie, HTTPException


COOKIE_NAME = "taiico_session"
DEFAULT_SESSION_IDLE_SECONDS = 60 * 60
SECRET_PATH = Path(__file__).resolve().parents[2] / "local-secrets" / "session-signing.key"


def session_idle_seconds() -> int:
    try:
        configured = int(os.getenv("AUTH_SESSION_IDLE_SECONDS", str(DEFAULT_SESSION_IDLE_SECONDS)))
    except ValueError:
        configured = DEFAULT_SESSION_IDLE_SECONDS
    return min(max(configured, 5 * 60), 24 * 60 * 60)


def _secret() -> bytes:
    configured = os.getenv("AUTH_SESSION_SECRET", "").encode()
    if configured:
        return configured
    SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not SECRET_PATH.exists():
        SECRET_PATH.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        SECRET_PATH.chmod(0o600)
    return SECRET_PATH.read_text(encoding="utf-8").strip().encode()


def create_session_token(username: str) -> str:
    now = int(time.time())
    payload = json.dumps(
        {
            "sub": username.strip().casefold(),
            "iat": now,
            "exp": now + session_idle_seconds(),
        },
        separators=(",", ":"),
    ).encode()
    encoded = base64.urlsafe_b64encode(payload).rstrip(b"=")
    signature = hmac.new(_secret(), encoded, hashlib.sha256).digest()
    return f"{encoded.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def read_session_token(token: str) -> str:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected = hmac.new(_secret(), encoded.encode(), hashlib.sha256).digest()
        supplied = base64.urlsafe_b64decode(supplied_signature + "=" * (-len(supplied_signature) % 4))
        if not hmac.compare_digest(expected, supplied):
            raise ValueError("invalid signature")
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if int(payload["exp"]) < int(time.time()):
            raise ValueError("expired session")
        return str(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from exc


def current_username(taiico_session: str | None = Cookie(default=None)) -> str:
    if not taiico_session:
        raise HTTPException(status_code=401, detail="Authentication required")
    return read_session_token(taiico_session)
