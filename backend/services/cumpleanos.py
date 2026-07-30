from __future__ import annotations

import datetime
import io
import re
import threading
import time
from dataclasses import dataclass
from typing import Iterable

import pandas as pd
from fastapi import APIRouter, HTTPException

from config import METLIFE_PATHS
from parsers.metlife_gmm_renovaciones import parse_metlife_gmm_renewal_workbook
from parsers.metlife_vida_renovaciones import parse_metlife_vida_renewal_workbook
from services.pendientes import DEFAULT_AGENTS_METLIFE_FILE_ID, _download_workbook


router = APIRouter(prefix="/cumpleanos", tags=["cumpleanos"])

PERSON_RFC_PATTERN = re.compile(
    r"^[A-ZÑ&]{4}(?P<year>\d{2})(?P<month>\d{2})(?P<day>\d{2})[A-Z0-9]{3}$",
    re.IGNORECASE,
)
CACHE_SECONDS = 300


@dataclass(frozen=True)
class AgentRecord:
    rfc: str
    name: str
    promotoria: str

    @property
    def label(self) -> str:
        if self.rfc and self.name:
            return f"{self.rfc} - {self.name}"
        return self.rfc or self.name


_cache_lock = threading.Lock()
_cached_result: dict | None = None
_cache_expires_at = 0.0
_cache_signature: tuple | None = None


def clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).replace("\xa0", " ").strip()
    if re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    return " ".join(text.split())


def normalize_code(value: object) -> str:
    return clean_text(value).upper()


def parse_birth_date_from_rfc(
    rfc: object,
    *,
    today: datetime.date | None = None,
) -> datetime.date | None:
    normalized = normalize_code(rfc)
    match = PERSON_RFC_PATTERN.fullmatch(normalized)
    if not match:
        return None

    today = today or datetime.date.today()
    short_year = int(match.group("year"))
    year = (
        2000 + short_year
        if short_year <= today.year % 100
        else 1900 + short_year
    )
    try:
        return datetime.date(
            year,
            int(match.group("month")),
            int(match.group("day")),
        )
    except ValueError:
        return None


def next_birthday_for(
    birth_date: datetime.date,
    *,
    today: datetime.date,
) -> datetime.date:
    def birthday_in(year: int) -> datetime.date:
        try:
            return birth_date.replace(year=year)
        except ValueError:
            return datetime.date(year, 2, 28)

    upcoming = birthday_in(today.year)
    return upcoming if upcoming >= today else birthday_in(today.year + 1)


def parse_agent_lookup(workbook: bytes) -> dict[str, AgentRecord]:
    excel = pd.ExcelFile(io.BytesIO(workbook))
    sheet_name = "Datos" if "Datos" in excel.sheet_names else excel.sheet_names[0]
    table = pd.read_excel(
        io.BytesIO(workbook),
        sheet_name=sheet_name,
        dtype=str,
        keep_default_na=False,
    )
    required = {"CLAVE_DEFINITIVA", "RFC", "Promotoria"}
    missing = required.difference(table.columns)
    if missing:
        raise ValueError(
            "La base de agentes no contiene las columnas requeridas: "
            + ", ".join(sorted(missing))
        )

    agents: dict[str, AgentRecord] = {}
    for _, row in table.iterrows():
        key = normalize_code(row.get("CLAVE_DEFINITIVA"))
        if not key:
            continue
        name_parts = [
            clean_text(row.get("Nombres")),
            clean_text(row.get("Apellido_Paterno")),
            clean_text(row.get("Apellido_Materno")),
        ]
        name = " ".join(part for part in name_parts if part)
        if not name:
            name = clean_text(row.get("Nombre"))
        agents[key] = AgentRecord(
            rfc=normalize_code(row.get("RFC")),
            name=name.title(),
            promotoria=normalize_code(row.get("Promotoria")),
        )
    return agents


def build_birthday_directory(
    records: Iterable[dict],
    agents: dict[str, AgentRecord],
    *,
    today: datetime.date | None = None,
) -> dict:
    today = today or datetime.date.today()
    grouped: dict[str, dict] = {}
    invalid_rfc_rows = 0
    non_person_rfc_rows = 0
    unmatched_agent_rows = 0

    for record in records:
        rfc = normalize_code(record.get("rfc"))
        if len(rfc) != 13:
            non_person_rfc_rows += 1
            continue
        birth_date = parse_birth_date_from_rfc(rfc, today=today)
        if birth_date is None:
            invalid_rfc_rows += 1
            continue

        agent_code = normalize_code(record.get("agent_code"))
        agent = agents.get(agent_code)
        if agent is None:
            unmatched_agent_rows += 1
        client = grouped.setdefault(
            rfc,
            {
                "client_name": clean_text(record.get("client_name")),
                "rfc": rfc,
                "birth_date": birth_date.isoformat(),
                "agent_rfc": agent.rfc if agent else "",
                "agent_name": (
                    agent.name if agent else clean_text(record.get("agent_name"))
                ),
                "agent_label": (
                    agent.label
                    if agent
                    else clean_text(record.get("agent_name"))
                ),
                "promotoria": (
                    agent.promotoria
                    if agent
                    else normalize_code(record.get("promotoria"))
                ),
                "policies": [],
            },
        )

        if not client["client_name"]:
            client["client_name"] = clean_text(record.get("client_name"))
        if agent and not client["agent_rfc"]:
            client["agent_rfc"] = agent.rfc
            client["agent_name"] = agent.name
            client["agent_label"] = agent.label
            client["promotoria"] = agent.promotoria

        policy_number = clean_text(record.get("policy_number"))
        branch = normalize_code(record.get("product_branch"))
        policy_key = (branch, policy_number)
        existing_keys = {
            (policy["branch"], policy["policy_number"])
            for policy in client["policies"]
        }
        if policy_number and policy_key not in existing_keys:
            client["policies"].append(
                {"branch": branch, "policy_number": policy_number}
            )

    clients = []
    for client in grouped.values():
        birth_date = datetime.date.fromisoformat(client["birth_date"])
        next_birthday = next_birthday_for(birth_date, today=today)
        client["next_birthday"] = next_birthday.isoformat()
        client["days_until_birthday"] = (next_birthday - today).days
        client["policies"].sort(
            key=lambda policy: (policy["branch"], policy["policy_number"])
        )
        clients.append(client)

    clients.sort(
        key=lambda client: (
            client["days_until_birthday"],
            client["client_name"].casefold(),
            client["rfc"],
        )
    )
    return {
        "generated_on": today.isoformat(),
        "clients": clients,
        "summary": {
            "total_clients": len(clients),
            "birthdays_this_month": sum(
                1
                for client in clients
                if datetime.date.fromisoformat(client["birth_date"]).month
                == today.month
            ),
            "birthdays_next_30_days": sum(
                1 for client in clients if client["days_until_birthday"] <= 30
            ),
            "invalid_rfc_rows": invalid_rfc_rows,
            "non_person_rfc_rows": non_person_rfc_rows,
            "unmatched_agent_rows": unmatched_agent_rows,
        },
    }


def _source_signature() -> tuple:
    signature = []
    for path in (
        METLIFE_PATHS["RENOVACIONES_GMM"],
        METLIFE_PATHS["RENOVACIONES_VIDA"],
    ):
        stat = path.stat()
        signature.append((str(path), stat.st_mtime_ns, stat.st_size))
    return tuple(signature)


def _load_directory_uncached() -> dict:
    gmm_rows, gmm_issues = parse_metlife_gmm_renewal_workbook(
        METLIFE_PATHS["RENOVACIONES_GMM"]
    )
    vida_rows, vida_issues = parse_metlife_vida_renewal_workbook(
        METLIFE_PATHS["RENOVACIONES_VIDA"]
    )
    critical_issues = [
        issue
        for issue in (*gmm_issues, *vida_issues)
        if issue.get("severity") == "critical"
    ]
    if critical_issues:
        raise ValueError(
            "; ".join(issue["issue_summary"] for issue in critical_issues)
        )

    agent_workbook = _download_workbook(DEFAULT_AGENTS_METLIFE_FILE_ID)
    agents = parse_agent_lookup(agent_workbook)
    records = [
        candidate.normalized_payload
        for candidate in (*gmm_rows, *vida_rows)
    ]
    result = build_birthday_directory(records, agents)
    result["sources"] = {
        "renewal_files": ["Metlife GMM.xlsx", "Metlife Vida.xlsx"],
        "agent_directory": "Agentes MetLife",
    }
    return result


def load_birthday_directory() -> dict:
    global _cached_result, _cache_expires_at, _cache_signature

    signature = _source_signature()
    now = time.monotonic()
    with _cache_lock:
        if (
            _cached_result is not None
            and _cache_signature == signature
            and now < _cache_expires_at
        ):
            return _cached_result
        result = _load_directory_uncached()
        _cached_result = result
        _cache_signature = signature
        _cache_expires_at = now + CACHE_SECONDS
        return result


@router.get("/clientes")
def birthday_clients():
    try:
        return load_birthday_directory()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="No se encontró una de las bases locales de renovaciones.",
        ) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
