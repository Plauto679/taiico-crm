from __future__ import annotations

import csv
import io
import os
import threading
import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from googleapiclient.http import MediaIoBaseUpload
from pydantic import BaseModel, Field, model_validator

from drive.client import download_drive_file_bytes
from services.auth import _build_writable_drive_service
from services.data_cache import data_cache


router = APIRouter(prefix="/rrhh", tags=["rrhh"])
PEOPLE_FILE_ID = os.getenv("GOOGLE_DRIVE_RRHH_FILE_ID", "1kAlNJ93qPVeIQmokGTgmyk1VqRQ4fqu6")
RRHH_FOLDER_ID = os.getenv("GOOGLE_DRIVE_RRHH_FOLDER_ID", "1uyT3X3cz8aziPgLN0ogv8LgbdYGuudZq")
VACATIONS_FILE_NAME = "RRHH_Vacaciones.csv"
PEOPLE_HEADERS = (
    "ID", "Nombre completo", "Inicio de colaboración", "Días colaborando", "Expediente",
    "Puesto", "Área", "Tipo de relación", "Estatus", "Días de vacaciones anuales", "Notas",
)
VACATION_HEADERS = (
    "ID", "Colaborador ID", "Nombre completo", "Fecha inicio", "Fecha fin", "Días",
    "Estatus", "Comentarios",
)
_file_lock = threading.RLock()


class CollaboratorInput(BaseModel):
    nombre_completo: str = Field(min_length=2, max_length=255)
    inicio_colaboracion: date
    expediente: str = Field(default="", max_length=1000)
    puesto: str = Field(default="", max_length=255)
    area: str = Field(default="", max_length=255)
    tipo_relacion: str = Field(default="Empleado", max_length=100)
    estatus: str = Field(default="Activo", max_length=100)
    dias_vacaciones_anuales: int = Field(default=12, ge=0, le=365)
    notas: str = Field(default="", max_length=3000)


class VacationInput(BaseModel):
    collaborator_id: str = Field(min_length=1, max_length=100)
    fecha_inicio: date
    fecha_fin: date
    estatus: str = Field(default="Solicitada", max_length=100)
    comentarios: str = Field(default="", max_length=3000)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("La fecha final no puede ser anterior a la fecha inicial")
        return self


def _read_csv(file_id: str, headers: tuple[str, ...]) -> list[dict[str, str]]:
    content = download_drive_file_bytes(file_id).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    rows = []
    for raw in reader:
        row = {header: str(raw.get(header) or "").strip() for header in headers}
        if any(row.values()):
            rows.append(row)
    return rows


def _csv_bytes(rows: list[dict[str, Any]], headers: tuple[str, ...]) -> bytes:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def _upload(file_id: str, rows: list[dict[str, Any]], headers: tuple[str, ...]) -> None:
    media = MediaIoBaseUpload(io.BytesIO(_csv_bytes(rows, headers)), mimetype="text/csv", resumable=False)
    _build_writable_drive_service().files().update(
        fileId=file_id, media_body=media, supportsAllDrives=True
    ).execute()
    data_cache.invalidate("rrhh:data")


def _vacations_file_id(*, create: bool = False) -> str | None:
    service = _build_writable_drive_service()
    escaped = VACATIONS_FILE_NAME.replace("'", "\\'")
    files = service.files().list(
        q=f"'{RRHH_FOLDER_ID}' in parents and name = '{escaped}' and trashed = false",
        fields="files(id)", supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute().get("files", [])
    if files:
        return str(files[0]["id"])
    if not create:
        return None
    media = MediaIoBaseUpload(io.BytesIO(_csv_bytes([], VACATION_HEADERS)), mimetype="text/csv", resumable=False)
    created = service.files().create(
        body={"name": VACATIONS_FILE_NAME, "parents": [RRHH_FOLDER_ID]},
        media_body=media, fields="id", supportsAllDrives=True,
    ).execute()
    return str(created["id"])


def _days_between(start: str, end: date | None = None) -> int:
    try:
        parsed = date.fromisoformat(start)
    except ValueError:
        try:
            parsed = datetime.strptime(start, "%d/%m/%Y").date()
        except ValueError:
            return 0
    return max(0, ((end or date.today()) - parsed).days)


def _serialize_person(row: dict[str, str], index: int, vacation_rows: list[dict[str, str]]) -> dict[str, Any]:
    person_id = row.get("ID") or f"ROW-{index}"
    used = sum(int(item.get("Días") or 0) for item in vacation_rows if item.get("Colaborador ID") == person_id and item.get("Estatus", "").casefold() == "aprobada" and item.get("Fecha inicio", "").startswith(str(date.today().year)))
    annual = int(row.get("Días de vacaciones anuales") or 12)
    return {
        "id": person_id,
        "nombre_completo": row.get("Nombre completo", ""),
        "inicio_colaboracion": row.get("Inicio de colaboración", ""),
        "dias_colaborando": _days_between(row.get("Inicio de colaboración", "")),
        "expediente": row.get("Expediente", ""),
        "puesto": row.get("Puesto", ""),
        "area": row.get("Área", ""),
        "tipo_relacion": row.get("Tipo de relación", "") or "Empleado",
        "estatus": row.get("Estatus", "") or "Activo",
        "dias_vacaciones_anuales": annual,
        "dias_vacaciones_usados": used,
        "dias_vacaciones_disponibles": max(0, annual - used),
        "notas": row.get("Notas", ""),
    }


def _serialize_vacation(row: dict[str, str]) -> dict[str, Any]:
    return {
        "id": row.get("ID", ""), "collaborator_id": row.get("Colaborador ID", ""),
        "nombre_completo": row.get("Nombre completo", ""), "fecha_inicio": row.get("Fecha inicio", ""),
        "fecha_fin": row.get("Fecha fin", ""), "dias": int(row.get("Días") or 0),
        "estatus": row.get("Estatus", ""), "comentarios": row.get("Comentarios", ""),
    }


def _people_and_vacations():
    people = _read_csv(PEOPLE_FILE_ID, PEOPLE_HEADERS)
    vacation_id = _vacations_file_id()
    vacations = _read_csv(vacation_id, VACATION_HEADERS) if vacation_id else []
    return people, vacations


def _load_hr_data_fresh():
    people, vacations = _people_and_vacations()
    serialized_people = [_serialize_person(row, index, vacations) for index, row in enumerate(people, 2)]
    return {
        "collaborators": serialized_people,
        "vacations": [_serialize_vacation(row) for row in vacations],
        "source_url": f"https://drive.google.com/open?id={PEOPLE_FILE_ID}",
    }


@router.get("")
def get_hr_data():
    try:
        ttl_seconds = max(0, int(os.getenv("RRHH_CACHE_SECONDS", "300")))
        return data_cache.get_or_load("rrhh:data", _load_hr_data_fresh, ttl_seconds=ttl_seconds).value
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"No se pudo leer la información de RRHH: {exc}") from exc


def _person_row(payload: CollaboratorInput, person_id: str) -> dict[str, Any]:
    return {
        "ID": person_id, "Nombre completo": " ".join(payload.nombre_completo.split()),
        "Inicio de colaboración": payload.inicio_colaboracion.isoformat(),
        "Días colaborando": _days_between(payload.inicio_colaboracion.isoformat()), "Expediente": payload.expediente.strip(),
        "Puesto": payload.puesto.strip(), "Área": payload.area.strip(), "Tipo de relación": payload.tipo_relacion,
        "Estatus": payload.estatus, "Días de vacaciones anuales": payload.dias_vacaciones_anuales,
        "Notas": payload.notas.strip(),
    }


@router.post("/collaborators", status_code=201)
def create_collaborator(payload: CollaboratorInput):
    with _file_lock:
        people, vacations = _people_and_vacations()
        person_id = f"RH-{uuid.uuid4().hex[:10].upper()}"
        row = _person_row(payload, person_id)
        people.append(row)
        _upload(PEOPLE_FILE_ID, people, PEOPLE_HEADERS)
        return {"collaborator": _serialize_person(row, len(people) + 1, vacations)}


@router.put("/collaborators/{person_id}")
def update_collaborator(person_id: str, payload: CollaboratorInput):
    with _file_lock:
        people, vacations = _people_and_vacations()
        index = next((i for i, row in enumerate(people) if (row.get("ID") or f"ROW-{i + 2}") == person_id), None)
        if index is None:
            raise HTTPException(status_code=404, detail="Colaborador no encontrado")
        stored_id = people[index].get("ID") or f"RH-{uuid.uuid4().hex[:10].upper()}"
        people[index] = _person_row(payload, stored_id)
        _upload(PEOPLE_FILE_ID, people, PEOPLE_HEADERS)
        return {"collaborator": _serialize_person(people[index], index + 2, vacations)}


@router.post("/vacations", status_code=201)
def create_vacation(payload: VacationInput):
    with _file_lock:
        people, _ = _people_and_vacations()
        person = next((row for i, row in enumerate(people) if (row.get("ID") or f"ROW-{i + 2}") == payload.collaborator_id), None)
        if not person:
            raise HTTPException(status_code=404, detail="Colaborador no encontrado")
        file_id = _vacations_file_id(create=True)
        assert file_id
        vacations = _read_csv(file_id, VACATION_HEADERS)
        row = {
            "ID": f"VAC-{uuid.uuid4().hex[:10].upper()}", "Colaborador ID": payload.collaborator_id,
            "Nombre completo": person.get("Nombre completo", ""), "Fecha inicio": payload.fecha_inicio.isoformat(),
            "Fecha fin": payload.fecha_fin.isoformat(), "Días": (payload.fecha_fin - payload.fecha_inicio).days + 1,
            "Estatus": payload.estatus, "Comentarios": payload.comentarios.strip(),
        }
        vacations.append(row)
        _upload(file_id, vacations, VACATION_HEADERS)
        return {"vacation": _serialize_vacation(row)}
