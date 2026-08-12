from __future__ import annotations

import io
import os
import threading
import time
import uuid
from datetime import datetime, timezone

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_

from database import Client, SessionLocal
from drive.client import download_drive_file_bytes
from services.auth import AccessProfile
from services.authorization import current_access_profile


router = APIRouter(prefix="/cotizaciones", tags=["cotizaciones"])

QUOTES_FILE_ID_ENV = "GOOGLE_DRIVE_QUOTES_FILE_ID"
DEFAULT_QUOTES_FILE_ID = "1uP-G9GAz75SyO4nUhrJlaHDhX5zJ6vk4"
AGENTS_FILE_ID_ENV = "GOOGLE_DRIVE_AGENTS_METLIFE_FILE_ID"
DEFAULT_AGENTS_FILE_ID = "1IoeLDCQe4T3DofStiBSaI09xjX2-RSby"
PRODUCTS = {
    "GMM": ("Medicalife Familiar", "Medicalife PG", "Primordial"),
    "Vida": ("Metalife", "Totalife", "Flexilife", "Horizonte", "Temporal"),
}
INITIAL_STATUS = "Pendiente de cotización"
HEADERS = (
    "Agente",
    "Promotoría",
    "Aseguradora",
    "Clave de agente",
    "Cliente / Prospecto",
    "RFC",
    "Ramo",
    "Producto",
    "Estatus",
    "Cotizaciones",
    "ID",
)
_workbook_lock = threading.RLock()
_agent_cache_lock = threading.RLock()
_agent_cache: tuple[float, list[dict[str, str]]] | None = None


class QuoteCreate(BaseModel):
    client_id: str | None = None
    prospect_name: str | None = Field(default=None, max_length=255)
    ramo: str
    producto: str
    agent_rfc: str | None = None
    agent_promotoria: str | None = None

    @model_validator(mode="after")
    def validate_client_and_product(self):
        if bool(self.client_id) == bool(str(self.prospect_name or "").strip()):
            raise ValueError("Selecciona un cliente existente o captura un prospecto")
        products = PRODUCTS.get(self.ramo)
        if not products:
            raise ValueError("El ramo debe ser GMM o Vida")
        if self.producto not in products:
            raise ValueError(f"El producto no corresponde al ramo {self.ramo}")
        return self


def _file_id() -> str:
    return os.getenv(QUOTES_FILE_ID_ENV, "").strip() or DEFAULT_QUOTES_FILE_ID


def _build_writable_drive_service():
    try:
        from google.auth import default
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError("Faltan las dependencias de Google Drive") from exc
    credentials, _ = default(scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _upload_workbook(workbook_bytes: bytes) -> None:
    try:
        from googleapiclient.http import MediaIoBaseUpload
    except ImportError as exc:
        raise RuntimeError("Faltan las dependencias de Google Drive") from exc
    media = MediaIoBaseUpload(
        io.BytesIO(workbook_bytes),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        resumable=False,
    )
    _build_writable_drive_service().files().update(
        fileId=_file_id(), media_body=media, supportsAllDrives=True
    ).execute()


def _load_workbook():
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl es necesario para administrar cotizaciones") from exc
    return load_workbook(io.BytesIO(download_drive_file_bytes(_file_id())))


def _sheet_and_headers(workbook):
    sheet = workbook.active
    headers: dict[str, int] = {}
    for index, cell in enumerate(sheet[1], start=1):
        value = str(cell.value or "").strip()
        if value:
            headers[value] = index
    for header in HEADERS:
        if header not in headers:
            column = sheet.max_column + 1
            sheet.cell(row=1, column=column, value=header)
            headers[header] = column
    return sheet, headers


def _serialize_row(sheet, headers: dict[str, int], row_number: int) -> dict[str, str]:
    return {
        "id": str(sheet.cell(row=row_number, column=headers["ID"]).value or ""),
        "cliente": str(sheet.cell(row=row_number, column=headers["Cliente / Prospecto"]).value or ""),
        "rfc": str(sheet.cell(row=row_number, column=headers["RFC"]).value or ""),
        "ramo": str(sheet.cell(row=row_number, column=headers["Ramo"]).value or ""),
        "producto": str(sheet.cell(row=row_number, column=headers["Producto"]).value or ""),
        "estatus": str(sheet.cell(row=row_number, column=headers["Estatus"]).value or ""),
        "cotizaciones": str(sheet.cell(row=row_number, column=headers["Cotizaciones"]).value or ""),
        "agente": str(sheet.cell(row=row_number, column=headers["Agente"]).value or ""),
        "promotoria": str(sheet.cell(row=row_number, column=headers["Promotoría"]).value or ""),
        "aseguradora": str(sheet.cell(row=row_number, column=headers["Aseguradora"]).value or ""),
        "clave_agente": str(sheet.cell(row=row_number, column=headers["Clave de agente"]).value or ""),
    }


def parse_agent_directory(workbook_bytes: bytes) -> list[dict[str, str]]:
    excel = pd.ExcelFile(io.BytesIO(workbook_bytes))
    sheet_name = "Datos" if "Datos" in excel.sheet_names else excel.sheet_names[0]
    table = pd.read_excel(
        io.BytesIO(workbook_bytes),
        sheet_name=sheet_name,
        dtype=str,
        keep_default_na=False,
    )
    required = {"RFC", "Promotoria", "CLAVE_DEFINITIVA", "CLAVE_ARRANQUE"}
    missing = sorted(required.difference(table.columns))
    if missing:
        raise ValueError("La base de agentes no contiene: " + ", ".join(missing))

    agents: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for _, row in table.iterrows():
        rfc = "".join(str(row.get("RFC") or "").upper().split())
        promotoria = str(row.get("Promotoria") or "").strip().upper()
        definitive_key = str(row.get("CLAVE_DEFINITIVA") or "").strip()
        start_key = str(row.get("CLAVE_ARRANQUE") or "").strip()
        key = definitive_key or start_key
        if not rfc or not promotoria or not key or (rfc, promotoria) in seen:
            continue
        parts = [
            str(row.get("Nombres") or "").strip(),
            str(row.get("Apellido_Paterno") or "").strip(),
            str(row.get("Apellido_Materno") or "").strip(),
        ]
        name = " ".join(part for part in parts if part)
        if not name:
            name = str(row.get("Nombre") or "").strip()
        agents.append(
            {
                "rfc": rfc,
                "name": name.title() or "Nombre no registrado",
                "promotoria": promotoria,
                "key": key,
                "key_source": "CLAVE_DEFINITIVA" if definitive_key else "CLAVE_ARRANQUE",
            }
        )
        seen.add((rfc, promotoria))
    return sorted(agents, key=lambda item: (item["promotoria"], item["name"], item["rfc"]))


def load_agent_directory() -> list[dict[str, str]]:
    global _agent_cache
    now = time.monotonic()
    cache_seconds = max(0, int(os.getenv("QUOTES_AGENTS_CACHE_SECONDS", "300")))
    with _agent_cache_lock:
        if _agent_cache and now < _agent_cache[0]:
            return _agent_cache[1]
        file_id = os.getenv(AGENTS_FILE_ID_ENV, "").strip() or DEFAULT_AGENTS_FILE_ID
        agents = parse_agent_directory(download_drive_file_bytes(file_id))
        _agent_cache = (now + cache_seconds, agents)
        return agents


def agents_for_profile(profile: AccessProfile) -> list[dict[str, str]]:
    allowed_promotorias = set(profile.promotorias)
    agents = [agent for agent in load_agent_directory() if agent["promotoria"] in allowed_promotorias]
    if profile.is_agent:
        profile_rfc = "".join(profile.rfc.upper().split())
        agents = [agent for agent in agents if agent["rfc"] == profile_rfc]
    return agents


def assigned_agent(
    profile: AccessProfile,
    requested_rfc: str | None,
    requested_promotoria: str | None = None,
) -> dict[str, str]:
    options = agents_for_profile(profile)
    if profile.is_agent:
        if not profile.rfc:
            raise ValueError("Tu usuario no tiene RFC de agente configurado en Accesos")
        if len(options) != 1:
            raise ValueError("No fue posible identificar una única clave MetLife para tu usuario")
        return options[0]
    selected = "".join(str(requested_rfc or "").upper().split())
    selected_promotoria = str(requested_promotoria or "").strip().upper()
    matches = [
        agent for agent in options
        if agent["rfc"] == selected and agent["promotoria"] == selected_promotoria
    ]
    if not selected:
        raise ValueError("Selecciona el agente responsable de la cotización")
    if len(matches) != 1:
        raise ValueError("El agente no pertenece a una promotoría autorizada para tu usuario")
    return matches[0]


def list_quotes() -> list[dict[str, str]]:
    workbook = _load_workbook()
    sheet, headers = _sheet_and_headers(workbook)
    rows = []
    for row_number in range(2, sheet.max_row + 1):
        row = _serialize_row(sheet, headers, row_number)
        if any(row.values()):
            rows.append(row)
    return rows


def create_quote(payload: QuoteCreate, profile: AccessProfile) -> dict[str, str]:
    agent = assigned_agent(profile, payload.agent_rfc, payload.agent_promotoria)
    db = SessionLocal()
    try:
        if payload.client_id:
            client = db.query(Client).filter(Client.id == payload.client_id).first()
            if not client:
                raise ValueError("El cliente seleccionado ya no existe")
            name = client.full_name.strip()
            rfc = "".join(str(client.rfc or "").upper().split())
            if not rfc:
                raise ValueError("El cliente seleccionado no tiene RFC; regístralo como prospecto")
        else:
            name = " ".join(str(payload.prospect_name or "").split())
            rfc = ""
            if len(name) < 2:
                raise ValueError("Captura el nombre del prospecto")
    finally:
        db.close()

    quote_id = f"COT-{datetime.now(timezone.utc):%Y%m%d}-{uuid.uuid4().hex[:6].upper()}"
    values = {
        "ID": quote_id,
        "Agente": agent["name"],
        "Promotoría": agent["promotoria"],
        "Aseguradora": "MetLife",
        "Clave de agente": agent["key"],
        "Cliente / Prospecto": name,
        "RFC": rfc,
        "Ramo": payload.ramo,
        "Producto": payload.producto,
        "Estatus": INITIAL_STATUS,
        "Cotizaciones": "",
    }
    with _workbook_lock:
        workbook = _load_workbook()
        sheet, headers = _sheet_and_headers(workbook)
        row_number = sheet.max_row + 1
        for header, value in values.items():
            sheet.cell(row=row_number, column=headers[header], value=value)
        output = io.BytesIO()
        workbook.save(output)
        _upload_workbook(output.getvalue())
        return _serialize_row(sheet, headers, row_number)


@router.get("/config")
def get_quotes_config(profile: AccessProfile = Depends(current_access_profile)):
    agents = agents_for_profile(profile)
    return {
        "products": PRODUCTS,
        "initial_status": INITIAL_STATUS,
        "insurer": "MetLife",
        "agents": agents,
        "agent_is_automatic": profile.is_agent,
    }


@router.get("")
def get_quotes():
    try:
        return {"quotes": list_quotes()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo leer Cotizaciones.xlsx: {exc}") from exc


@router.get("/clients")
def search_clients(q: str = Query(min_length=2, max_length=120)):
    term = q.strip()
    normalized_rfc = "".join(term.upper().split())
    db = SessionLocal()
    try:
        clients = (
            db.query(Client)
            .filter(
                or_(
                    Client.full_name.ilike(f"%{term}%"),
                    Client.rfc.ilike(f"%{normalized_rfc}%"),
                )
            )
            .order_by(Client.full_name)
            .limit(20)
            .all()
        )
        return {
            "clients": [
                {"id": client.id, "nombre": client.full_name, "rfc": client.rfc or ""}
                for client in clients
            ]
        }
    finally:
        db.close()


@router.post("", status_code=201)
def add_quote(
    payload: QuoteCreate,
    profile: AccessProfile = Depends(current_access_profile),
):
    try:
        return {"quote": create_quote(payload, profile)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo registrar la cotización: {exc}") from exc
