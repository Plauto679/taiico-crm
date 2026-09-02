from __future__ import annotations

import io
import os
import re
import threading
import time

import pandas as pd

from drive.client import download_drive_file_bytes


AGENTS_FILE_ID_ENV = "GOOGLE_DRIVE_AGENTS_METLIFE_FILE_ID"
DEFAULT_AGENTS_FILE_ID = "1IoeLDCQe4T3DofStiBSaI09xjX2-RSby"

_cache_lock = threading.RLock()
_cache: tuple[float, list[dict[str, str]]] | None = None
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AgentContactResolutionError(ValueError):
    pass


def clear_agent_directory_cache() -> None:
    global _cache
    with _cache_lock:
        _cache = None


def normalize_agent_key(value: object) -> str:
    text = str(value or "").strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    return "".join(text.upper().split())


def parse_agent_directory(workbook_bytes: bytes) -> list[dict[str, str]]:
    excel = pd.ExcelFile(io.BytesIO(workbook_bytes))
    sheet_name = "Datos" if "Datos" in excel.sheet_names else excel.sheet_names[0]
    table = pd.read_excel(
        io.BytesIO(workbook_bytes),
        sheet_name=sheet_name,
        dtype=str,
        keep_default_na=False,
    )
    table.columns = [str(column).strip() for column in table.columns]
    required = {
        "Promotoria",
        "CLAVE_DEFINITIVA",
        "CLAVE_ARRANQUE",
    }
    missing = sorted(required.difference(table.columns))
    if missing:
        raise ValueError("La base de agentes no contiene: " + ", ".join(missing))

    agents: list[dict[str, str]] = []
    for row_number, (_, row) in enumerate(table.iterrows(), start=2):
        definitive_key = normalize_agent_key(row.get("CLAVE_DEFINITIVA"))
        start_key = normalize_agent_key(row.get("CLAVE_ARRANQUE"))
        key = definitive_key or start_key
        promotoria = str(row.get("Promotoria") or "").strip()
        if not key:
            continue
        name = str(row.get("Nombre") or "").strip()
        if not name:
            name = " ".join(
                part
                for part in (
                    str(row.get("Nombres") or row.get("Nombre_s") or "").strip(),
                    str(row.get("Apellido_Paterno") or "").strip(),
                    str(row.get("Apellido_Materno") or "").strip(),
                )
                if part
            )
        agents.append(
            {
                "key": key,
                "definitive_key": definitive_key,
                "start_key": start_key,
                "promotoria": promotoria,
                "name": name,
                "email": str(row.get("Correo_Personal") or "").strip(),
                "row_number": str(row_number),
                "key_source": "CLAVE_DEFINITIVA" if definitive_key else "CLAVE_ARRANQUE",
            }
        )
    return agents


def load_agent_directory() -> list[dict[str, str]]:
    global _cache
    now = time.monotonic()
    cache_seconds = max(0, int(os.getenv("METLIFE_AGENTS_CACHE_SECONDS", "300")))
    with _cache_lock:
        if _cache and now < _cache[0]:
            return _cache[1]
        file_id = os.getenv(AGENTS_FILE_ID_ENV, "").strip() or DEFAULT_AGENTS_FILE_ID
        agents = parse_agent_directory(download_drive_file_bytes(file_id))
        _cache = (now + cache_seconds, agents)
        return agents


def promotoria_by_agent_key() -> dict[str, str]:
    indexed: dict[str, str] = {}
    ambiguous: set[str] = set()
    for agent in load_agent_directory():
        key = normalize_agent_key(agent.get("key"))
        promotoria = str(agent.get("promotoria") or "").strip()
        previous = indexed.get(key)
        if previous and previous.casefold() != promotoria.casefold():
            ambiguous.add(key)
        elif key and promotoria:
            indexed[key] = promotoria
    for key in ambiguous:
        indexed.pop(key, None)
    return indexed


def resolve_agent_contact(agent_key: object) -> dict[str, str]:
    normalized_key = normalize_agent_key(agent_key)
    if not normalized_key:
        raise AgentContactResolutionError("La póliza no contiene una clave de agente")

    matches = [
        agent
        for agent in load_agent_directory()
        if normalized_key
        in {
            normalize_agent_key(agent.get("definitive_key")),
            normalize_agent_key(agent.get("start_key")),
        }
    ]
    if not matches:
        raise AgentContactResolutionError(
            f"Clave de agente {normalized_key} no encontrada en la base de Agentes"
        )
    if len(matches) > 1:
        rows = ", ".join(agent.get("row_number", "?") for agent in matches)
        raise AgentContactResolutionError(
            f"Clave de agente {normalized_key} duplicada o ambigua (filas {rows})"
        )

    contact = matches[0]
    email = str(contact.get("email") or "").strip()
    if not EMAIL_PATTERN.fullmatch(email):
        raise AgentContactResolutionError(
            f"El agente de la clave {normalized_key} no tiene un Correo_Personal válido"
        )
    return contact
