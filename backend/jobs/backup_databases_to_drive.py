from __future__ import annotations

import argparse
import fcntl
import json
import os
import sqlite3
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from googleapiclient.http import MediaFileUpload


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import (  # noqa: E402
    CARTERA_SOURCE_FILE_IDS,
    FINANCE_SOURCE_FILE_IDS,
    GOOGLE_DRIVE_SOURCE_FOLDERS,
)
from database import DATABASE_URL  # noqa: E402
from services.auth import _build_writable_drive_service  # noqa: E402


BACKUP_ROOT_FOLDER_ID = os.getenv(
    "GOOGLE_DRIVE_DATABASE_BACKUPS_FOLDER_ID",
    "1d3WOlKR5q34UsQlpq90zWRxdD37cAGrZ",
).strip()
RETENTION_DAYS = 30
MEXICO_CITY = ZoneInfo("America/Mexico_City")
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
BACKUP_MARKER = "taiico_daily_database_backup"
LOCK_PATH = PROJECT_ROOT / ".runtime" / "database-backups.lock"
STATE_PATH = PROJECT_ROOT / ".runtime" / "database-backups-state.json"


@dataclass(frozen=True)
class DriveSource:
    key: str
    folder_name: str
    file_id: str


def _configured(value: str | None, default: str = "") -> str:
    return str(value or default).strip()


def configured_drive_sources() -> list[DriveSource]:
    sources = [
        DriveSource("usuarios", "Usuarios", _configured(os.getenv("GOOGLE_DRIVE_USERS_FILE_ID"))),
        DriveSource("cotizaciones", "Cotizaciones", _configured(os.getenv("GOOGLE_DRIVE_QUOTES_FILE_ID"), "1uP-G9GAz75SyO4nUhrJlaHDhX5zJ6vk4")),
        DriveSource("agentes_metlife", "Agentes MetLife", _configured(os.getenv("GOOGLE_DRIVE_AGENTS_METLIFE_FILE_ID"), "1IoeLDCQe4T3DofStiBSaI09xjX2-RSby")),
        DriveSource("correos_clientes", "Correos de clientes", _configured(os.getenv("GOOGLE_DRIVE_CLIENT_EMAILS_FILE_ID"))),
        DriveSource("pendientes_emision", "Pendientes - Emisión y Servicios", _configured(os.getenv("GOOGLE_DRIVE_PENDING_EMISION_SERVICIOS_FILE_ID"), "1JMr-EwtniwHvPm6zefhGJroTw2vxivmC")),
        DriveSource("pendientes_siniestros", "Pendientes - Siniestros", _configured(os.getenv("GOOGLE_DRIVE_PENDING_SINIESTROS_FILE_ID"), "1UvXo2LboTKWl5323mEuP6bmmyIhLYveL")),
        DriveSource("recluta", "Recluta", _configured(os.getenv("GOOGLE_DRIVE_RECLUTA_SOURCE_FILE_ID"), "1a4YYy-vF4pESre60BJWXwdp_1DdSmObT")),
        DriveSource("rrhh", "RRHH", _configured(os.getenv("GOOGLE_DRIVE_RRHH_FILE_ID"), "1kAlNJ93qPVeIQmokGTgmyk1VqRQ4fqu6")),
        DriveSource("cartera_metlife", "Cartera - MetLife", _configured(CARTERA_SOURCE_FILE_IDS.get("metlife"))),
        DriveSource("cartera_sura", "Cartera - SURA", _configured(CARTERA_SOURCE_FILE_IDS.get("sura"))),
        DriveSource("cartera_aarco", "Cartera - AARCO", _configured(CARTERA_SOURCE_FILE_IDS.get("aarco_axa"))),
        DriveSource("finanzas_tla_amex", "Finanzas - TLA - AMEX", _configured(FINANCE_SOURCE_FILE_IDS.get("tla_amex"))),
        DriveSource("finanzas_tla_bbva", "Finanzas - TLA - BBVA", _configured(FINANCE_SOURCE_FILE_IDS.get("tla_bbva"))),
        DriveSource("finanzas_tla_banorte", "Finanzas - TLA - Banorte", _configured(FINANCE_SOURCE_FILE_IDS.get("tla_banorte"))),
        DriveSource("finanzas_ts_bbva", "Finanzas - TS - BBVA", _configured(FINANCE_SOURCE_FILE_IDS.get("ts_bbva"))),
    ]
    source_labels = {
        "cobranza.metlife": "Cobranza - MetLife",
        "cobranza.sura": "Cobranza - SURA",
        "cobranza.aarco": "Cobranza - AARCO",
        "renovaciones.aarco_axa": "Renovaciones - AARCO y AXA",
        "renovaciones.metlife_gmm": "Renovaciones - MetLife GMM",
        "renovaciones.metlife_vida": "Renovaciones - MetLife Vida",
        "renovaciones.promotoria_sura": "Renovaciones - Promotoría SURA",
        "renovaciones.sura": "Renovaciones - SURA",
    }
    sources.extend(
        DriveSource(key.replace(".", "_"), source_labels[key], _configured(config.get("file_id")))
        for key, config in GOOGLE_DRIVE_SOURCE_FOLDERS.items()
        if key in source_labels
    )

    missing = [source.folder_name for source in sources if not source.file_id]
    if missing:
        raise RuntimeError("Faltan IDs de Drive para: " + ", ".join(missing))
    duplicate_ids = {
        source.file_id
        for source in sources
        if sum(other.file_id == source.file_id for other in sources) > 1
    }
    if duplicate_ids:
        raise RuntimeError("Hay fuentes duplicadas en el inventario de respaldos")
    return sources


def _escape_query(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _list_files(service, query: str, fields: str) -> list[dict]:
    files: list[dict] = []
    page_token = None
    while True:
        response = service.files().list(
            q=query,
            fields=f"nextPageToken,files({fields})",
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return files


def ensure_source_folder(service, source: DriveSource) -> str:
    query = (
        f"'{_escape_query(BACKUP_ROOT_FOLDER_ID)}' in parents and trashed = false "
        f"and mimeType = '{FOLDER_MIME_TYPE}' "
        f"and appProperties has {{ key='taiico_backup_source_key' and value='{_escape_query(source.key)}' }}"
    )
    matches = _list_files(service, query, "id,name")
    if matches:
        return str(matches[0]["id"])

    # Reuse an empty/user-created folder with the expected name before creating one.
    name_query = (
        f"'{_escape_query(BACKUP_ROOT_FOLDER_ID)}' in parents and trashed = false "
        f"and mimeType = '{FOLDER_MIME_TYPE}' and name = '{_escape_query(source.folder_name)}'"
    )
    matches = _list_files(service, name_query, "id,name")
    if matches:
        folder_id = str(matches[0]["id"])
        service.files().update(
            fileId=folder_id,
            body={"appProperties": {"taiico_backup_source_key": source.key}},
            fields="id",
            supportsAllDrives=True,
        ).execute()
        return folder_id

    created = service.files().create(
        body={
            "name": source.folder_name,
            "mimeType": FOLDER_MIME_TYPE,
            "parents": [BACKUP_ROOT_FOLDER_ID],
            "appProperties": {"taiico_backup_source_key": source.key},
        },
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return str(created["id"])


def _daily_backup_in_folder(service, folder_id: str, source: DriveSource, day: date) -> dict:
    source_metadata = service.files().get(
        fileId=source.file_id,
        fields="id,name,mimeType,size,modifiedTime,md5Checksum,trashed",
        supportsAllDrives=True,
    ).execute()
    if source_metadata.get("trashed"):
        raise RuntimeError(f"La fuente {source.folder_name} está en la papelera")
    backup_name = f"{day.isoformat()} - {source_metadata['name']}"
    query = (
        f"'{_escape_query(folder_id)}' in parents and trashed = false "
        f"and name = '{_escape_query(backup_name)}'"
    )
    existing = _list_files(service, query, "id,name,createdTime")
    if existing:
        return {"status": "already_exists", "id": existing[0]["id"], "name": backup_name}
    created = service.files().copy(
        fileId=source.file_id,
        body={
            "name": backup_name,
            "parents": [folder_id],
            "appProperties": {
                "taiico_backup_kind": BACKUP_MARKER,
                "taiico_backup_source_id": source.file_id,
                "taiico_backup_source_key": source.key,
                "taiico_backup_date": day.isoformat(),
            },
        },
        fields="id,name,createdTime,size,webViewLink",
        supportsAllDrives=True,
    ).execute()
    return {"status": "created", **created}


def _sqlite_path() -> Path | None:
    prefix = "sqlite:///"
    if not DATABASE_URL.startswith(prefix):
        return None
    raw_path = DATABASE_URL[len(prefix):]
    path = Path(raw_path)
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def _snapshot_sqlite(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise RuntimeError(f"No se encontró la base SQL local: {source}")
    with sqlite3.connect(source) as current, sqlite3.connect(destination) as backup:
        current.backup(backup)


def _daily_sql_backup(service, folder_id: str, day: date) -> dict:
    backup_name = f"{day.isoformat()} - taiico-crm.sqlite3"
    query = (
        f"'{_escape_query(folder_id)}' in parents and trashed = false "
        f"and name = '{_escape_query(backup_name)}'"
    )
    existing = _list_files(service, query, "id,name,createdTime")
    if existing:
        return {"status": "already_exists", "id": existing[0]["id"], "name": backup_name}
    sqlite_path = _sqlite_path()
    if sqlite_path is None:
        raise RuntimeError("El respaldo automático de la base SQL requiere SQLite")
    with tempfile.TemporaryDirectory(prefix="taiico-sql-backup-") as temporary:
        snapshot = Path(temporary) / "taiico-crm.sqlite3"
        _snapshot_sqlite(sqlite_path, snapshot)
        created = service.files().create(
            body={
                "name": backup_name,
                "parents": [folder_id],
                "appProperties": {
                    "taiico_backup_kind": BACKUP_MARKER,
                    "taiico_backup_source_id": "local-sqlite",
                    "taiico_backup_source_key": "base_sql_crm",
                    "taiico_backup_date": day.isoformat(),
                },
            },
            media_body=MediaFileUpload(
                str(snapshot), mimetype="application/vnd.sqlite3", resumable=False
            ),
            fields="id,name,createdTime,size,webViewLink",
            supportsAllDrives=True,
        ).execute()
    return {"status": "created", **created}


def prune_old_backups(service, folder_id: str, today: date) -> int:
    cutoff = today - timedelta(days=RETENTION_DAYS - 1)
    query = (
        f"'{_escape_query(folder_id)}' in parents and trashed = false "
        f"and appProperties has {{ key='taiico_backup_kind' and value='{BACKUP_MARKER}' }}"
    )
    deleted = 0
    for item in _list_files(service, query, "id,name,appProperties"):
        raw_date = (item.get("appProperties") or {}).get("taiico_backup_date", "")
        try:
            backup_date = date.fromisoformat(raw_date)
        except ValueError:
            continue
        if backup_date < cutoff:
            service.files().update(
                fileId=item["id"],
                body={"trashed": True},
                fields="id,trashed",
                supportsAllDrives=True,
            ).execute()
            deleted += 1
    return deleted


def run_backup(day: date | None = None) -> dict:
    if not BACKUP_ROOT_FOLDER_ID:
        raise RuntimeError("GOOGLE_DRIVE_DATABASE_BACKUPS_FOLDER_ID no está configurado")
    today = day or datetime.now(MEXICO_CITY).date()
    service = _build_writable_drive_service()
    results: list[dict] = []
    errors: list[dict] = []

    for source in configured_drive_sources():
        try:
            folder_id = ensure_source_folder(service, source)
            backup = _daily_backup_in_folder(service, folder_id, source, today)
            deleted = prune_old_backups(service, folder_id, today)
            results.append({"key": source.key, "folder": source.folder_name, **backup, "pruned": deleted})
        except Exception as exc:
            errors.append({"key": source.key, "folder": source.folder_name, "error": str(exc)})

    sql_source = DriveSource("base_sql_crm", "Base SQL del CRM", "local-sqlite")
    try:
        folder_id = ensure_source_folder(service, sql_source)
        backup = _daily_sql_backup(service, folder_id, today)
        deleted = prune_old_backups(service, folder_id, today)
        results.append({"key": sql_source.key, "folder": sql_source.folder_name, **backup, "pruned": deleted})
    except Exception as exc:
        errors.append({"key": sql_source.key, "folder": sql_source.folder_name, "error": str(exc)})

    return {
        "date": today.isoformat(),
        "timezone": str(MEXICO_CITY),
        "retention_days": RETENTION_DAYS,
        "successful": len(results),
        "created": sum(item["status"] == "created" for item in results),
        "already_existed": sum(item["status"] == "already_exists" for item in results),
        "pruned": sum(item["pruned"] for item in results),
        "errors": errors,
        "results": results,
    }


def _last_successful_date() -> date | None:
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return date.fromisoformat(str(payload.get("last_successful_date", "")))
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _remember_successful_date(day: date) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_PATH.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({"last_successful_date": day.isoformat()}) + "\n",
        encoding="utf-8",
    )
    temporary.replace(STATE_PATH)


def main() -> int:
    parser = argparse.ArgumentParser(description="Respalda diariamente las bases del CRM en Google Drive")
    parser.add_argument("--date", help="Fecha de respaldo YYYY-MM-DD; por defecto hoy en Ciudad de México")
    args = parser.parse_args()
    requested_day = date.fromisoformat(args.date) if args.date else None
    today = requested_day or datetime.now(MEXICO_CITY).date()
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "skipped", "reason": "another_backup_is_running"}))
            return 0
        if requested_day is None and _last_successful_date() == today:
            print(
                json.dumps(
                    {
                        "status": "skipped",
                        "reason": "daily_backup_already_completed",
                        "date": today.isoformat(),
                    }
                )
            )
            return 0
        result = run_backup(today)
        if not result["errors"]:
            _remember_successful_date(today)
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
