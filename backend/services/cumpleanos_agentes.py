from __future__ import annotations

import datetime
import io
import threading
import time

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from services.cumpleanos import (
    clean_text,
    next_birthday_for,
    normalize_code,
    parse_birth_date_from_rfc,
)
from services.pendientes import DEFAULT_AGENTS_METLIFE_FILE_ID, _download_workbook
from services.data_cache import data_cache
from services.auth import AccessProfile
from services.authorization import normalize_promotoria, require_module_access


router = APIRouter(prefix="/cumpleanos-agentes", tags=["cumpleanos-agentes"])
CACHE_SECONDS = 300

_cache_lock = threading.Lock()
_cached_result: dict | None = None
_cache_expires_at = 0.0


def build_agent_birthday_directory(
    workbook: bytes,
    *,
    today: datetime.date | None = None,
) -> dict:
    today = today or datetime.date.today()
    excel = pd.ExcelFile(io.BytesIO(workbook))
    sheet_name = "Datos" if "Datos" in excel.sheet_names else excel.sheet_names[0]
    table = pd.read_excel(
        io.BytesIO(workbook),
        sheet_name=sheet_name,
        dtype=str,
        keep_default_na=False,
    )
    required = {"RFC", "Promotoria"}
    missing = required.difference(table.columns)
    if missing:
        raise ValueError(
            "La base de agentes no contiene las columnas requeridas: "
            + ", ".join(sorted(missing))
        )

    grouped: dict[str, dict] = {}
    missing_rfc_rows = 0
    invalid_rfc_rows = 0
    duplicate_rows = 0

    for _, row in table.iterrows():
        rfc = normalize_code(row.get("RFC"))
        if not rfc:
            missing_rfc_rows += 1
            continue
        birth_date = parse_birth_date_from_rfc(rfc, today=today)
        if birth_date is None:
            invalid_rfc_rows += 1
            continue

        name_parts = [
            clean_text(row.get("Nombres")),
            clean_text(row.get("Apellido_Paterno")),
            clean_text(row.get("Apellido_Materno")),
        ]
        name = " ".join(part for part in name_parts if part)
        if not name:
            name = clean_text(row.get("Nombre"))

        agent = grouped.get(rfc)
        if agent is None:
            agent = {
                "agent_name": name.title(),
                "rfc": rfc,
                "birth_date": birth_date.isoformat(),
                "definitive_keys": [],
                "promotorias": [],
                "email": clean_text(row.get("Correo_Personal")),
                "status": clean_text(row.get("Estado") or row.get("Estatus_Met")),
            }
            grouped[rfc] = agent
        else:
            duplicate_rows += 1

        key = clean_text(row.get("CLAVE_DEFINITIVA"))
        promotoria = normalize_code(row.get("Promotoria"))
        if key and key not in agent["definitive_keys"]:
            agent["definitive_keys"].append(key)
        if promotoria and promotoria not in agent["promotorias"]:
            agent["promotorias"].append(promotoria)
        if not agent["email"]:
            agent["email"] = clean_text(row.get("Correo_Personal"))
        if not agent["status"]:
            agent["status"] = clean_text(row.get("Estado") or row.get("Estatus_Met"))

    agents = []
    for agent in grouped.values():
        birth_date = datetime.date.fromisoformat(agent["birth_date"])
        next_birthday = next_birthday_for(birth_date, today=today)
        agent["next_birthday"] = next_birthday.isoformat()
        agent["days_until_birthday"] = (next_birthday - today).days
        agent["definitive_keys"].sort()
        agent["promotorias"].sort()
        agents.append(agent)

    agents.sort(
        key=lambda agent: (
            agent["days_until_birthday"],
            agent["agent_name"].casefold(),
            agent["rfc"],
        )
    )
    return {
        "generated_on": today.isoformat(),
        "agents": agents,
        "summary": {
            "total_agents": len(agents),
            "birthdays_this_month": sum(
                1
                for agent in agents
                if datetime.date.fromisoformat(agent["birth_date"]).month
                == today.month
            ),
            "birthdays_next_30_days": sum(
                1 for agent in agents if agent["days_until_birthday"] <= 30
            ),
            "missing_rfc_rows": missing_rfc_rows,
            "invalid_rfc_rows": invalid_rfc_rows,
            "duplicate_rows": duplicate_rows,
        },
        "sources": {"agent_directory": "Agentes MetLife"},
    }


def load_agent_birthday_directory() -> dict:
    def load_fresh():
        workbook = _download_workbook(DEFAULT_AGENTS_METLIFE_FILE_ID)
        return build_agent_birthday_directory(workbook)

    return data_cache.get_or_load(
        "cumpleanos:agentes",
        load_fresh,
        ttl_seconds=CACHE_SECONDS,
    ).value


@router.get("")
def birthday_agents(
    profile: AccessProfile = Depends(require_module_access("cumpleanos_agentes")),
):
    try:
        result = load_agent_birthday_directory()
        allowed = set(profile.promotorias)
        agents = result["agents"] if profile.is_central_admin else [
            agent for agent in result["agents"]
            if any(normalize_promotoria(value) in allowed for value in agent.get("promotorias", []))
        ]
        scoped = {**result, "agents": agents, "summary": {**result["summary"]}}
        scoped["summary"]["total_agents"] = len(agents)
        scoped["summary"]["birthdays_this_month"] = sum(
            1 for agent in agents
            if datetime.date.fromisoformat(agent["birth_date"]).month
            == datetime.date.fromisoformat(result["generated_on"]).month
        )
        scoped["summary"]["birthdays_next_30_days"] = sum(
            1 for agent in agents if agent["days_until_birthday"] <= 30
        )
        return scoped
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
