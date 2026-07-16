from __future__ import annotations

import io
import os
import threading
import time
from dataclasses import dataclass

import pandas as pd
from fastapi import APIRouter, HTTPException

from drive.client import build_drive_service


router = APIRouter(prefix="/pendientes", tags=["pendientes"])

DEFAULT_EMISION_SERVICIOS_FILE_ID = "1JMr-EwtniwHvPm6zefhGJroTw2vxivmC"
DEFAULT_SINIESTROS_FILE_ID = "1UvXo2LboTKWl5323mEuP6bmmyIhLYveL"
DEFAULT_CACHE_SECONDS = 300


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
        core_column_count=14,
    ),
    "siniestros": PendingSource(
        key="siniestros",
        title="Siniestros",
        file_id_env="GOOGLE_DRIVE_PENDING_SINIESTROS_FILE_ID",
        default_file_id=DEFAULT_SINIESTROS_FILE_ID,
        sheet_name="Base",
        core_column_count=11,
    ),
}

_cache_lock = threading.Lock()
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


def _download_workbook(file_id: str) -> bytes:
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


def load_pending_source(source: PendingSource) -> dict:
    cache_seconds = max(
        0,
        int(os.getenv("PENDING_SOURCES_CACHE_SECONDS", str(DEFAULT_CACHE_SECONDS))),
    )
    now = time.monotonic()
    with _cache_lock:
        cached = _cache.get(source.key)
        if cached and now < cached[0]:
            return cached[1]

        file_id = os.getenv(source.file_id_env, source.default_file_id).strip()
        if not file_id:
            raise RuntimeError(f"{source.file_id_env} is not configured")
        result = parse_pending_workbook(_download_workbook(file_id), source)
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
