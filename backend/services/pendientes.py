from __future__ import annotations

import io
import os
import posixpath
import re
import threading
import time
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal
from xml.etree import ElementTree
from xml.sax.saxutils import escape, quoteattr
from zoneinfo import ZoneInfo

import pandas as pd
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from pydantic import BaseModel, Field

from services.session_auth import current_username
from services.pending_document_requirements import requirements_for, split_request_types
from services.mail_configuration import smtp_settings_for
from services.renovaciones import send_email_smtp


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
    rfc: str = ""
    poliza: str = ""
    casificacion: Literal["Vida", "GMM"]
    tipo_tramite: Literal["Servicios", "Emisión"]
    solicitud_de: str


class SiniestrosCreateRequest(BaseModel):
    asegurado: str
    rfc: str = ""
    tipo_tramite: Literal[
        "Cirugía Progamada",
        "Reembolso",
        "Programación de Medicamentos",
        "Programación de estudios/terapias",
    ]
    tramite: Literal["Complemento", "Reconsideración", "Garantías"]


class PendingFollowUpRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=5000)


class PendingUpdateRequest(BaseModel):
    values: dict[str, str]


class PendingReportRequest(BaseModel):
    emails: list[str] = Field(default_factory=list, max_length=50)
    # Kept temporarily for backwards compatibility with older CRM clients.
    email: str | None = Field(default=None, min_length=3, max_length=320)


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

REPORT_COLORS = ("verde", "amarillo", "rojo")
REPORT_COLOR_LABELS = {
    "verde": "Verde",
    "amarillo": "Amarillo",
    "rojo": "Rojo",
}


def clean_cell(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().split())


def _normalized_header(value: str) -> str:
    return " ".join(
        unicodedata.normalize("NFKD", clean_cell(value))
        .encode("ascii", "ignore")
        .decode("ascii")
        .casefold()
        .split()
    )


def _looks_like_history_header(value: str) -> bool:
    normalized = _normalized_header(value)
    return normalized == "fecha hoy" or bool(
        re.match(
            r"^(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-](?:\d{1,2}|[a-z]{3})(?:[/-]\d{2,4})?)",
            normalized,
        )
    )


def _core_count_for_headers(source: PendingSource, headers: list[str]) -> int:
    return next(
        (
            index
            for index, header in enumerate(headers)
            if index >= source.core_column_count and _looks_like_history_header(header)
        ),
        source.core_column_count,
    )


DATE_COUNTER_PAIRS = (
    ("Fecha Inicio", "Días Transcurridos"),
    ("Fecha ingreso en la aseguradora", "Dias en la aseguradora"),
    ("Fecha de registro de siniestro", "Dias desde registro del siniestro"),
    ("Fecha de envío a la aseguradora", "DIAS CUMPLIDOS EN LA ASEGURADORA"),
    # Compatibility while the renamed Siniestros headers propagate through Drive.
    ("Fecha de envío", "DIAS CUMPLIDOS"),
)


def _parse_pending_date(value: str) -> date | None:
    text = clean_cell(value)
    if not text:
        return None
    if re.fullmatch(r"\d+(?:\.0+)?", text):
        try:
            return (datetime(1899, 12, 30) + pd.to_timedelta(float(text), unit="D")).date()
        except (OverflowError, ValueError):
            return None
    try:
        if re.match(r"^\d{4}-\d{1,2}-\d{1,2}", text):
            return datetime.fromisoformat(text[:10]).date()
        parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
        return None if pd.isna(parsed) else parsed.date()
    except (TypeError, ValueError):
        return None


def _derived_day_values(summary: dict[str, str], today: date | None = None) -> dict[str, str]:
    current_date = today or datetime.now(ZoneInfo("America/Mexico_City")).date()
    headers = {_normalized_header(header): header for header in summary}
    derived: dict[str, str] = {}
    for date_label, days_label in DATE_COUNTER_PAIRS:
        actual_date_header = headers.get(_normalized_header(date_label))
        actual_days_header = headers.get(_normalized_header(days_label))
        if not actual_date_header or not actual_days_header:
            continue
        start_date = _parse_pending_date(summary.get(actual_date_header, ""))
        derived[actual_days_header] = (
            str(max(0, (current_date - start_date).days))
            if start_date
            else ""
        )
    return derived


def _summary_value(summary: dict[str, str], label: str) -> str:
    normalized_label = _normalized_header(label)
    return next(
        (
            clean_cell(value)
            for header, value in summary.items()
            if _normalized_header(header) == normalized_label
        ),
        "",
    )


def _day_number(value: object) -> int | None:
    text = clean_cell(value)
    if not text:
        return None
    try:
        return max(0, int(float(text.replace(",", ""))))
    except ValueError:
        return None


def _traffic_color(days: int) -> str:
    if days <= 5:
        return "verde"
    if days <= 10:
        return "amarillo"
    return "rojo"


def _report_metric(
    rows: list[dict],
    *,
    key: str,
    label: str,
    days_header: str,
    only_when_blank_header: str | None = None,
) -> dict:
    details = {color: [] for color in REPORT_COLORS}
    for row in rows:
        summary = row.get("summary", {})
        if only_when_blank_header and _summary_value(summary, only_when_blank_header):
            continue
        days = _day_number(_summary_value(summary, days_header))
        if days is None:
            continue
        color = _traffic_color(days)
        details[color].append({
            "source_row": row.get("source_row"),
            "days": days,
            "summary": summary,
            "latest_update": row.get("latest_update", {}),
        })
    return {
        "key": key,
        "label": label,
        "days_header": days_header,
        "counts": {color: len(details[color]) for color in REPORT_COLORS},
        "details": details,
    }


def build_pending_report(
    emision_servicios: dict,
    siniestros: dict,
    generated_on: date | None = None,
) -> dict:
    report_date = generated_on or datetime.now(ZoneInfo("America/Mexico_City")).date()
    return {
        "generated_on": report_date.isoformat(),
        "sections": [
            {
                "key": "emision-servicios",
                "title": "Emisión y Servicios",
                "metrics": [
                    _report_metric(
                        emision_servicios["rows"],
                        key="dias-transcurridos",
                        label="Días transcurridos (registro de la emisión/servicio)",
                        days_header="Días Transcurridos",
                        only_when_blank_header="Dias en la aseguradora",
                    ),
                    _report_metric(
                        emision_servicios["rows"],
                        key="dias-en-aseguradora",
                        label="Días en la aseguradora",
                        days_header="Dias en la aseguradora",
                    ),
                ],
            },
            {
                "key": "siniestros",
                "title": "Siniestros",
                "metrics": [
                    _report_metric(
                        siniestros["rows"],
                        key="dias-desde-registro",
                        label="Días desde el registro del siniestro",
                        days_header="Dias desde registro del siniestro",
                        only_when_blank_header="DIAS CUMPLIDOS EN LA ASEGURADORA",
                    ),
                    _report_metric(
                        siniestros["rows"],
                        key="dias-en-aseguradora",
                        label="Días cumplidos en la aseguradora",
                        days_header="DIAS CUMPLIDOS EN LA ASEGURADORA",
                    ),
                ],
            },
        ],
    }


def _report_identity(detail: dict, section_key: str) -> tuple[str, str, str]:
    summary = detail["summary"]
    insured = _summary_value(summary, "Asegurado") or _summary_value(summary, "ASEGURADO")
    rfc = _summary_value(summary, "RFC")
    request = (
        _summary_value(summary, "Solicitud de")
        if section_key == "emision-servicios"
        else _summary_value(summary, "Trámite")
    )
    return insured or "—", rfc or "—", request or "—"


def pending_report_text(report: dict) -> str:
    lines = [
        "Informe de pendientes TAIICO",
        f"Fecha: {report['generated_on']}",
        "",
        "Rangos: Verde 0-5 días; Amarillo 6-10 días; Rojo más de 10 días.",
    ]
    for section in report["sections"]:
        lines.extend(["", section["title"], "=" * len(section["title"])])
        for metric in section["metrics"]:
            counts = metric["counts"]
            lines.append(
                f"{metric['label']}: Verde {counts['verde']} | "
                f"Amarillo {counts['amarillo']} | Rojo {counts['rojo']}"
            )
            for color in REPORT_COLORS:
                for detail in metric["details"][color]:
                    insured, rfc, request = _report_identity(detail, section["key"])
                    lines.append(
                        f"- {REPORT_COLOR_LABELS[color]} | {detail['days']} días | "
                        f"{insured} | {rfc} | {request}"
                    )
    return "\n".join(lines)


def pending_report_html(report: dict) -> str:
    color_styles = {
        "verde": ("#166534", "#dcfce7"),
        "amarillo": ("#854d0e", "#fef9c3"),
        "rojo": ("#991b1b", "#fee2e2"),
    }
    sections = []
    for section in report["sections"]:
        metrics = []
        for metric in section["metrics"]:
            count_cells = "".join(
                (
                    f'<td style="padding:10px;border:1px solid #cbd5e1;'
                    f'color:{color_styles[color][0]};background:{color_styles[color][1]};'
                    f'font-weight:700;text-align:center">'
                    f'{metric["counts"][color]}</td>'
                )
                for color in REPORT_COLORS
            )
            detail_groups = []
            for color in REPORT_COLORS:
                rows = []
                for detail in metric["details"][color]:
                    insured, rfc, request = _report_identity(detail, section["key"])
                    latest = detail.get("latest_update", {})
                    latest_text = (
                        f"({clean_cell(latest.get('date'))}) {clean_cell(latest.get('update'))}"
                        if clean_cell(latest.get("update"))
                        else "—"
                    )
                    rows.append(
                        "<tr>"
                        f"<td>{escape(insured)}</td><td>{escape(rfc)}</td>"
                        f"<td>{escape(request)}</td><td>{detail['days']}</td>"
                        f"<td>{escape(latest_text)}</td>"
                        "</tr>"
                    )
                if rows:
                    foreground, background = color_styles[color]
                    detail_groups.append(
                        f'<h4 style="margin:18px 0 8px;color:{foreground}">'
                        f'{REPORT_COLOR_LABELS[color]} ({len(rows)})</h4>'
                        '<table style="width:100%;border-collapse:collapse;font-size:13px">'
                        "<thead><tr><th>Asegurado</th><th>RFC</th><th>Solicitud/Trámite</th>"
                        "<th>Días</th><th>Última actualización</th></tr></thead>"
                        f"<tbody>{''.join(rows)}</tbody></table>"
                    )
            metrics.append(
                f"<h3>{escape(metric['label'])}</h3>"
                '<table style="width:100%;border-collapse:collapse">'
                "<thead><tr><th>Verde (0-5)</th><th>Amarillo (6-10)</th>"
                f"<th>Rojo (&gt;10)</th></tr></thead><tbody><tr>{count_cells}</tr></tbody></table>"
                + "".join(detail_groups)
            )
        sections.append(f"<h2>{escape(section['title'])}</h2>{''.join(metrics)}")
    return (
        "<!doctype html><html><body style=\"font-family:Arial,sans-serif;color:#0f172a\">"
        "<style>th,td{padding:8px;border:1px solid #cbd5e1;text-align:left;vertical-align:top}"
        "th{background:#e2e8f0}</style>"
        "<h1>Informe de pendientes TAIICO</h1>"
        f"<p>Fecha: {escape(report['generated_on'])}</p>"
        "<p>El detalle incluye únicamente registros clasificables en cada indicador.</p>"
        f"{''.join(sections)}</body></html>"
    )


def parse_pending_workbook(
    workbook: bytes,
    source: PendingSource,
    today: date | None = None,
) -> dict:
    table = pd.read_excel(
        io.BytesIO(workbook),
        sheet_name=source.sheet_name,
        dtype=str,
        keep_default_na=False,
    )
    headers = [clean_cell(column) for column in table.columns]
    core_column_count = _core_count_for_headers(source, headers)
    if len(headers) <= core_column_count:
        raise ValueError(
            f"{source.title} sheet {source.sheet_name} must contain more than "
            f"{core_column_count} columns"
        )

    core_headers = headers[:core_column_count]
    history_headers = headers[core_column_count:]
    latest_header = history_headers[-1]
    rows = []

    for index, (_, series) in enumerate(table.iterrows(), start=2):
        values = [clean_cell(value) for value in series.tolist()]
        core_values = values[:core_column_count]
        if not any(core_values):
            continue

        history_values = values[core_column_count:]
        history = [
            {"date": header, "update": value}
            for header, value in zip(history_headers, history_values)
            if value
        ]
        latest_update = history[-1] if history else {"date": "", "update": ""}
        summary = dict(zip(core_headers, core_values))
        summary.update(_derived_day_values(summary, today))
        rows.append({
            "id": f"{source.key}:{index}",
            "source_row": index,
            "summary": summary,
            "latest_update": latest_update,
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


def _folder_descriptor_from_row(row: dict) -> str:
    summary = row.get("summary", {})
    return clean_cell(
        summary.get("Solicitud de")
        or summary.get("Trámite")
        or summary.get("Tipo de Trámite")
        or ""
    )


def _folder_name_for_row(row: dict) -> str:
    rfc = _folder_name_for_rfc(_rfc_from_row(row))
    descriptor = re.sub(r"[\\/:*?\"<>|]+", "-", _folder_descriptor_from_row(row))
    return f"{rfc} - {descriptor}"[:180] if descriptor else rfc


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
        folder_name = _folder_name_for_row(row) if rfc else ""
        legacy_name = _folder_name_for_rfc(rfc) if rfc else ""
        folder = (
            folders.get(folder_name.casefold()) or folders.get(legacy_name.casefold())
            if folder_name
            else None
        )
        row["folder_name"] = folder_name
        row["folder_id"] = folder.get("id") if folder else None
        row["folder_url"] = folder.get("webViewLink") if folder else None
    result["documents_folder_id"] = _documents_root_id()
    result["documents_folder_url"] = f"https://drive.google.com/drive/folders/{_documents_root_id()}"
    return result


def _create_folder_for_row(service, row: dict) -> dict:
    folder_name = _folder_name_for_row(row)
    legacy_name = _folder_name_for_rfc(_rfc_from_row(row))
    existing = next(
        (
            folder for folder in _list_pending_folders(service)
            if clean_cell(folder.get("name", "")).casefold()
            in {folder_name.casefold(), legacy_name.casefold()}
        ),
        None,
    )
    if existing:
        folder = existing
        if clean_cell(existing.get("name", "")).casefold() != folder_name.casefold():
            folder = service.files().update(
                fileId=existing["id"],
                body={"name": folder_name},
                fields="id,name,webViewLink",
                supportsAllDrives=True,
            ).execute()
    else:
        folder = service.files().create(
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


def update_pending_record(
    workbook: bytes,
    source: PendingSource,
    source_row: int,
    values: dict[str, str],
) -> bytes:
    parsed = parse_pending_workbook(workbook, source)
    if not any(row["source_row"] == source_row for row in parsed["rows"]):
        raise ValueError(f"La fila {source_row} no existe en el archivo canónico")
    header_columns = {header: index + 1 for index, header in enumerate(parsed["core_headers"])}
    missing = sorted(set(values).difference(header_columns))
    if missing:
        raise ValueError("La base no contiene las columnas: " + ", ".join(missing))
    if not values:
        raise ValueError("No se recibieron cambios para guardar")
    updates = {
        (source_row, header_columns[header]): clean_cell(value)
        for header, value in values.items()
    }
    return _update_xlsx_cells(workbook, source.sheet_name, updates)


def add_pending_follow_up(
    workbook: bytes,
    source: PendingSource,
    source_row: int,
    comment: str,
    follow_up_date: date | None = None,
) -> tuple[bytes, str]:
    comment = clean_cell(comment)
    if not comment:
        raise ValueError("El comentario de seguimiento es obligatorio")

    table = pd.read_excel(
        io.BytesIO(workbook),
        sheet_name=source.sheet_name,
        dtype=str,
        keep_default_na=False,
    )
    if source_row < 2 or source_row > len(table.index) + 1:
        raise ValueError(f"La fila {source_row} no existe en el archivo canónico")

    target_date = follow_up_date or datetime.now(ZoneInfo("America/Mexico_City")).date()
    headers = [clean_cell(column) for column in table.columns]
    core_column_count = _core_count_for_headers(source, headers)
    target_column = next(
        (
            index + 1 for index, header in enumerate(headers)
            if index >= core_column_count and _history_header_matches_date(header, target_date)
        ),
        None,
    )
    header_value = _format_follow_up_header(source, target_date)
    updates: dict[tuple[int, int], str] = {}
    if target_column is None:
        target_column = len(headers) + 1
        updates[(1, target_column)] = header_value
        existing_comment = ""
    else:
        header_value = headers[target_column - 1]
        existing_comment = clean_cell(table.iloc[source_row - 2, target_column - 1])

    updates[(source_row, target_column)] = (
        f"{existing_comment} | {comment}" if existing_comment else comment
    )
    return _update_xlsx_cells(workbook, source.sheet_name, updates), header_value


def _history_header_matches_date(value: str, target: date) -> bool:
    text = clean_cell(value).casefold()
    if not text:
        return False
    iso_match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if iso_match:
        try:
            return date(*map(int, iso_match.groups())) == target
        except ValueError:
            return False

    numeric_match = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$", text)
    if numeric_match:
        day, month, year = map(int, numeric_match.groups())
        year = year + 2000 if year < 100 else year
        try:
            return date(year, month, day) == target
        except ValueError:
            return False

    month_numbers = {
        "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
        "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
    }
    named_match = re.match(r"^(\d{1,2})\s*-\s*([a-záéíóú]{3})\s*(?:-\s*(\d{2,4}))?$", text)
    if not named_match or named_match.group(2) not in month_numbers:
        return False
    day = int(named_match.group(1))
    month = month_numbers[named_match.group(2)]
    year_text = named_match.group(3)
    year = target.year if not year_text else int(year_text)
    year = year + 2000 if year < 100 else year
    try:
        return date(year, month, day) == target
    except ValueError:
        return False


def _format_follow_up_header(source: PendingSource, value: date) -> str:
    if source.key == "siniestros":
        return value.strftime("%d/%m/%Y")
    month = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")[value.month - 1]
    return f"{value.day:02d}-{month}-{value.year % 100:02d}"


def _update_xlsx_cells(
    workbook: bytes,
    sheet_name: str,
    updates: dict[tuple[int, int], str],
) -> bytes:
    with zipfile.ZipFile(io.BytesIO(workbook), "r") as archive:
        sheet_path = _worksheet_path(archive, sheet_name)
        sheet_xml = archive.read(sheet_path).decode("utf-8")
        updated_xml = _upsert_sheet_cells(sheet_xml, updates)
        replacements = {sheet_path: updated_xml.encode("utf-8")}
        new_header = next(
            ((column, value) for (row, column), value in updates.items() if row == 1),
            None,
        )
        if new_header:
            column_number, header_value = new_header
            for table_path in _related_table_paths(archive, sheet_path):
                table_xml = archive.read(table_path).decode("utf-8")
                updated_table = _extend_table_definition(
                    table_xml,
                    column_number,
                    header_value,
                )
                if updated_table != table_xml:
                    replacements[table_path] = updated_table.encode("utf-8")
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as destination:
            for item in archive.infolist():
                content = replacements.get(item.filename, archive.read(item.filename))
                destination.writestr(item, content)
    return output.getvalue()


def _related_table_paths(archive: zipfile.ZipFile, sheet_path: str) -> list[str]:
    relationships_path = posixpath.join(
        posixpath.dirname(sheet_path),
        "_rels",
        f"{posixpath.basename(sheet_path)}.rels",
    )
    if relationships_path not in archive.namelist():
        return []
    relationships = ElementTree.fromstring(archive.read(relationships_path))
    namespace = "http://schemas.openxmlformats.org/package/2006/relationships"
    paths = []
    for relationship in relationships.findall(f"{{{namespace}}}Relationship"):
        if not relationship.attrib.get("Type", "").endswith("/table"):
            continue
        target = relationship.attrib.get("Target", "")
        path = (
            target.lstrip("/")
            if target.startswith("/")
            else posixpath.normpath(posixpath.join(posixpath.dirname(sheet_path), target))
        )
        if path in archive.namelist():
            paths.append(path)
    return paths


def _extend_table_definition(table_xml: str, column_number: int, header_value: str) -> str:
    table_ref = re.search(r'(<table\b[^>]*\bref=")([A-Z]+\d+):([A-Z]+)(\d+)(")', table_xml)
    if not table_ref:
        return table_xml
    current_end_column = _column_number(table_ref.group(3))
    if column_number <= current_end_column:
        return table_xml
    if column_number != current_end_column + 1:
        raise ValueError("La nueva columna de seguimiento no es contigua a la tabla")

    new_end = _column_letter(column_number)
    replacement = (
        f'{table_ref.group(1)}{table_ref.group(2)}:{new_end}{table_ref.group(4)}{table_ref.group(5)}'
    )
    table_xml = table_xml[:table_ref.start()] + replacement + table_xml[table_ref.end():]
    table_xml = re.sub(
        rf'(<autoFilter\b[^>]*\bref="[A-Z]+\d+:)[A-Z]+(\d+")',
        rf'\g<1>{new_end}\2',
        table_xml,
        count=1,
    )

    columns = re.search(r'(<tableColumns\b[^>]*\bcount=")(\d+)("[^>]*>)(.*?)(</tableColumns>)', table_xml, re.DOTALL)
    if not columns:
        raise ValueError("La tabla no contiene una definición de columnas válida")
    next_id = max(
        [int(value) for value in re.findall(r'<tableColumn\b[^>]*\bid="(\d+)"', columns.group(4))],
        default=0,
    ) + 1
    new_column = f'<tableColumn id="{next_id}" name={quoteattr(header_value)}/>'
    new_columns = (
        f'{columns.group(1)}{int(columns.group(2)) + 1}{columns.group(3)}'
        f'{columns.group(4)}{new_column}{columns.group(5)}'
    )
    return table_xml[:columns.start()] + new_columns + table_xml[columns.end():]


def _upsert_sheet_cells(sheet_xml: str, updates: dict[tuple[int, int], str]) -> str:
    for (row_number, column_number), value in sorted(updates.items()):
        row_pattern = re.compile(
            rf'<row\b[^>]*\br="{row_number}"[^>]*(?:/>|>.*?</row>)',
            re.DOTALL,
        )
        row_match = row_pattern.search(sheet_xml)
        if not row_match:
            raise ValueError(f"La fila {row_number} no existe en la pestaña")
        updated_row = _upsert_cell_in_row(row_match.group(0), row_number, column_number, value)
        sheet_xml = sheet_xml[:row_match.start()] + updated_row + sheet_xml[row_match.end():]
        sheet_xml = _extend_dimension_to_cell(sheet_xml, column_number, row_number)
    return sheet_xml


def _upsert_cell_in_row(row_xml: str, row_number: int, column_number: int, value: str) -> str:
    cell_reference = f"{_column_letter(column_number)}{row_number}"
    cell_pattern = re.compile(
        rf'<c\b[^>]*\br="{cell_reference}"[^>]*(?:/>|>.*?</c>)',
        re.DOTALL,
    )
    existing = cell_pattern.search(row_xml)
    styles = _cell_styles(row_xml, row_number)
    style_value = styles.get(column_number)
    if style_value is None and styles:
        previous_columns = [column for column in styles if column < column_number]
        style_value = styles[max(previous_columns)] if previous_columns else styles[min(styles)]
    style = f' s="{style_value}"' if style_value is not None else ""
    cell = f'<c r="{cell_reference}"{style} t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>'
    if existing:
        return row_xml[:existing.start()] + cell + row_xml[existing.end():]
    if row_xml.endswith("/>"):
        return row_xml[:-2] + f">{cell}</row>"

    insertion_point = row_xml.rfind("</row>")
    for match in re.finditer(r'<c\b[^>]*\br="([A-Z]+)\d+"[^>]*(?:/>|>.*?</c>)', row_xml, re.DOTALL):
        if _column_number(match.group(1)) > column_number:
            insertion_point = match.start()
            break
    return row_xml[:insertion_point] + cell + row_xml[insertion_point:]


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


def _extend_dimension_to_cell(sheet_xml: str, column_number: int, row_number: int) -> str:
    match = re.search(r'<dimension ref="([A-Z]+)(\d+):([A-Z]+)(\d+)"', sheet_xml)
    if not match:
        return sheet_xml
    end_column = max(_column_number(match.group(3)), column_number)
    end_row = max(int(match.group(4)), row_number)
    replacement = (
        f'<dimension ref="{match.group(1)}{match.group(2)}:'
        f'{_column_letter(end_column)}{end_row}"'
    )
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


def normalize_report_recipients(values: list[str]) -> list[str]:
    recipients: list[str] = []
    seen: set[str] = set()
    for value in values:
        for candidate in re.split(r"[,;\n]+", str(value or "")):
            recipient = candidate.strip().casefold()
            if not recipient:
                continue
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", recipient):
                raise ValueError(f"Dirección de correo inválida: {candidate.strip()}")
            if recipient not in seen:
                recipients.append(recipient)
                seen.add(recipient)
    if not recipients:
        raise ValueError("Ingresa al menos una dirección de correo válida")
    return recipients


def deliver_pending_report(
    recipients: list[str],
    *,
    sender_username: str,
) -> dict:
    normalized_recipients = normalize_report_recipients(recipients)
    service = build_pending_drive_service()
    for source_key in SOURCES:
        _clear_source_cache(source_key)
    report = build_pending_report(
        load_pending_source(SOURCES["emision-servicios"], service),
        load_pending_source(SOURCES["siniestros"], service),
    )
    settings = smtp_settings_for(sender_username)
    send_email_smtp(
        subject=f"Informe de pendientes TAIICO - {report['generated_on']}",
        body=pending_report_text(report),
        html_body=pending_report_html(report),
        recipients=normalized_recipients,
        cc_recipients=[],
        settings=settings,
    )
    return {
        "sent": True,
        "recipient": ", ".join(normalized_recipients),
        "recipients": normalized_recipients,
        "generated_on": report["generated_on"],
        "report": report,
    }


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


@router.post("/report")
def send_pending_report(
    request: PendingReportRequest,
    username: str = Depends(current_username),
):
    requested_recipients = list(request.emails)
    if request.email:
        requested_recipients.append(request.email)
    try:
        return deliver_pending_report(
            requested_recipients,
            sender_username=username,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No fue posible enviar el informe de pendientes: {exc}",
        ) from exc


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
    selected_requests = split_request_types(request.solicitud_de)
    invalid_requests = [
        selected_request
        for selected_request in selected_requests
        if selected_request not in allowed_requests
    ]
    if not selected_requests or invalid_requests:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Solicitud de no válida para {request.casificacion}: "
                + ", ".join(invalid_requests or ["sin selección"])
            ),
        )
    values = {
        "Asegurado": request.asegurado,
        "RFC": request.rfc.strip().upper(),
        "Póliza": request.poliza,
        "Casificacion": request.casificacion,
        "Tipo de Trámite": request.tipo_tramite,
        "Solicitud de": ", ".join(selected_requests),
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
        if _rfc_from_row(created) and not created.get("folder_id"):
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


@router.patch("/{source_key}/{source_row}")
def update_pending(
    source_key: str,
    source_row: int,
    request: PendingUpdateRequest,
    _username: str = Depends(current_username),
):
    source = SOURCES.get(source_key)
    if not source:
        raise HTTPException(status_code=404, detail="Fuente de pendientes no encontrada")
    values = {clean_cell(key): clean_cell(value) for key, value in request.values.items()}
    if "RFC" in values:
        values["RFC"] = values["RFC"].upper()
    try:
        with _write_lock:
            service = build_pending_drive_service()
            _, original_row = _get_pending_row(source_key, source_row, service)
            merged_summary = {**original_row["summary"], **values}
            values.update(_derived_day_values(merged_summary))
            file_id = _source_file_id(source)
            updated_workbook = update_pending_record(
                _download_workbook(file_id, service),
                source,
                source_row,
                values,
            )
            _upload_workbook(file_id, updated_workbook, service)
            _clear_source_cache(source.key)
            refreshed = load_pending_source(source, service)
            updated_row = next(
                (row for row in refreshed["rows"] if row["source_row"] == source_row),
                None,
            )
            if not updated_row:
                raise RuntimeError("Los cambios se guardaron, pero no pudieron releerse desde Drive")

            folder_warning = None
            new_rfc = _rfc_from_row(updated_row)
            old_folder_id = original_row.get("folder_id")
            if new_rfc:
                try:
                    target_name = _folder_name_for_row(updated_row)
                    if old_folder_id:
                        folder = service.files().update(
                            fileId=old_folder_id,
                            body={"name": target_name},
                            fields="id,name,webViewLink",
                            supportsAllDrives=True,
                        ).execute()
                        updated_row["folder_name"] = target_name
                        updated_row["folder_id"] = folder.get("id")
                        updated_row["folder_url"] = folder.get("webViewLink")
                    elif not updated_row.get("folder_id"):
                        _create_folder_for_row(service, updated_row)
                    elif updated_row.get("folder_name") != target_name:
                        folder = service.files().update(
                            fileId=updated_row["folder_id"],
                            body={"name": target_name},
                            fields="id,name,webViewLink",
                            supportsAllDrives=True,
                        ).execute()
                        updated_row["folder_name"] = target_name
                        updated_row["folder_url"] = folder.get("webViewLink")
                    _clear_source_cache(source.key)
                except Exception as exc:
                    folder_warning = (
                        "Los datos se guardaron, pero no fue posible sincronizar la carpeta: "
                        f"{exc}"
                    )
        return {"updated": True, "row": updated_row, "folder_warning": folder_warning}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No fue posible actualizar el pendiente en {source.title}: {exc}",
        ) from exc


@router.post("/{source_key}/{source_row}/follow-up")
def create_pending_follow_up(
    source_key: str,
    source_row: int,
    request: PendingFollowUpRequest,
    _username: str = Depends(current_username),
):
    source = SOURCES.get(source_key)
    if not source:
        raise HTTPException(status_code=404, detail="Fuente de pendientes no encontrada")
    try:
        with _write_lock:
            service = build_pending_drive_service()
            file_id = _source_file_id(source)
            updated_workbook, date_header = add_pending_follow_up(
                _download_workbook(file_id, service),
                source,
                source_row,
                request.comment,
            )
            _upload_workbook(file_id, updated_workbook, service)
            _clear_source_cache(source.key)
            refreshed = load_pending_source(source, service)
            updated_row = next(
                (row for row in refreshed["rows"] if row["source_row"] == source_row),
                None,
            )
        if not updated_row:
            raise RuntimeError("El seguimiento se guardó, pero no pudo releerse desde Drive")
        return {"updated": True, "date_header": date_header, "row": updated_row}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No fue posible guardar el seguimiento en {source.title}: {exc}",
        ) from exc


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
