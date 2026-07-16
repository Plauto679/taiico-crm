from __future__ import annotations

import hmac
import io
import os
import threading
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from drive.client import build_drive_service


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


USERS_FILE_ID_ENV = "GOOGLE_DRIVE_USERS_FILE_ID"
USERS_CACHE_SECONDS_ENV = "AUTH_USERS_CACHE_SECONDS"
DEFAULT_CACHE_SECONDS = 300
REQUIRED_COLUMNS = {"Usuario", "Password"}

_cache_lock = threading.Lock()
_cached_credentials: dict[str, str] | None = None
_cache_expires_at = 0.0


def _download_users_workbook(file_id: str) -> bytes:
    try:
        from googleapiclient.http import MediaIoBaseDownload
    except ImportError as exc:
        raise RuntimeError(
            "Google Drive dependencies are not installed. "
            "Run `pip install -r backend/requirements.txt`."
        ) from exc

    output = io.BytesIO()
    request = build_drive_service().files().get_media(
        fileId=file_id,
        supportsAllDrives=True,
    )
    downloader = MediaIoBaseDownload(output, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return output.getvalue()


def _read_credentials(workbook: bytes) -> dict[str, str]:
    table = pd.read_excel(io.BytesIO(workbook), dtype=str, keep_default_na=False)
    missing_columns = REQUIRED_COLUMNS.difference(table.columns)
    if missing_columns:
        raise ValueError(
            "Users workbook is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    credentials: dict[str, str] = {}
    for _, row in table.iterrows():
        username = str(row["Usuario"]).strip().casefold()
        password = str(row["Password"])
        if username and password:
            credentials[username] = password
    return credentials


def _cache_seconds() -> int:
    value = int(os.getenv(USERS_CACHE_SECONDS_ENV, str(DEFAULT_CACHE_SECONDS)))
    return max(0, value)


def _load_credentials() -> dict[str, str]:
    global _cached_credentials, _cache_expires_at

    file_id = os.getenv(USERS_FILE_ID_ENV, "").strip()
    if not file_id:
        raise RuntimeError(f"{USERS_FILE_ID_ENV} is not configured")

    now = time.monotonic()
    with _cache_lock:
        if _cached_credentials is not None and now < _cache_expires_at:
            return _cached_credentials

        credentials = _read_credentials(_download_users_workbook(file_id))
        _cached_credentials = credentials
        _cache_expires_at = now + _cache_seconds()
        return credentials


def clear_credentials_cache() -> None:
    """Clear the in-memory workbook cache (primarily for tests)."""
    global _cached_credentials, _cache_expires_at
    with _cache_lock:
        _cached_credentials = None
        _cache_expires_at = 0.0


def verify_credentials(username, password) -> bool:
    """Verify credentials against the configured read-only Drive workbook."""
    try:
        stored_password = _load_credentials().get(str(username).strip().casefold())
        if stored_password is None:
            return False
        return hmac.compare_digest(stored_password, str(password))
    except Exception as exc:
        # Fail closed without logging credential values.
        print(f"Authentication unavailable: {type(exc).__name__}: {exc}")
        return False
