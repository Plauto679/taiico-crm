from __future__ import annotations

import csv
import io
import json
import os
import threading
from datetime import date, datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from googleapiclient.http import MediaIoBaseUpload
from sqlalchemy import desc

from database import AuditLog, SessionLocal
from services.authorization import current_access_profile
from services.session_auth import COOKIE_NAME, read_session_token


router = APIRouter(prefix="/logs", tags=["logs"])
LOGS_FOLDER_ID = os.getenv("GOOGLE_DRIVE_LOGS_FOLDER_ID", "1I5hTofOFip_uYuu8S5az0HC0sWuODqWr")
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
EXCLUDED_PATHS = {"/login", "/logout", "/session/refresh", "/password/forgot", "/password/reset", "/password/change"}
SENSITIVE_KEYS = {"password", "new_password", "current_password", "token", "authorization", "content", "file"}
_sync_lock = threading.Lock()


def _module_for_path(path: str) -> str:
    root = path.strip("/").split("/", 1)[0].replace("-", "_") or "sistema"
    aliases = {"base_loads": "carga_bases", "mail_configuration": "configuracion_mail"}
    return aliases.get(root, root)


def _safe_value(value: Any, key: str = "") -> Any:
    if key.casefold() in SENSITIVE_KEYS:
        return "[PROTEGIDO]"
    if isinstance(value, dict):
        return {str(k): _safe_value(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_value(item) for item in value[:50]]
    if isinstance(value, str):
        return value[:1000]
    return value


def _entity(payload: dict[str, Any], path: str) -> tuple[str | None, str | None]:
    candidates = ("policy_number", "folio", "rfc", "username", "id", "row_number")
    entity_id = next((str(payload[key]) for key in candidates if payload.get(key) not in (None, "")), None)
    path_parts = path.strip("/").split("/")
    if not entity_id and len(path_parts) > 2:
        entity_id = path_parts[-1]
    return (_module_for_path(path).rstrip("s"), entity_id)


def _action(method: str, path: str) -> str:
    last = path.rstrip("/").split("/")[-1].replace("-", " ")
    verbs = {"POST": "Crear/Ejecutar", "PUT": "Actualizar", "PATCH": "Actualizar", "DELETE": "Eliminar"}
    return f"{verbs.get(method, method)} · {last}"


def should_audit(request: Request) -> bool:
    return request.method in MUTATING_METHODS and request.url.path not in EXCLUDED_PATHS and not request.url.path.startswith("/logs")


async def capture_request(request: Request) -> tuple[str | None, dict[str, Any]]:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None, {}
    try:
        username = read_session_token(token)
    except HTTPException:
        return None, {}
    payload: dict[str, Any] = {}
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            parsed = json.loads((await request.body()).decode("utf-8"))
            if isinstance(parsed, dict):
                payload = _safe_value(parsed)
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
    return username, payload


def record_event(request: Request, username: str, payload: dict[str, Any], status_code: int) -> None:
    entity_type, entity_id = _entity(payload, request.url.path)
    db = SessionLocal()
    try:
        db.add(AuditLog(
            username=username,
            module=_module_for_path(request.url.path),
            action=_action(request.method, request.url.path),
            entity_type=entity_type,
            entity_id=entity_id,
            http_method=request.method,
            endpoint=request.url.path,
            status_code=status_code,
            outcome="exitoso" if status_code < 400 else "error",
            changes_json=payload,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent", "")[:500],
        ))
        db.commit()
    finally:
        db.close()
    threading.Thread(target=sync_month_to_drive, args=(datetime.utcnow(),), daemon=True).start()


def _rows_for_month(moment: datetime) -> list[AuditLog]:
    start = datetime(moment.year, moment.month, 1)
    end = datetime(moment.year + (moment.month == 12), 1 if moment.month == 12 else moment.month + 1, 1)
    db = SessionLocal()
    try:
        return db.query(AuditLog).filter(AuditLog.occurred_at >= start, AuditLog.occurred_at < end).order_by(AuditLog.occurred_at).all()
    finally:
        db.close()


def sync_month_to_drive(moment: datetime | None = None) -> str | None:
    if not LOGS_FOLDER_ID or not _sync_lock.acquire(blocking=False):
        return None
    try:
        moment = moment or datetime.utcnow()
        filename = f"TAIICO_Auditoria_{moment:%Y-%m}.csv"
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Fecha UTC", "Usuario", "Módulo", "Acción", "Tipo", "Registro", "Resultado", "Método", "Ruta", "Cambios", "IP"])
        for row in _rows_for_month(moment):
            writer.writerow([row.occurred_at.isoformat(), row.username, row.module, row.action, row.entity_type or "", row.entity_id or "", row.outcome, row.http_method, row.endpoint, json.dumps(row.changes_json or {}, ensure_ascii=False), row.ip_address or ""])
        content = output.getvalue().encode("utf-8-sig")

        from services.auth import _build_writable_drive_service
        service = _build_writable_drive_service()
        escaped = filename.replace("'", "\\'")
        matches = service.files().list(q=f"'{LOGS_FOLDER_ID}' in parents and name = '{escaped}' and trashed = false", fields="files(id,webViewLink)", supportsAllDrives=True, includeItemsFromAllDrives=True).execute().get("files", [])
        media = MediaIoBaseUpload(io.BytesIO(content), mimetype="text/csv", resumable=False)
        if matches:
            saved = service.files().update(fileId=matches[0]["id"], media_body=media, fields="id,webViewLink", supportsAllDrives=True).execute()
        else:
            saved = service.files().create(body={"name": filename, "parents": [LOGS_FOLDER_ID]}, media_body=media, fields="id,webViewLink", supportsAllDrives=True).execute()
        return saved.get("webViewLink") or f"https://drive.google.com/open?id={saved['id']}"
    except Exception as exc:
        print(f"Audit Drive sync unavailable: {type(exc).__name__}: {exc}")
        return None
    finally:
        _sync_lock.release()


def _serialize(row: AuditLog) -> dict[str, Any]:
    return {"id": row.id, "occurred_at": row.occurred_at.isoformat(), "username": row.username, "module": row.module, "action": row.action, "entity_type": row.entity_type, "entity_id": row.entity_id, "http_method": row.http_method, "endpoint": row.endpoint, "status_code": row.status_code, "outcome": row.outcome, "changes": row.changes_json or {}, "ip_address": row.ip_address, "user_agent": row.user_agent}


@router.get("")
def list_logs(
    username: str | None = None,
    module: str | None = None,
    outcome: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
    _profile=Depends(current_access_profile),
):
    db = SessionLocal()
    try:
        query = db.query(AuditLog)
        if username: query = query.filter(AuditLog.username == username)
        if module: query = query.filter(AuditLog.module == module)
        if outcome: query = query.filter(AuditLog.outcome == outcome)
        if start_date: query = query.filter(AuditLog.occurred_at >= datetime.combine(start_date, time.min))
        if end_date: query = query.filter(AuditLog.occurred_at < datetime.combine(end_date + timedelta(days=1), time.min))
        rows = query.order_by(desc(AuditLog.occurred_at)).limit(limit).all()
        return {"logs": [_serialize(row) for row in rows], "drive_folder_url": f"https://drive.google.com/drive/folders/{LOGS_FOLDER_ID}"}
    finally:
        db.close()


@router.post("/sync")
def sync_logs(_profile=Depends(current_access_profile)):
    url = sync_month_to_drive()
    return {"success": bool(url), "url": url, "folder_url": f"https://drive.google.com/drive/folders/{LOGS_FOLDER_ID}"}
