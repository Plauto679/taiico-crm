from __future__ import annotations

import io
import os
import threading
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import or_

from database import Client, SessionLocal
from drive.client import download_drive_file_bytes


router = APIRouter(prefix="/cotizaciones", tags=["cotizaciones"])

QUOTES_FILE_ID_ENV = "GOOGLE_DRIVE_QUOTES_FILE_ID"
DEFAULT_QUOTES_FILE_ID = "1uP-G9GAz75SyO4nUhrJlaHDhX5zJ6vk4"
PRODUCTS = {
    "GMM": ("Medicalife Familiar", "Medicalife PG", "Primordial"),
    "Vida": ("Metalife", "Totalife", "Flexilife", "Horizonte", "Temporal"),
}
INITIAL_STATUS = "Pendiente de cotización"
HEADERS = ("ID", "Cliente / Prospecto", "RFC", "Ramo", "Producto", "Estatus", "Cotizaciones")
_workbook_lock = threading.RLock()


class QuoteCreate(BaseModel):
    client_id: str | None = None
    prospect_name: str | None = Field(default=None, max_length=255)
    ramo: str
    producto: str

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
    # El archivo original trae una primera columna sin encabezado; se reutiliza para el ID.
    if "ID" not in headers and sheet.max_column >= len(HEADERS):
        sheet.cell(row=1, column=1, value="ID")
        headers["ID"] = 1
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
    }


def list_quotes() -> list[dict[str, str]]:
    workbook = _load_workbook()
    sheet, headers = _sheet_and_headers(workbook)
    rows = []
    for row_number in range(2, sheet.max_row + 1):
        row = _serialize_row(sheet, headers, row_number)
        if any(row.values()):
            rows.append(row)
    return rows


def create_quote(payload: QuoteCreate) -> dict[str, str]:
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
def get_quotes_config():
    return {"products": PRODUCTS, "initial_status": INITIAL_STATUS}


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
def add_quote(payload: QuoteCreate):
    try:
        return {"quote": create_quote(payload)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo registrar la cotización: {exc}") from exc
