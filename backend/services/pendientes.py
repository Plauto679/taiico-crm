from __future__ import annotations

import io
import os
import posixpath
import re
import threading
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree
from xml.sax.saxutils import escape

import pandas as pd
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from pydantic import BaseModel

from services.session_auth import current_username
from services.pending_document_requirements import requirements_for


load_dotenv(Path(__file__).resolve().parents[1] / ".env")
router = APIRouter(prefix="/pendientes", tags=["pendientes"])

DEFAULT_EMISION_SERVICIOS_FILE_ID = "1JMr-EwtniwHvPm6zefhGJroTw2vxivmC"
DEFAULT_SINIESTROS_FILE_ID = "1UvXo2LboTKWl5323mEuP6bmmyIhLYveL"
DEFAULT_PENDING_DOCUMENTS_FOLDER_ID = "1IIIgHB8SlEIZr5vSAuly14NJMO50ke1b"
DEFAULT_CACHE_SECONDS = 300
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024

GMM_REQUEST_OPTIONS = {
    "EMISION PERSONA FISICA",
    "EMISION PERSONA MORAL",
    "Modificación de nombre y apellidos GMM",
    "Cambio de contratante GMM",
    "Cambio de domicilio GMM",
    "Corrección RFC GMM",
    "Cambio de beneficiario GMM",
    "Duplicado de póliza GMM",
    "Duplicado de endoso GMM",
    "Cambio clave de agente",
    "Reconocimiento de antigüedad",
    "Rehabilitación GMM",
    "Cambio de conducto de cobro (Débito o crédito)",
    "Cambio de conducto de cobro (Conducto Agente)",
    "Cambio de forma de pago GMM",
    "Inclusión/Exclusión De Coberturas GMM",
    "Inclusión/Exclusión De Dependientes GMM",
    "Cancelación de pólizas GMM",
    "Aclaración de pagos GMM",
    "Aplicación de pagos GMM",
    "Reembolso GMM",
}

VIDA_REQUEST_OPTIONS = {
    "EMISION PERSONA FISICA",
    "EMISION PERSONA MORAL",
    "Modificación de nombre y apellidos VIDA",
    "Cambio de contratante VIDA",
    "Cambio de domicilio VIDA",
    "Corrección RFC VIDA",
    "Cambio de beneficiario VIDA",
    "Duplicado de póliza GMM",
    "Cambio clave de agente VIDA",
    "Rehabilitación VIDA",
    "Cambio de conducto de cobro (Débito o crédito)",
    "Cambio de conducto de cobro (Conducto Agente)",
    "Duplicado de recibo VIDA",
    "Cambio de forma de pago VIDA",
    "Corrección de edad / Corrección fecha de nacimiento VIDA",
    "Inclusión/Exclusión De Coberturas VIDA",
    "Rescate total / parcial VIDA",
    "Devolución de primas VIDA",
    "Aclaración de pagos VIDA",
    "Aplicación de pagos VIDA",
}


class EmisionServiciosCreateRequest(BaseModel):
    asegurado: str
    rfc: str
    poliza: str
    casificacion: Literal["Vida", "GMM"]
    tipo_tramite: Literal["Servicios", "Emisión"]
    solicitud_de: str


class SiniestrosCreateRequest(BaseModel):
    asegurado: str
    rfc: str
    tipo_tramite: Literal[
        "Cirugía Progamada",
        "Reembolso",
        "Programación de Medicamentos",
        "Programación de estudios/terapias",
    ]
    tramite: Literal["Complemento", "Reconsideración", "Garantías"]


@dataclass(frozen=True)
class PendingSource:
    key: str
    title: str
    file_id_env: str
    default_file_id: str
    sheet_name: str
    core_column_count: int


SOURCES = {
    "emision-servicios": PendingSource(
        key="emision-servicios",
        title="Emisión y Servicios",
        file_id_env="GOOGLE_DRIVE_PENDING_EMISION_SERVICIOS_FILE_ID",
        default_file_id=DEFAULT_EMISION_SERVICIOS_FILE_ID,
        sheet_name="Base1",
        core_column_count=15,
    ),
    "siniestros": PendingSource(
        key="siniestros",
        title="Siniestros",
        file_id_env="GOOGLE_DRIVE_PENDING_SINIESTROS_FILE_ID",
        default_file_id=DEFAULT_SINIESTROS_FILE_ID,
        sheet_name="Base",
        core_column_count=12,
    ),
}

_cache_lock = threading.Lock()
_write_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}


def clean_cell(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().split())


def parse_pending_workbook(workbook: bytes, source: PendingSource) -> dict:
    table = pd.read_excel(
        io.BytesIO(workbook),
        sheet_name=source.sheet_name,
        dtype=str,
        keep_default_na=False,
    )
    headers = [clean_cell(column) for column in table.columns]
    if len(headers) <= source.core_column_count:
        raise ValueError(
            f"{source.title} sheet {source.sheet_name} must contain more than "
            f"{source.core_column_count} columns"
        )

    core_headers = headers[: source.core_column_count]
    history_headers = headers[source.core_column_count :]
    latest_header = history_headers[-1]
    rows = []

    for index, (_, series) in enumerate(table.iterrows(), start=2):
        values = [clean_cell(value) for value in series.tolist()]
        core_values = values[: source.core_column_count]
        if not any(core_values):
            continue

        history_values = values[source.core_column_count :]
        history = [
            {"date": header, "update": value}
            for header, value in zip(history_headers, history_values)
            if value
        ]
        rows.append({
            "id": f"{source.key}:{index}",
            "source_row": index,
            "summary": dict(zip(core_headers, core_values)),
            "latest_update": {
                "date": latest_header,
                "update": history_values[-1] if history_values else "",
            },
            "history": history,
        })

    return {
        "source": source.key,
        "title": source.title,
        "sheet_name": source.sheet_name,
        "core_headers": core_headers,
        "latest_update_header": latest_header,
        "rows": rows,
    }


def build_pending_drive_service():
    credentials, _ = default(scopes=[DRIVE_SCOPE])
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _documents_root_id() -> str:
    return os.getenv(
        "GOOGLE_DRIVE_PENDING_DOCUMENTS_FOLDER_ID",
        DEFAULT_PENDING_DOCUMENTS_FOLDER_ID,
    ).strip()


def _rfc_from_row(row: dict) -> str:
    return clean_cell(row.get("summary", {}).get("RFC", "")).upper()


def _folder_name_for_rfc(rfc: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "-", clean_cell(rfc).upper())
    if not cleaned:
        raise ValueError("El RFC es obligatorio para integrar el expediente")
    return cleaned[:180]


def _document_name_for(value: str, original_filename: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "-", clean_cell(value))
    if not cleaned:
        raise ValueError("El nombre del documento es obligatorio")
    original_suffix = Path(original_filename or "").suffix
    if original_suffix and not Path(cleaned).suffix:
        cleaned = f"{cleaned}{original_suffix.lower()}"
    return cleaned[:220]


def _list_pending_folders(service) -> list[dict]:
    response = service.files().list(
        q=(
            f"'{_documents_root_id()}' in parents and "
            f"mimeType = '{FOLDER_MIME_TYPE}' and trashed = false"
        ),
        fields="files(id,name,webViewLink,modifiedTime)",
        supportsAllDrives=True,
        includeItemsFromAllDrives=True,
        pageSize=1000,
    ).execute()
    return response.get("files", [])


def _decorate_rows_with_folders(result: dict, service) -> dict:
    folders = {
        clean_cell(folder.get("name", "")).casefold(): folder
        for folder in _list_pending_folders(service)
    }
    for row in result["rows"]:
        rfc = _rfc_from_row(row)
        folder_name = _folder_name_for_rfc(rfc) if rfc else ""
        folder = folders.get(folder_name.casefold()) if folder_name else None
        row["folder_name"] = folder_name
        row["folder_id"] = folder.get("id") if folder else None
        row["folder_url"] = folder.get("webViewLink") if folder else None
    result["documents_folder_id"] = _documents_root_id()
    result["documents_folder_url"] = f"https://drive.google.com/drive/folders/{_documents_root_id()}"
    return result


def _create_folder_for_row(service, row: dict) -> dict:
    rfc = _rfc_from_row(row)
    folder_name = _folder_name_for_rfc(rfc)
    existing = next(
        (
            folder for folder in _list_pending_folders(service)
            if clean_cell(folder.get("name", "")).casefold() == folder_name.casefold()
        ),
        None,
    )
    folder = existing or service.files().create(
        body={
            "name": folder_name,
            "parents": [_documents_root_id()],
            "mimeType": FOLDER_MIME_TYPE,
        },
        fields="id,name,webViewLink",
        supportsAllDrives=True,
    ).execute()
    row["folder_name"] = folder_name
    row["folder_id"] = folder.get("id")
    row["folder_url"] = folder.get("webViewLink")
    return row


def _requirements_for_row(row: dict) -> list[str]:
    summary = row.get("summary", {})
    return requirements_for(
        clean_cell(summary.get("Casificacion", "")),
        clean_cell(summary.get("Solicitud de", "")),
    )


def _download_workbook(file_id: str, service=None) -> bytes:
    service = service or build_pending_drive_service()
    output = io.BytesIO()
    request = service.files().get_media(
        fileId=file_id,
        supportsAllDrives=True,
    )
    downloader = MediaIoBaseDownload(output, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return output.getvalue()


def append_pending_record(workbook: bytes, source: PendingSource, values: dict[str, str]) -> tuple[bytes, int]:
    parsed = parse_pending_workbook(workbook, source)
    next_row = max((row["source_row"] for row in parsed["rows"]), default=1) + 1
    header_columns = {header: index + 1 for index, header in enumerate(parsed["core_headers"])}
    missing = sorted(set(values).difference(header_columns))
    if missing:
        raise ValueError("La base no contiene las columnas: " + ", ".join(missing))
    indexed_values = {
        header_columns[header]: clean_cell(value)
        for header, value in values.items()
    }
    return _append_xlsx_row(workbook, source.sheet_name, next_row, indexed_values), next_row


def _append_xlsx_row(
    workbook: bytes,
    sheet_name: str,
    row_number: int,
    values: dict[int, str],
) -> bytes:
    with zipfile.ZipFile(io.BytesIO(workbook), "r") as archive:
        sheet_path = _worksheet_path(archive, sheet_name)
        sheet_xml = archive.read(sheet_path).decode("utf-8")
        updated_xml = _insert_sheet_row(sheet_xml, row_number, values)
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as destination:
            for item in archive.infolist():
                content = updated_xml.encode("utf-8") if item.filename == sheet_path else archive.read(item.filename)
                destination.writestr(item, content)
    return output.getvalue()


def _worksheet_path(archive: zipfile.ZipFile, sheet_name: str) -> str:
    workbook_root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    main_namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    relationship_namespace = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    relationship_id = None
    for sheet in workbook_root.findall(f".//{{{main_namespace}}}sheet"):
        if sheet.attrib.get("name") == sheet_name:
            relationship_id = sheet.attrib.get(f"{{{relationship_namespace}}}id")
            break
    if not relationship_id:
        raise ValueError(f"No se encontró la pestaña {sheet_name}")

    relationships = ElementTree.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    package_namespace = "http://schemas.openxmlformats.org/package/2006/relationships"
    for relationship in relationships.findall(f"{{{package_namespace}}}Relationship"):
        if relationship.attrib.get("Id") == relationship_id:
            target = relationship.attrib["Target"].lstrip("/")
            return target if target.startswith("xl/") else posixpath.normpath(posixpath.join("xl", target))
    raise ValueError(f"No se encontró el archivo interno de la pestaña {sheet_name}")


def _insert_sheet_row(sheet_xml: str, row_number: int, values: dict[int, str]) -> str:
    sheet_data = re.search(r"(<sheetData>)(.*?)(</sheetData>)", sheet_xml, flags=re.DOTALL)
    if not sheet_data:
        raise ValueError("La pestaña no contiene una tabla de datos válida")

    rows_xml = sheet_data.group(2)
    row_pattern = re.compile(r'<row\b[^>]*\br="(\d+)"[^>]*(?:/>|>.*?</row>)', re.DOTALL)
    rows = list(row_pattern.finditer(rows_xml))
    if any(int(match.group(1)) == row_number for match in rows):
        raise ValueError(f"La fila {row_number} ya está ocupada")

    previous = next((match for match in reversed(rows) if int(match.group(1)) < row_number), None)
    styles = _cell_styles(previous.group(0), int(previous.group(1))) if previous else {}
    max_column = max([*styles.keys(), *values.keys()], default=max(values, default=1))
    cells = []
    for column in range(1, max_column + 1):
        cell_reference = f"{_column_letter(column)}{row_number}"
        style = f' s="{styles[column]}"' if column in styles else ""
        if column in values:
            cell_value = escape(values[column])
            cells.append(
                f'<c r="{cell_reference}"{style} t="inlineStr"><is><t xml:space="preserve">{cell_value}</t></is></c>'
            )
        elif column in styles:
            cells.append(f'<c r="{cell_reference}"{style}/>')
    new_row = f'<row r="{row_number}">{"".join(cells)}</row>'

    insertion_point = next((match.start() for match in rows if int(match.group(1)) > row_number), len(rows_xml))
    updated_rows = rows_xml[:insertion_point] + new_row + rows_xml[insertion_point:]
    updated_xml = sheet_xml[:sheet_data.start(2)] + updated_rows + sheet_xml[sheet_data.end(2):]
    return _extend_dimension(updated_xml, row_number)


def _cell_styles(row_xml: str, row_number: int) -> dict[int, str]:
    styles = {}
    for cell in re.finditer(r'<c\b([^>]*)\br="([A-Z]+)' + str(row_number) + r'"([^>]*)>', row_xml):
        attributes = cell.group(1) + cell.group(3)
        style = re.search(r'\bs="(\d+)"', attributes)
        if style:
            styles[_column_number(cell.group(2))] = style.group(1)
    return styles


def _column_letter(number: int) -> str:
    letters = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _column_number(letters: str) -> int:
    number = 0
    for character in letters:
        number = number * 26 + ord(character) - 64
    return number


def _extend_dimension(sheet_xml: str, row_number: int) -> str:
    match = re.search(r'<dimension ref="([A-Z]+\d+):([A-Z]+)(\d+)"', sheet_xml)
    if not match or int(match.group(3)) >= row_number:
        return sheet_xml
    replacement = f'<dimension ref="{match.group(1)}:{match.group(2)}{row_number}"'
    return sheet_xml[:match.start()] + replacement + sheet_xml[match.end():]


def _upload_workbook(file_id: str, workbook: bytes, service) -> None:
    service.files().update(
        fileId=file_id,
        media_body=MediaIoBaseUpload(
            io.BytesIO(workbook),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            resumable=False,
        ),
        supportsAllDrives=True,
    ).execute()


def _source_file_id(source: PendingSource) -> str:
    file_id = os.getenv(source.file_id_env, source.default_file_id).strip()
    if not file_id:
        raise RuntimeError(f"{source.file_id_env} is not configured")
    return file_id


def _clear_source_cache(source_key: str) -> None:
    with _cache_lock:
        _cache.pop(source_key, None)


def load_pending_source(source: PendingSource, service=None) -> dict:
    cache_seconds = max(
        0,
        int(os.getenv("PENDING_SOURCES_CACHE_SECONDS", str(DEFAULT_CACHE_SECONDS))),
    )
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(source.key)
        if cached and now < cached[0]:
            return cached[1]

        service = service or build_pending_drive_service()
        file_id = _source_file_id(source)
        result = parse_pending_workbook(_download_workbook(file_id, service), source)
        _decorate_rows_with_folders(result, service)
        result["source_file_id"] = file_id
        _cache[source.key] = (now + cache_seconds, result)
        return result


@router.get("/{source_key}")
async def get_pending_source(source_key: str):
    source = SOURCES.get(source_key)
    if not source:
        raise HTTPException(status_code=404, detail="Unknown pending source")
    try:
        return load_pending_source(source)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unable to load canonical {source.title} workbook: {exc}",
        ) from exc


@router.post("/emision-servicios")
def create_emision_servicios_pending(
    request: EmisionServiciosCreateRequest,
    _username: str = Depends(current_username),
):
    allowed_requests = GMM_REQUEST_OPTIONS if request.casificacion == "GMM" else VIDA_REQUEST_OPTIONS
    if request.solicitud_de not in allowed_requests:
        raise HTTPException(
            status_code=422,
            detail=f"Solicitud de no válida para {request.casificacion}",
        )
    values = {
        "Asegurado": request.asegurado,
        "RFC": request.rfc.strip().upper(),
        "Póliza": request.poliza,
        "Casificacion": request.casificacion,
        "Tipo de Trámite": request.tipo_tramite,
        "Solicitud de": request.solicitud_de,
    }
    return _create_pending_record(SOURCES["emision-servicios"], values)


@router.post("/siniestros")
def create_siniestros_pending(
    request: SiniestrosCreateRequest,
    _username: str = Depends(current_username),
):
    values = {
        "ASEGURADO": request.asegurado,
        "RFC": request.rfc.strip().upper(),
        "Tipo de Trámite": request.tipo_tramite,
        "Trámite": request.tramite,
    }
    return _create_pending_record(SOURCES["siniestros"], values)


def _create_pending_record(source: PendingSource, values: dict[str, str]):
    if not clean_cell(values.get("Asegurado") or values.get("ASEGURADO")):
        raise HTTPException(status_code=422, detail="El nombre del asegurado es obligatorio")
    if not clean_cell(values.get("RFC")):
        raise HTTPException(status_code=422, detail="El RFC es obligatorio")
    try:
        with _write_lock:
            service = build_pending_drive_service()
            file_id = _source_file_id(source)
            updated, source_row = append_pending_record(
                _download_workbook(file_id, service),
                source,
                values,
            )
            _upload_workbook(file_id, updated, service)
            _clear_source_cache(source.key)
            refreshed = load_pending_source(source, service)
            created = next((row for row in refreshed["rows"] if row["source_row"] == source_row), None)
        if not created:
            raise RuntimeError("El registro se guardó, pero no pudo releerse desde Drive")
        folder_warning = None
        if not created.get("folder_id"):
            try:
                _create_folder_for_row(service, created)
                _clear_source_cache(source.key)
            except Exception as exc:
                folder_warning = f"El registro se guardó, pero no fue posible crear su carpeta: {exc}"
        return {"created": True, "row": created, "folder_warning": folder_warning}
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No fue posible registrar el pendiente en {source.title}: {exc}",
        ) from exc


def _get_pending_row(source_key: str, source_row: int, service=None) -> tuple[PendingSource, dict]:
    source = SOURCES.get(source_key)
    if not source:
        raise HTTPException(status_code=404, detail="Fuente de pendientes no encontrada")
    result = load_pending_source(source, service)
    row = next((item for item in result["rows"] if item["source_row"] == source_row), None)
    if not row:
        raise HTTPException(status_code=404, detail="Pendiente no encontrado en el archivo canónico")
    return source, row


@router.get("/{source_key}/{source_row}/documents")
def get_pending_documents(source_key: str, source_row: int):
    try:
        service = build_pending_drive_service()
        _, row = _get_pending_row(source_key, source_row, service)
        if not row.get("folder_id"):
            return {
                "row": row,
                "folder_missing": True,
                "required_documents": _requirements_for_row(row),
                "documents": [],
            }
        response = service.files().list(
            q=f"'{row['folder_id']}' in parents and trashed = false",
            fields="files(id,name,mimeType,webViewLink,modifiedTime,size)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            orderBy="folder,name",
            pageSize=1000,
        ).execute()
        return {
            "row": row,
            "folder_missing": False,
            "required_documents": _requirements_for_row(row),
            "documents": response.get("files", []),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No fue posible consultar el expediente: {exc}") from exc


@router.post("/{source_key}/{source_row}/folder")
def create_pending_folder(
    source_key: str,
    source_row: int,
    _username: str = Depends(current_username),
):
    try:
        service = build_pending_drive_service()
        source, row = _get_pending_row(source_key, source_row, service)
        if row.get("folder_id"):
            return {"created": False, "row": row}
        _create_folder_for_row(service, row)
        _clear_source_cache(source.key)
        return {"created": True, "row": row}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No fue posible crear la carpeta del pendiente: {exc}") from exc


@router.post("/{source_key}/{source_row}/documents")
async def upload_pending_document(
    source_key: str,
    source_row: int,
    document_name: str = Form(...),
    document: UploadFile = File(...),
    _username: str = Depends(current_username),
):
    try:
        service = build_pending_drive_service()
        _, row = _get_pending_row(source_key, source_row, service)
        if not row.get("folder_id"):
            raise HTTPException(status_code=409, detail="Primero debe crearse la carpeta del expediente")

        final_name = _document_name_for(document_name, document.filename or "")
        existing = service.files().list(
            q=f"'{row['folder_id']}' in parents and trashed = false",
            fields="files(id,name)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageSize=1000,
        ).execute().get("files", [])
        existing_document = next(
            (item for item in existing if clean_cell(item.get("name", "")).casefold() == final_name.casefold()),
            None,
        )

        content = await document.read(MAX_DOCUMENT_BYTES + 1)
        if not content:
            raise HTTPException(status_code=400, detail="El archivo está vacío")
        if len(content) > MAX_DOCUMENT_BYTES:
            raise HTTPException(status_code=413, detail="El archivo supera el límite de 25 MB")

        media = MediaIoBaseUpload(
            io.BytesIO(content),
            mimetype=document.content_type or "application/octet-stream",
            resumable=False,
        )
        if existing_document:
            saved = service.files().update(
                fileId=existing_document["id"],
                media_body=media,
                fields="id,name,mimeType,webViewLink,modifiedTime,size",
                supportsAllDrives=True,
            ).execute()
        else:
            saved = service.files().create(
                body={"name": final_name, "parents": [row["folder_id"]]},
                media_body=media,
                fields="id,name,mimeType,webViewLink,modifiedTime,size",
                supportsAllDrives=True,
            ).execute()
        return {"uploaded": True, "replaced": bool(existing_document), "document": saved}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No fue posible cargar el documento: {exc}") from exc
    finally:
        await document.close()
