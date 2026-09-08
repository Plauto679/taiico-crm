from __future__ import annotations

import fcntl
import io
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload
from pydantic import BaseModel, Field

from database import engine
from jobs.backup_databases_to_drive import (
    BACKUP_MARKER,
    BACKUP_ROOT_FOLDER_ID,
    LOCK_PATH,
    MEXICO_CITY,
    DriveSource,
    _escape_query,
    _list_files,
    _snapshot_sqlite,
    _sqlite_path,
    configured_drive_sources,
    ensure_source_folder,
)
from services.auth import _build_writable_drive_service, clear_credentials_cache
from services.authorization import AccessProfile, require_module_access


router = APIRouter(prefix="/time-machine", tags=["time-machine"])
RESTORE_CONFIRMATION = "RESTAURAR"
PRE_RESTORE_REASON = "pre_restore"
GOOGLE_NATIVE_PREFIX = "application/vnd.google-apps."


class RestoreRequest(BaseModel):
    source_key: str = Field(min_length=1, max_length=100)
    backup_file_id: str = Field(min_length=5, max_length=200)
    confirmation: str = Field(min_length=1, max_length=30)


def all_sources() -> list[DriveSource]:
    return [
        *configured_drive_sources(),
        DriveSource("base_sql_crm", "Base SQL del CRM", "local-sqlite"),
    ]


def source_by_key(source_key: str) -> DriveSource:
    try:
        return next(source for source in all_sources() if source.key == source_key)
    except StopIteration as exc:
        raise ValueError("La base seleccionada no pertenece al inventario de respaldos") from exc


@contextmanager
def restoration_lock() -> Iterator[None]:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                "Hay otro respaldo o restauración en curso. Intenta nuevamente en unos minutos."
            ) from exc
        yield


def _download_file(service, file_id: str) -> bytes:
    output = io.BytesIO()
    downloader = MediaIoBaseDownload(
        output,
        service.files().get_media(fileId=file_id, supportsAllDrives=True),
    )
    complete = False
    while not complete:
        _, complete = downloader.next_chunk()
    return output.getvalue()


def _backup_query() -> str:
    return (
        "trashed = false and "
        f"appProperties has {{ key='taiico_backup_kind' and value='{BACKUP_MARKER}' }}"
    )


def list_restore_points() -> dict:
    service = _build_writable_drive_service()
    files = _list_files(
        service,
        _backup_query(),
        "id,name,createdTime,modifiedTime,size,mimeType,webViewLink,parents,appProperties",
    )
    by_source: dict[str, list[dict]] = {}
    for item in files:
        properties = item.get("appProperties") or {}
        source_key = str(properties.get("taiico_backup_source_key") or "")
        if not source_key:
            continue
        by_source.setdefault(source_key, []).append(
            {
                "id": str(item["id"]),
                "name": str(item.get("name") or "Respaldo"),
                "backup_date": str(properties.get("taiico_backup_date") or ""),
                "created_time": item.get("createdTime"),
                "size": int(item.get("size") or 0),
                "web_view_link": item.get("webViewLink"),
                "reason": str(properties.get("taiico_backup_reason") or "daily"),
            }
        )

    sources = []
    for source in all_sources():
        restore_points = sorted(
            by_source.get(source.key, []),
            key=lambda item: (item["backup_date"], item.get("created_time") or ""),
            reverse=True,
        )
        sources.append(
            {
                "key": source.key,
                "name": source.folder_name,
                "versions": restore_points,
                "version_count": len(restore_points),
                "latest_backup_date": (
                    restore_points[0]["backup_date"] if restore_points else None
                ),
            }
        )
    return {
        "root_folder_url": f"https://drive.google.com/drive/folders/{BACKUP_ROOT_FOLDER_ID}",
        "sources": sources,
    }


def _validated_backup(service, source: DriveSource, backup_file_id: str) -> dict:
    metadata = service.files().get(
        fileId=backup_file_id,
        fields="id,name,mimeType,size,trashed,parents,appProperties",
        supportsAllDrives=True,
    ).execute()
    properties = metadata.get("appProperties") or {}
    if metadata.get("trashed"):
        raise ValueError("El respaldo seleccionado está en la papelera")
    if properties.get("taiico_backup_kind") != BACKUP_MARKER:
        raise ValueError("El archivo seleccionado no es un respaldo administrado por Time Machine")
    if properties.get("taiico_backup_source_key") != source.key:
        raise ValueError("El respaldo seleccionado corresponde a otra base")
    folder_id = ensure_source_folder(service, source)
    if folder_id not in set(metadata.get("parents") or []):
        raise ValueError("El respaldo no se encuentra en la carpeta esperada")
    return metadata


def _safety_properties(source: DriveSource, timestamp: datetime) -> dict[str, str]:
    return {
        "taiico_backup_kind": BACKUP_MARKER,
        "taiico_backup_source_id": source.file_id,
        "taiico_backup_source_key": source.key,
        "taiico_backup_date": timestamp.date().isoformat(),
        "taiico_backup_reason": PRE_RESTORE_REASON,
    }


def _create_drive_safety_backup(service, source: DriveSource, folder_id: str) -> dict:
    timestamp = datetime.now(MEXICO_CITY)
    source_metadata = service.files().get(
        fileId=source.file_id,
        fields="id,name,mimeType,trashed",
        supportsAllDrives=True,
    ).execute()
    if source_metadata.get("trashed"):
        raise RuntimeError("La base vigente está en la papelera")
    if str(source_metadata.get("mimeType") or "").startswith(GOOGLE_NATIVE_PREFIX):
        raise ValueError(
            "La base vigente usa un formato nativo de Google y no puede reemplazarse conservando el ID"
        )
    name = (
        f"{timestamp:%Y-%m-%dT%H-%M-%S} - Pre-restauración - "
        f"{source_metadata.get('name') or source.folder_name}"
    )
    return service.files().copy(
        fileId=source.file_id,
        body={
            "name": name,
            "parents": [folder_id],
            "appProperties": _safety_properties(source, timestamp),
        },
        fields="id,name,webViewLink,createdTime",
        supportsAllDrives=True,
    ).execute()


def _restore_drive_source(service, source: DriveSource, backup: dict) -> dict:
    mime_type = str(backup.get("mimeType") or "application/octet-stream")
    if mime_type.startswith(GOOGLE_NATIVE_PREFIX):
        raise ValueError(
            "Este respaldo usa un formato nativo de Google y no puede reemplazarse conservando el ID"
        )
    folder_id = ensure_source_folder(service, source)
    safety = _create_drive_safety_backup(service, source, folder_id)
    content = _download_file(service, str(backup["id"]))
    if not content:
        raise ValueError("El respaldo seleccionado está vacío")
    updated = service.files().update(
        fileId=source.file_id,
        media_body=MediaIoBaseUpload(io.BytesIO(content), mimetype=mime_type, resumable=False),
        fields="id,name,modifiedTime,webViewLink,size",
        supportsAllDrives=True,
    ).execute()
    if source.key == "usuarios":
        clear_credentials_cache()
    return {"safety_backup": safety, "restored_file": updated}


def _validate_sqlite(path: Path) -> None:
    try:
        with sqlite3.connect(path) as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()
    except sqlite3.DatabaseError as exc:
        raise ValueError("El respaldo no contiene una base SQLite válida") from exc
    if not result or str(result[0]).casefold() != "ok":
        raise ValueError("La comprobación de integridad del respaldo SQL falló")


def _create_sql_safety_backup(service, source: DriveSource, folder_id: str, sql_path: Path) -> dict:
    timestamp = datetime.now(MEXICO_CITY)
    with tempfile.TemporaryDirectory(prefix="taiico-pre-restore-") as temporary:
        snapshot = Path(temporary) / "taiico-crm.sqlite3"
        _snapshot_sqlite(sql_path, snapshot)
        return service.files().create(
            body={
                "name": f"{timestamp:%Y-%m-%dT%H-%M-%S} - Pre-restauración - taiico-crm.sqlite3",
                "parents": [folder_id],
                "appProperties": _safety_properties(source, timestamp),
            },
            media_body=MediaFileUpload(
                str(snapshot), mimetype="application/vnd.sqlite3", resumable=False
            ),
            fields="id,name,webViewLink,createdTime",
            supportsAllDrives=True,
        ).execute()


def _restore_sql_source(service, source: DriveSource, backup: dict) -> dict:
    sql_path = _sqlite_path()
    if sql_path is None:
        raise ValueError("La base SQL configurada no es SQLite y no admite esta restauración")
    folder_id = ensure_source_folder(service, source)
    safety = _create_sql_safety_backup(service, source, folder_id, sql_path)
    with tempfile.TemporaryDirectory(prefix="taiico-time-machine-") as temporary:
        restored_path = Path(temporary) / "restored.sqlite3"
        restored_path.write_bytes(_download_file(service, str(backup["id"])))
        _validate_sqlite(restored_path)
        engine.dispose()
        with sqlite3.connect(restored_path) as restored, sqlite3.connect(sql_path) as current:
            restored.backup(current)
        engine.dispose()
    return {
        "safety_backup": safety,
        "restored_file": {"id": "local-sqlite", "name": sql_path.name},
    }


def restore_backup(source_key: str, backup_file_id: str) -> dict:
    source = source_by_key(source_key)
    service = _build_writable_drive_service()
    with restoration_lock():
        backup = _validated_backup(service, source, backup_file_id)
        restored = (
            _restore_sql_source(service, source, backup)
            if source.key == "base_sql_crm"
            else _restore_drive_source(service, source, backup)
        )
    return {
        "success": True,
        "source_key": source.key,
        "source_name": source.folder_name,
        "restored_backup": {"id": backup["id"], "name": backup.get("name")},
        **restored,
    }


@router.get("")
def get_time_machine(
    profile: AccessProfile = Depends(require_module_access("time_machine")),
):
    return {**list_restore_points(), "can_restore": profile.can_operate("time_machine")}


@router.post("/restore")
def restore_time_machine_backup(
    payload: RestoreRequest,
    _profile: AccessProfile = Depends(
        require_module_access("time_machine", operation=True)
    ),
):
    if payload.confirmation.strip().upper() != RESTORE_CONFIRMATION:
        raise HTTPException(status_code=400, detail="Escribe RESTAURAR para confirmar")
    try:
        return restore_backup(payload.source_key, payload.backup_file_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
