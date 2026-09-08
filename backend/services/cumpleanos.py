from __future__ import annotations

import datetime
import hashlib
import io
import re
from dataclasses import dataclass
from collections import Counter, defaultdict
from typing import Iterable
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from config import METLIFE_PATHS
from database import Client, Policy, SessionLocal
from parsers.metlife_gmm_renovaciones import parse_metlife_gmm_renewal_workbook
from parsers.metlife_vida_renovaciones import parse_metlife_vida_renewal_workbook
from services.pendientes import DEFAULT_AGENTS_METLIFE_FILE_ID, _download_workbook
from services.data_cache import data_cache
from services.auth import AccessProfile
from services.authorization import profile_allows_promotoria, require_module_access
from services.client_promotorias import normalize_identity
from services.agent_scope import (
    normalize_rfc as normalize_agent_rfc,
    profile_allows_insurer,
    resolve_agent_scope,
)
from services.metlife_agent_directory import normalize_agent_match_key


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
    email: str = ""

    @property
    def label(self) -> str:
        if self.rfc and self.name:
            return f"{self.rfc} - {self.name}"
        return self.rfc or self.name


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


def _renewal_deadline_date(value: object) -> datetime.date | None:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    text = clean_text(value)
    if not text:
        return None
    try:
        return datetime.date.fromisoformat(text[:10])
    except ValueError:
        return None


def filter_future_policy_records(
    records: Iterable[dict],
    *,
    today: datetime.date,
) -> tuple[list[dict], dict[str, int]]:
    future: list[dict] = []
    expired_or_today = 0
    missing_or_invalid = 0
    total = 0
    for record in records:
        total += 1
        renewal_deadline = _renewal_deadline_date(record.get("renewal_deadline"))
        if renewal_deadline is None:
            missing_or_invalid += 1
        elif renewal_deadline > today:
            future.append(record)
        else:
            expired_or_today += 1
    return future, {
        "policy_rows_total": total,
        "policy_rows_future": len(future),
        "policy_rows_expired_or_today": expired_or_today,
        "policy_rows_missing_or_invalid_end_date": missing_or_invalid,
    }


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
        keys = {
            normalize_code(row.get("CLAVE_DEFINITIVA")),
            normalize_code(row.get("CLAVE_ARRANQUE")),
            normalize_agent_match_key(row.get("CLAVE_DEFINITIVA")),
            normalize_agent_match_key(row.get("CLAVE_ARRANQUE")),
        } - {""}
        if not keys:
            continue
        name_parts = [
            clean_text(row.get("Nombres")),
            clean_text(row.get("Apellido_Paterno")),
            clean_text(row.get("Apellido_Materno")),
        ]
        name = " ".join(part for part in name_parts if part)
        if not name:
            name = clean_text(row.get("Nombre"))
        record = AgentRecord(
            rfc=normalize_code(row.get("RFC")),
            name=name.title(),
            promotoria=normalize_code(row.get("Promotoria")),
            email=clean_text(row.get("Correo_Personal")).casefold(),
        )
        for key in keys:
            agents[key] = record
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
                "agent_email": agent.email if agent else "",
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
            client["agent_email"] = agent.email

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


def _normalized_phone(value: object) -> str:
    return "".join(character for character in clean_text(value) if character.isdigit())


def _policy_key(policy: dict) -> tuple[str, str]:
    return (
        normalize_code(policy.get("branch")),
        clean_text(policy.get("policy_number")),
    )


def _policy_is_active(policy: dict, *, today: datetime.date) -> bool:
    if normalize_code(policy.get("status")) != "IN_FORCE":
        return False
    start_date = _renewal_deadline_date(policy.get("effective_start_date"))
    end_date = _renewal_deadline_date(policy.get("effective_end_date"))
    return bool(start_date and end_date and start_date <= today <= end_date)


def _choose_agent(records: Iterable[dict], agents: dict[str, AgentRecord]) -> AgentRecord | None:
    matches = [
        agents[code]
        for code in (normalize_agent_match_key(record.get("agent_code")) for record in records)
        if code in agents
    ]
    if not matches:
        return None
    counts = Counter((item.rfc, item.name, item.promotoria, item.email) for item in matches)
    selected = counts.most_common(1)[0][0]
    return AgentRecord(*selected)


def build_client_master_birthday_directory(
    client_records: Iterable[dict],
    enrichment_records: Iterable[dict],
    agents: dict[str, AgentRecord],
    *,
    today: datetime.date | None = None,
) -> dict:
    """Build birthdays from the Client registry without changing Client identity.

    Two Client rows are presented as one birthday person only when their RFC birth
    date matches and they share the RFC identity segment (initials + birth date),
    normalized email, phone, or full name. This collapses legitimate alternate RFC
    homoclaves for birthday delivery while the underlying Client records and
    expedientes remain independent.
    """
    today = today or datetime.date.today()
    enrichment_by_rfc: dict[str, list[dict]] = defaultdict(list)
    enrichment_by_policy: dict[str, list[dict]] = defaultdict(list)
    for record in enrichment_records:
        rfc = normalize_code(record.get("rfc"))
        policy_number = clean_text(record.get("policy_number"))
        if rfc:
            enrichment_by_rfc[rfc].append(record)
        if policy_number:
            enrichment_by_policy[policy_number].append(record)

    candidates: list[dict] = []
    invalid_rfc_rows = 0
    non_person_rfc_rows = 0
    unmatched_agent_rows = 0
    total_client_records = 0
    for source in client_records:
        total_client_records += 1
        rfc = normalize_code(source.get("rfc"))
        if len(rfc) != 13:
            non_person_rfc_rows += 1
            continue
        birth_date = parse_birth_date_from_rfc(rfc, today=today)
        if birth_date is None:
            invalid_rfc_rows += 1
            continue

        policies = []
        matched_records = list(enrichment_by_rfc.get(rfc, ()))
        for source_policy in source.get("policies") or ():
            policy_matches = list(enrichment_by_policy.get(clean_text(source_policy.get("policy_number")), ()))
            if not policy_matches:
                policy_matches = list(enrichment_by_rfc.get(rfc, ()))
            policy_agent = _choose_agent(policy_matches, agents)
            policy = {
                "branch": normalize_code(source_policy.get("branch")),
                "policy_number": clean_text(source_policy.get("policy_number")),
                "status": clean_text(source_policy.get("status")),
                "effective_start_date": clean_text(source_policy.get("effective_start_date")),
                "effective_end_date": clean_text(source_policy.get("effective_end_date")),
                "agent_rfc": policy_agent.rfc if policy_agent else "",
            }
            policy["is_active"] = _policy_is_active(policy, today=today)
            if policy["policy_number"] and _policy_key(policy) not in {
                _policy_key(item) for item in policies
            }:
                policies.append(policy)
            matched_records.extend(
                enrichment_by_policy.get(policy["policy_number"], ())
            )

        agent = _choose_agent(matched_records, agents)
        if policies and agent is None:
            unmatched_agent_rows += len(policies)
        source_promotorias = {
            normalize_code(value)
            for value in source.get("promotorias") or ()
            if normalize_code(value)
        }
        if agent and agent.promotoria:
            source_promotorias.add(agent.promotoria)
        candidates.append(
            {
                "client_id": clean_text(source.get("id")),
                "client_name": clean_text(source.get("client_name")),
                "rfc": rfc,
                "birth_date": birth_date.isoformat(),
                "email": clean_text(source.get("email")).casefold(),
                "phone": _normalized_phone(source.get("phone")),
                "agent": agent,
                "promotorias": source_promotorias,
                "policies": policies,
            }
        )

    parent = list(range(len(candidates)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    identity_index: dict[tuple[str, str, str], int] = {}
    for index, candidate in enumerate(candidates):
        identities = [
            ("rfc_identity", candidate["rfc"][:10]),
            ("email", candidate["email"]),
            ("phone", candidate["phone"]),
            ("name", normalize_identity(candidate["client_name"])),
        ]
        for kind, value in identities:
            if not value:
                continue
            key = (candidate["birth_date"], kind, value)
            previous = identity_index.setdefault(key, index)
            union(index, previous)

    groups: dict[int, list[dict]] = defaultdict(list)
    for index, candidate in enumerate(candidates):
        groups[find(index)].append(candidate)

    clients = []
    for group in groups.values():
        rfcs = sorted({item["rfc"] for item in group})
        client_ids = sorted({item["client_id"] for item in group if item["client_id"]})
        names = Counter(item["client_name"] for item in group if item["client_name"])
        client_name = names.most_common(1)[0][0] if names else "Cliente sin nombre"
        policies_by_key = {
            _policy_key(policy): policy
            for item in group
            for policy in item["policies"]
            if policy["policy_number"]
        }
        agent = _choose_agent(
            [
                {"agent_code": code}
                for code, known in agents.items()
                if any(item["agent"] == known for item in group)
            ],
            agents,
        )
        promotorias = sorted({
            value
            for item in group
            for value in item["promotorias"]
            if value
        })
        birth_date = datetime.date.fromisoformat(group[0]["birth_date"])
        next_birthday = next_birthday_for(birth_date, today=today)
        policies = sorted(policies_by_key.values(), key=_policy_key)
        active_policies = [policy for policy in policies if policy["is_active"]]
        clients.append(
            {
                "identity_key": hashlib.sha256(
                    f"{birth_date.isoformat()}|{'|'.join(client_ids or rfcs)}".encode("utf-8")
                ).hexdigest()[:16],
                "client_ids": client_ids,
                "client_name": client_name,
                "rfc": ", ".join(rfcs),
                "rfcs": rfcs,
                "birth_date": birth_date.isoformat(),
                "next_birthday": next_birthday.isoformat(),
                "days_until_birthday": (next_birthday - today).days,
                "agent_rfc": agent.rfc if agent else "",
                "agent_name": agent.name if agent else "",
                "agent_label": agent.label if agent else "",
                "agent_email": agent.email if agent else "",
                "promotoria": promotorias[0] if promotorias else "",
                "promotorias": promotorias,
                "policies": policies,
                "active_policies": active_policies,
                "active_policy_count": len(active_policies),
            }
        )

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
                if datetime.date.fromisoformat(client["birth_date"]).month == today.month
            ),
            "birthdays_next_30_days": sum(
                1 for client in clients if client["days_until_birthday"] <= 30
            ),
            "clients_with_active_policies": sum(
                1 for client in clients if client["active_policy_count"] > 0
            ),
            "total_client_records": total_client_records,
            "eligible_client_records": len(candidates),
            "duplicate_client_records_collapsed": len(candidates) - len(clients),
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
    db = SessionLocal()
    try:
        signature.extend(
            (
                ("clients", db.query(func.count(Client.id), func.max(Client.updated_at)).one()),
                ("policies", db.query(func.count(Policy.id), func.max(Policy.updated_at)).one()),
            )
        )
    finally:
        db.close()
    return tuple(signature)


def _load_master_clients() -> list[dict]:
    db = SessionLocal()
    try:
        clients = (
            db.query(Client)
            .options(
                selectinload(Client.promotorias),
                selectinload(Client.policies).selectinload(Policy.product),
            )
            .filter(Client.status != "inactive")
            .all()
        )
        return [
            {
                "id": client.id,
                "client_name": client.full_name,
                "rfc": client.rfc,
                "email": client.email,
                "phone": client.phone,
                "promotorias": [row.promotoria for row in client.promotorias],
                "policies": [
                    {
                        "policy_number": policy.policy_number,
                        "branch": policy.product.branch if policy.product else "",
                        "status": policy.status,
                        "effective_start_date": policy.effective_start_date,
                        "effective_end_date": policy.effective_end_date,
                    }
                    for policy in client.policies
                ],
            }
            for client in clients
        ]
    finally:
        db.close()


def _load_directory_uncached() -> dict:
    today = datetime.datetime.now(ZoneInfo("America/Mexico_City")).date()
    gmm_rows, gmm_issues = parse_metlife_gmm_renewal_workbook(
        METLIFE_PATHS["RENOVACIONES_GMM"],
        today=today,
    )
    vida_rows, vida_issues = parse_metlife_vida_renewal_workbook(
        METLIFE_PATHS["RENOVACIONES_VIDA"],
        today=today,
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
    all_records = [
        candidate.normalized_payload
        for candidate in (*gmm_rows, *vida_rows)
    ]
    result = build_client_master_birthday_directory(
        _load_master_clients(),
        all_records,
        agents,
        today=today,
    )
    result["sources"] = {
        "client_registry": "Registro maestro de Clientes",
        "renewal_files": ["Metlife GMM.xlsx", "Metlife Vida.xlsx"],
        "agent_directory": "Agentes MetLife",
    }
    return result


def load_birthday_directory() -> dict:
    signature = _source_signature()
    signature_key = hashlib.sha256(repr(signature).encode("utf-8")).hexdigest()[:16]
    return data_cache.get_or_load(
        f"cumpleanos:clientes:master-v3:{signature_key}",
        _load_directory_uncached,
        ttl_seconds=CACHE_SECONDS,
    ).value


@router.get("/clientes")
def birthday_clients(
    profile: AccessProfile = Depends(require_module_access("cumpleanos")),
):
    try:
        result = load_birthday_directory()
        clients = [
            client for client in result["clients"]
            if any(
                profile_allows_promotoria(profile, promotoria)
                for promotoria in (
                    client.get("promotorias") or [client.get("promotoria")]
                )
            )
        ]
        if profile.is_agent:
            scope = resolve_agent_scope(profile)
            linked_rfc = scope.rfc if scope and scope.keys else ""
            if not profile_allows_insurer(profile, "METLIFE"):
                linked_rfc = ""
            agent_clients = []
            for client in clients:
                policies = [
                    policy for policy in client.get("policies", [])
                    if normalize_agent_rfc(policy.get("agent_rfc")) == linked_rfc
                ]
                if not policies:
                    continue
                active_policies = [policy for policy in policies if policy.get("is_active")]
                agent_clients.append({
                    **client,
                    "agent_rfc": linked_rfc,
                    "policies": policies,
                    "active_policies": active_policies,
                    "active_policy_count": len(active_policies),
                })
            clients = agent_clients
        scoped = {**result, "clients": clients, "summary": {**result["summary"]}}
        scoped["summary"]["total_clients"] = len(clients)
        scoped["summary"]["birthdays_this_month"] = sum(
            1 for client in clients
            if datetime.date.fromisoformat(client["birth_date"]).month
            == datetime.date.fromisoformat(result["generated_on"]).month
        )
        scoped["summary"]["birthdays_next_30_days"] = sum(
            1 for client in clients if client["days_until_birthday"] <= 30
        )
        scoped["summary"]["clients_with_active_policies"] = sum(
            1 for client in clients if int(client.get("active_policy_count") or 0) > 0
        )
        return scoped
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="No se encontró una de las bases locales de renovaciones.",
        ) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
