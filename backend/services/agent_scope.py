from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re

from fastapi import HTTPException

from config import METLIFE_PATHS
from parsers.metlife_gmm_renovaciones import parse_metlife_gmm_renewal_workbook
from parsers.metlife_vida_renovaciones import parse_metlife_vida_renewal_workbook
from services.auth import AccessProfile
from services.metlife_agent_directory import load_agent_directory, normalize_agent_match_key


def normalize_rfc(value: object) -> str:
    return re.sub(r"[\s-]+", "", str(value or "").strip()).upper()


@dataclass(frozen=True)
class AgentScope:
    rfc: str
    name: str
    promotoria: str
    keys: frozenset[str]
    insurers: frozenset[str]

    def allows_key(self, value: object) -> bool:
        key = normalize_agent_match_key(value)
        return bool(key) and key in self.keys


def resolve_agent_scope(profile: AccessProfile) -> AgentScope | None:
    """Resolve an agent user to one unambiguous canonical Agents row.

    Administrators are intentionally unscoped. Agent users fail closed when the
    RFC is missing, duplicated, or the linked row has no carrier key.
    """
    if not profile.is_agent:
        return None
    rfc = normalize_rfc(profile.rfc)
    matches = [row for row in load_agent_directory() if normalize_rfc(row.get("rfc")) == rfc]
    if not rfc or len(matches) != 1:
        return AgentScope(rfc=rfc, name="", promotoria="", keys=frozenset(), insurers=frozenset())
    row = matches[0]
    status = str(row.get("status") or "").strip().upper()
    if status in {"INACTIVA", "INACTIVO", "BAJA", "CANCELADA", "CANCELADO"}:
        return AgentScope(
            rfc=rfc,
            name=str(row.get("name") or "").strip(),
            promotoria=str(row.get("promotoria") or "").strip(),
            keys=frozenset(),
            insurers=frozenset(),
        )
    keys = frozenset(
        key
        for key in (
            normalize_agent_match_key(row.get("start_key")),
            normalize_agent_match_key(row.get("definitive_key")),
        )
        if key
    )
    return AgentScope(
        rfc=rfc,
        name=str(row.get("name") or "").strip(),
        promotoria=str(row.get("promotoria") or "").strip(),
        keys=keys,
        insurers=frozenset(str(value).strip().upper() for value in profile.aseguradoras if str(value).strip()),
    )


def profile_allows_agent_key(profile: AccessProfile, value: object) -> bool:
    scope = resolve_agent_scope(profile)
    return True if scope is None else scope.allows_key(value)


def require_agent_key_access(profile: AccessProfile, value: object) -> None:
    if not profile_allows_agent_key(profile, value):
        raise HTTPException(status_code=403, detail="El registro no pertenece al agente vinculado a tu usuario")


def profile_allows_insurer(profile: AccessProfile, insurer: object) -> bool:
    if not profile.is_agent:
        return True
    allowed = {value.upper() for value in profile.aseguradoras}
    value = str(insurer or "").strip().upper().replace(" & ", "_")
    if value in {"AARCO_AXA", "AXA_AARCO"}:
        return bool(allowed.intersection({"AARCO", "AXA"}))
    return value in allowed


def _source_signature() -> tuple[tuple[str, int, int], ...]:
    result = []
    for key in ("RENOVACIONES_GMM", "RENOVACIONES_VIDA"):
        path = Path(METLIFE_PATHS[key])
        if not path.exists():
            result.append((str(path), 0, 0))
            continue
        stat = path.stat()
        result.append((str(path), stat.st_mtime_ns, stat.st_size))
    return tuple(result)


@lru_cache(maxsize=8)
def _policy_agent_index(signature: tuple[tuple[str, int, int], ...]) -> dict[str, str]:
    del signature
    indexed: dict[str, str] = {}
    sources = (
        (Path(METLIFE_PATHS["RENOVACIONES_GMM"]), parse_metlife_gmm_renewal_workbook),
        (Path(METLIFE_PATHS["RENOVACIONES_VIDA"]), parse_metlife_vida_renewal_workbook),
    )
    for path, parser in sources:
        if not path.exists():
            continue
        rows, issues = parser(path)
        if any(issue.get("severity") == "critical" for issue in issues):
            continue
        for row in rows:
            payload = row.normalized_payload
            policy = str(payload.get("policy_number") or "").strip().removesuffix(".0")
            key = normalize_agent_match_key(payload.get("agent_code"))
            if policy and key:
                indexed[policy] = key
    return indexed


def policy_agent_index() -> dict[str, str]:
    return _policy_agent_index(_source_signature())


def profile_policy_numbers(profile: AccessProfile) -> frozenset[str] | None:
    scope = resolve_agent_scope(profile)
    if scope is None:
        return None
    if "METLIFE" not in scope.insurers or not scope.keys:
        return frozenset()
    return frozenset(policy for policy, key in policy_agent_index().items() if key in scope.keys)


def profile_allows_policy(profile: AccessProfile, policy_number: object) -> bool:
    allowed = profile_policy_numbers(profile)
    if allowed is None:
        return True
    value = str(policy_number or "").strip().removesuffix(".0")
    return bool(value) and value in allowed
