from __future__ import annotations

import io
import os
import threading
import time
import unicodedata

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from database import Client, SessionLocal
from drive.client import build_drive_service


router = APIRouter(prefix="/client-email-directory", tags=["client-email-directory"])

CLIENT_EMAILS_FILE_ID_ENV = "GOOGLE_DRIVE_CLIENT_EMAILS_FILE_ID"
CLIENT_EMAILS_CACHE_SECONDS_ENV = "CLIENT_EMAILS_CACHE_SECONDS"
DEFAULT_CACHE_SECONDS = 300

_cache_lock = threading.Lock()
_cached_directory: dict[str, str] | None = None
_cached_ambiguous_names: set[str] = set()
_cache_expires_at = 0.0


class ClientEmailSyncRequest(BaseModel):
    dry_run: bool = True


def normalize_client_name(value: str | None) -> str:
    text = " ".join(str(value or "").strip().split()).casefold()
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )


def _download_directory_workbook(file_id: str) -> bytes:
    from googleapiclient.http import MediaIoBaseDownload

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


def parse_email_directory(workbook: bytes) -> tuple[dict[str, str], set[str]]:
    table = pd.read_excel(io.BytesIO(workbook), dtype=str, keep_default_na=False)
    required = {"Clientes", "Mail"}
    missing = required.difference(table.columns)
    if missing:
        raise ValueError("Client email workbook is missing: " + ", ".join(sorted(missing)))

    candidates: dict[str, set[str]] = {}
    for _, row in table.iterrows():
        normalized_name = normalize_client_name(row["Clientes"])
        email = str(row["Mail"]).strip().casefold()
        if normalized_name and email and "@" in email:
            candidates.setdefault(normalized_name, set()).add(email)

    ambiguous = {name for name, emails in candidates.items() if len(emails) > 1}
    directory = {
        name: next(iter(emails))
        for name, emails in candidates.items()
        if len(emails) == 1
    }
    return directory, ambiguous


def clear_email_directory_cache() -> None:
    global _cached_directory, _cached_ambiguous_names, _cache_expires_at
    with _cache_lock:
        _cached_directory = None
        _cached_ambiguous_names = set()
        _cache_expires_at = 0.0


def load_email_directory() -> tuple[dict[str, str], set[str]]:
    global _cached_directory, _cached_ambiguous_names, _cache_expires_at
    file_id = os.getenv(CLIENT_EMAILS_FILE_ID_ENV, "").strip()
    if not file_id:
        raise RuntimeError(f"{CLIENT_EMAILS_FILE_ID_ENV} is not configured")

    now = time.monotonic()
    with _cache_lock:
        if _cached_directory is not None and now < _cache_expires_at:
            return _cached_directory, _cached_ambiguous_names
        directory, ambiguous = parse_email_directory(_download_directory_workbook(file_id))
        cache_seconds = max(0, int(os.getenv(CLIENT_EMAILS_CACHE_SECONDS_ENV, str(DEFAULT_CACHE_SECONDS))))
        _cached_directory = directory
        _cached_ambiguous_names = ambiguous
        _cache_expires_at = now + cache_seconds
        return directory, ambiguous


def lookup_client_email(client_name: str | None) -> str | None:
    directory, ambiguous = load_email_directory()
    normalized_name = normalize_client_name(client_name)
    if not normalized_name or normalized_name in ambiguous:
        return None
    return directory.get(normalized_name)


@router.post("/sync")
async def sync_client_email_directory(request: ClientEmailSyncRequest):
    directory, ambiguous = load_email_directory()
    db = SessionLocal()
    try:
        matched = 0
        would_update = 0
        updated = 0
        existing_same = 0
        conflicts = 0
        unmatched = 0
        ambiguous_count = 0

        for client in db.query(Client).all():
            normalized_name = normalize_client_name(client.full_name)
            if normalized_name in ambiguous:
                ambiguous_count += 1
                continue
            canonical_email = directory.get(normalized_name)
            if not canonical_email:
                unmatched += 1
                continue
            matched += 1
            current_email = str(client.email or "").strip().casefold()
            if current_email == canonical_email:
                existing_same += 1
            elif current_email:
                conflicts += 1
            else:
                would_update += 1
                if not request.dry_run:
                    client.email = canonical_email
                    metadata = dict(client.metadata_json or {})
                    metadata["email_source"] = "canonical_client_email_directory"
                    metadata["email_source_file_id"] = os.getenv(CLIENT_EMAILS_FILE_ID_ENV)
                    client.metadata_json = metadata
                    updated += 1

        if request.dry_run:
            db.rollback()
        else:
            db.commit()
        return {
            "dry_run": request.dry_run,
            "directory_entries": len(directory),
            "ambiguous_directory_names": len(ambiguous),
            "matched_clients": matched,
            "would_update": would_update,
            "updated": updated,
            "existing_same": existing_same,
            "conflicts_not_overwritten": conflicts,
            "unmatched_clients": unmatched,
            "ambiguous_clients": ambiguous_count,
        }
    finally:
        db.close()
