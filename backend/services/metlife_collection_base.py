"""Collection portfolio from the canonical workbooks updated by Carga de Bases."""
from datetime import date
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException

from config import METLIFE_PATHS
from services.metlife_portal_collection import portal_collection_index, display_checked_timestamp
from parsers.metlife_gmm_renovaciones import parse_metlife_gmm_renewal_workbook
from parsers.metlife_vida_renovaciones import parse_metlife_vida_renewal_workbook
from services.agent_scope import profile_allows_agent_key, profile_allows_insurer
from services.authorization import profile_allows_promotoria
from services.metlife_agent_directory import normalize_agent_match_key, promotoria_by_agent_key


@lru_cache(maxsize=4)
def _read_base(path: str, branch: str, modified_ns: int, size: int):
    # File version participates in the key so an applied upload is visible immediately.
    parser = parse_metlife_vida_renewal_workbook if branch == "VIDA" else parse_metlife_gmm_renewal_workbook
    rows, _issues = parser(Path(path))
    return [row.normalized_payload for row in rows]


def collection_base(branch, start_date, end_date, profile):
    try:
        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None
    except ValueError as exc:
        raise HTTPException(422, "Las fechas deben tener formato YYYY-MM-DD") from exc
    if start and end and start > end:
        raise HTTPException(422, "La fecha inicial no puede ser posterior a la final")
    if profile.is_agent and not profile_allows_insurer(profile, "metlife"):
        return []
    path = Path(METLIFE_PATHS[f"RENOVACIONES_{branch}"])
    try:
        stat = path.stat()
        payloads = _read_base(str(path), branch, stat.st_mtime_ns, stat.st_size)
    except FileNotFoundError as exc:
        raise HTTPException(404, f"Carga la base de Metlife {branch} en Carga de Bases") from exc
    promoterias = promotoria_by_agent_key()
    portal_checks = portal_collection_index() if branch == "GMM" else {}
    results = []
    for payload in payloads:
        if not payload.get("policy_number"):
            continue
        agent = payload.get("agent_code") or ""
        promotoria = promoterias.get(normalize_agent_match_key(agent)) or payload.get("promotoria") or ""
        if profile.is_agent:
            if not profile_allows_agent_key(profile, agent):
                continue
        elif not profile_allows_promotoria(profile, promotoria):
            continue
        paid_until = payload.get("paid_until_date")
        if (start or end) and not paid_until:
            continue
        if start and paid_until < start or end and paid_until > end:
            continue
        portal = portal_checks.get((payload["policy_number"], iso_date(payload.get("renewal_deadline"))), {})
        results.append({
            "# de Póliza": payload["policy_number"],
            "Contratante": payload.get("client_name"),
            "RFC": payload.get("rfc"),
            "Producto": payload.get("product_name") or f"Metlife {branch}",
            "Inicio Vigencia": iso_date(payload.get("effective_start_date")),
            "Fin Vigencia": iso_date(payload.get("renewal_deadline")),
            "Forma de Pago": payload.get("payment_frequency_source"),
            "Conducto de Cobro": payload.get("collection_channel"),
            "Estado": payload.get("policy_status_source"),
            "Moneda": payload.get("currency"),
            "Prima Anual": money(payload.get("premium_amount")),
            "Prima Modal": money(payload.get("modal_premium_amount")),
            "Pagado Hasta": iso_date(paid_until),
            **({
                "Pagado Hasta (base)": iso_date(paid_until),
                "Pagado Hasta (portal)": portal.get("paid_until"),
                "Última consulta al portal": display_checked_timestamp(portal.get("checked_at")),
            } if branch == "GMM" else {}),
            "Clave Agente": agent,
            "Agente": payload.get("agent_name"),
            "Promotoría": promotoria,
        })
    return results


def iso_date(value):
    return value.isoformat() if value else None


def money(value):
    return float(value) if value is not None else None
