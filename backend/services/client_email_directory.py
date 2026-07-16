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
_cached_rfc_directory: dict[str, str] = {}
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


def normalize_rfc(value: str | None) -> str:
    return "".join(str(value or "").strip().upper().split())


def parse_client_directory(workbook: bytes) -> tuple[dict[str, str], dict[str, str], set[str]]:
    table = pd.read_excel(io.BytesIO(workbook), dtype=str, keep_default_na=False)
    required = {"Clientes", "Mail"}
    missing = required.difference(table.columns)
    if missing:
        raise ValueError("Client email workbook is missing: " + ", ".join(sorted(missing)))

    email_candidates: dict[str, set[str]] = {}
    rfc_candidates: dict[str, set[str]] = {}
    for _, row in table.iterrows():
        normalized_name = normalize_client_name(row["Clientes"])
        email = str(row["Mail"]).strip().casefold()
        if normalized_name and email and "@" in email:
            email_candidates.setdefault(normalized_name, set()).add(email)
        rfc = normalize_rfc(row.get("RFC"))
        if normalized_name and rfc:
            rfc_candidates.setdefault(normalized_name, set()).add(rfc)

    ambiguous = {
        name for name, values in email_candidates.items() if len(values) > 1
    } | {
        name for name, values in rfc_candidates.items() if len(values) > 1
    }
    email_directory = {
        name: next(iter(values))
        for name, values in email_candidates.items()
        if len(values) == 1 and name not in ambiguous
    }
    rfc_directory = {
        name: next(iter(values))
        for name, values in rfc_candidates.items()
        if len(values) == 1 and name not in ambiguous
    }
    return email_directory, rfc_directory, ambiguous


def parse_email_directory(workbook: bytes) -> tuple[dict[str, str], set[str]]:
    email_directory, _, ambiguous = parse_client_directory(workbook)
    return email_directory, ambiguous


def clear_email_directory_cache() -> None:
    global _cached_directory, _cached_rfc_directory, _cached_ambiguous_names, _cache_expires_at
    with _cache_lock:
        _cached_directory = None
        _cached_rfc_directory = {}
        _cached_ambiguous_names = set()
        _cache_expires_at = 0.0


def load_client_directory() -> tuple[dict[str, str], dict[str, str], set[str]]:
    global _cached_directory, _cached_rfc_directory, _cached_ambiguous_names, _cache_expires_at
    file_id = os.getenv(CLIENT_EMAILS_FILE_ID_ENV, "").strip()
    if not file_id:
        raise RuntimeError(f"{CLIENT_EMAILS_FILE_ID_ENV} is not configured")

    now = time.monotonic()
    with _cache_lock:
        if _cached_directory is not None and now < _cache_expires_at:
            return _cached_directory, _cached_rfc_directory, _cached_ambiguous_names
        directory, rfc_directory, ambiguous = parse_client_directory(
            _download_directory_workbook(file_id)
        )
        cache_seconds = max(0, int(os.getenv(CLIENT_EMAILS_CACHE_SECONDS_ENV, str(DEFAULT_CACHE_SECONDS))))
        _cached_directory = directory
        _cached_rfc_directory = rfc_directory
        _cached_ambiguous_names = ambiguous
        _cache_expires_at = now + cache_seconds
        return directory, rfc_directory, ambiguous


def load_email_directory() -> tuple[dict[str, str], set[str]]:
    directory, _, ambiguous = load_client_directory()
    return directory, ambiguous


def lookup_client_email(client_name: str | None) -> str | None:
    directory, ambiguous = load_email_directory()
    normalized_name = normalize_client_name(client_name)
    if not normalized_name or normalized_name in ambiguous:
        return None
    return directory.get(normalized_name)


@router.post("/sync")
async def sync_client_email_directory(request: ClientEmailSyncRequest):
    directory, rfc_directory, ambiguous = load_client_directory()
    db = SessionLocal()
    try:
        matched = 0
        would_update = 0
        updated = 0
        existing_same = 0
        conflicts = 0
        unmatched = 0
        ambiguous_count = 0
        rfc_would_update = 0
        rfc_updated = 0
        rfc_existing_same = 0
        rfc_conflicts = 0

        for client in db.query(Client).all():
            normalized_name = normalize_client_name(client.full_name)
            if normalized_name in ambiguous:
                ambiguous_count += 1
                continue
            canonical_email = directory.get(normalized_name)
            canonical_rfc = rfc_directory.get(normalized_name)
            if not canonical_email and not canonical_rfc:
                unmatched += 1
                continue
            matched += 1
            client_updated = False
            email_updated_for_client = False
            rfc_updated_for_client = False
            if canonical_email:
                current_email = str(client.email or "").strip().casefold()
                if current_email == canonical_email:
                    existing_same += 1
                elif current_email:
                    conflicts += 1
                else:
                    would_update += 1
                    if not request.dry_run:
                        client.email = canonical_email
                        updated += 1
                        client_updated = True
                        email_updated_for_client = True
            if canonical_rfc:
                current_rfc = normalize_rfc(client.rfc)
                if current_rfc == canonical_rfc:
                    rfc_existing_same += 1
                elif current_rfc:
                    rfc_conflicts += 1
                else:
                    rfc_would_update += 1
                    if not request.dry_run:
                        client.rfc = canonical_rfc
                        rfc_updated += 1
                        client_updated = True
                        rfc_updated_for_client = True

            if client_updated:
                metadata = dict(client.metadata_json or {})
                source_file_id = os.getenv(CLIENT_EMAILS_FILE_ID_ENV)
                if email_updated_for_client:
                    metadata["email_source"] = "canonical_client_email_directory"
                    metadata["email_source_file_id"] = source_file_id
                if rfc_updated_for_client:
                    metadata["rfc_source"] = "canonical_client_directory"
                    metadata["rfc_source_file_id"] = source_file_id
                client.metadata_json = metadata

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
            "rfc_directory_entries": len(rfc_directory),
            "rfc_would_update": rfc_would_update,
            "rfc_updated": rfc_updated,
            "rfc_existing_same": rfc_existing_same,
            "rfc_conflicts_not_overwritten": rfc_conflicts,
        }
    finally:
        db.close()
