from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
import unicodedata

from sqlalchemy import false
from sqlalchemy.orm import joinedload, selectinload

from config import METLIFE_PATHS
from database import Client, ClientPromotoria, Policy
from parsers.metlife_gmm_renovaciones import parse_metlife_gmm_renewal_workbook
from parsers.metlife_vida_renovaciones import parse_metlife_vida_renewal_workbook
from services.auth import AccessProfile, PROMOTORIAS
from services.authorization import normalize_promotoria
from services.metlife_agent_directory import normalize_agent_key


def normalize_identity(value: object) -> str:
    text = " ".join(str(value or "").strip().casefold().split())
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )


def normalize_rfc(value: object) -> str:
    return re.sub(r"[\s-]+", "", str(value or "").strip()).upper()


def valid_promotoria(value: object) -> bool:
    return normalize_promotoria(value) in set(PROMOTORIAS)


def scope_client_query(query, profile: AccessProfile):
    query = query.options(selectinload(Client.promotorias))
    if profile.is_central_admin:
        return query
    allowed = tuple(normalize_promotoria(value) for value in profile.promotorias if normalize_promotoria(value))
    if not allowed:
        return query.filter(false())
    return (
        query.join(ClientPromotoria, ClientPromotoria.client_id == Client.id)
        .filter(ClientPromotoria.promotoria.in_(allowed))
        .distinct()
    )


def client_is_visible(client: Client, profile: AccessProfile) -> bool:
    if profile.is_central_admin:
        return True
    allowed = {normalize_promotoria(value) for value in profile.promotorias}
    return bool(allowed.intersection({normalize_promotoria(row.promotoria) for row in client.promotorias}))


def assign_profile_promotorias(client: Client, profile: AccessProfile) -> None:
    if profile.is_central_admin:
        return
    existing = {normalize_promotoria(row.promotoria) for row in client.promotorias}
    for value in profile.promotorias:
        promotoria = normalize_promotoria(value)
        if promotoria and promotoria not in existing:
            client.promotorias.append(
                ClientPromotoria(
                    promotoria=promotoria,
                    sources_json=[{"source": "crm_user_scope", "reference": profile.username}],
                )
            )
            existing.add(promotoria)


def _unique_name_promotorias(agents: list[dict]) -> dict[str, str]:
    candidates: dict[str, set[str]] = defaultdict(set)
    for agent in agents:
        name = normalize_identity(agent.get("nombre"))
        promotoria = normalize_promotoria(agent.get("promotoria"))
        if name and promotoria:
            candidates[name].add(promotoria)
    return {name: next(iter(values)) for name, values in candidates.items() if len(values) == 1}


def _agent_key_promotorias(agents: list[dict]) -> dict[str, str]:
    candidates: dict[str, set[str]] = defaultdict(set)
    for agent in agents:
        promotoria = normalize_promotoria(agent.get("promotoria"))
        for field in ("clave_definitiva", "clave_arranque"):
            key = normalize_agent_key(agent.get(field))
            if key and promotoria:
                candidates[key].add(promotoria)
    return {key: next(iter(values)) for key, values in candidates.items() if len(values) == 1}


def collect_client_promotoria_evidence(db, *, agents: list[dict] | None = None) -> list[dict]:
    if agents is None:
        # Imported lazily because the Agents workbook helper shares the
        # Pendientes workbook downloader, which itself imports Clientes.
        from services.agentes import load_agents_directory

        agents = load_agents_directory()["agents"]
    by_name = _unique_name_promotorias(agents)
    by_key = _agent_key_promotorias(agents)
    known_promotorias = {
        normalize_promotoria(agent.get("promotoria"))
        for agent in agents
        if normalize_promotoria(agent.get("promotoria"))
    }
    clients = db.query(Client).options(joinedload(Client.policies)).all()
    by_rfc: dict[str, list[Client]] = defaultdict(list)
    by_policy: dict[str, list[Client]] = defaultdict(list)
    for client in clients:
        rfc = normalize_rfc(client.rfc)
        if rfc:
            by_rfc[rfc].append(client)
        for policy in client.policies:
            number = str(policy.policy_number or "").strip()
            if number:
                by_policy[number].append(client)

    evidence: dict[tuple[str, str], list[dict]] = defaultdict(list)

    def add(client: Client, promotoria: str, source: str, reference: str) -> None:
        normalized = normalize_promotoria(promotoria)
        item = {"source": source, "reference": reference}
        if normalized and item not in evidence[(client.id, normalized)]:
            evidence[(client.id, normalized)].append(item)

    for client in clients:
        prospectador = normalize_identity((client.metadata_json or {}).get("prospectador"))
        if prospectador in by_name:
            add(client, by_name[prospectador], "client_metadata.prospectador", prospectador)
        for policy in client.policies:
            metadata = policy.metadata_json or {}
            for field in ("prospector", "prospectador", "prospector_name"):
                prospectador = normalize_identity(metadata.get(field))
                if prospectador in by_name:
                    add(client, by_name[prospectador], f"policy_metadata.{field}", policy.policy_number)

    renewal_sources = (
        (Path(METLIFE_PATHS["RENOVACIONES_GMM"]), parse_metlife_gmm_renewal_workbook, "metlife_gmm_renewals"),
        (Path(METLIFE_PATHS["RENOVACIONES_VIDA"]), parse_metlife_vida_renewal_workbook, "metlife_vida_renewals"),
    )
    for path, parser, source in renewal_sources:
        if not path.exists():
            continue
        rows, issues = parser(path)
        if any(issue.get("severity") == "critical" for issue in issues):
            continue
        for row in rows:
            payload = row.normalized_payload
            key = normalize_agent_key(payload.get("agent_code"))
            source_promotoria = normalize_promotoria(payload.get("promotoria"))
            promotoria = (
                source_promotoria if source_promotoria in known_promotorias else by_key.get(key, "")
            )
            if not promotoria:
                continue
            policy_number = str(payload.get("policy_number") or "").strip()
            rfc = normalize_rfc(payload.get("rfc"))
            matches = list(by_rfc.get(rfc, ())) if rfc else []
            if not matches:
                matches = list(by_policy.get(policy_number, ()))
            for client in matches:
                add(client, promotoria, source, rfc or policy_number)

    return [
        {
            "client_id": client_id,
            "promotoria": promotoria,
            "sources": sources,
        }
        for (client_id, promotoria), sources in sorted(evidence.items())
    ]


def sync_client_promotorias(db, *, agents: list[dict] | None = None) -> dict:
    evidence = collect_client_promotoria_evidence(db, agents=agents)
    existing = {
        (row.client_id, normalize_promotoria(row.promotoria)): row
        for row in db.query(ClientPromotoria).all()
    }
    created = 0
    updated = 0
    for item in evidence:
        key = (item["client_id"], item["promotoria"])
        row = existing.get(key)
        if row is None:
            db.add(
                ClientPromotoria(
                    client_id=item["client_id"],
                    promotoria=item["promotoria"],
                    sources_json=item["sources"],
                )
            )
            created += 1
        elif row.sources_json != item["sources"]:
            preserved = [source for source in (row.sources_json or []) if source.get("source") == "crm_user_scope"]
            row.sources_json = preserved + [source for source in item["sources"] if source not in preserved]
            updated += 1
    db.flush()
    return {
        "evidence_count": len(evidence),
        "created": created,
        "updated": updated,
        "linked_clients": (
            db.query(ClientPromotoria.client_id)
            .filter(ClientPromotoria.promotoria.in_(PROMOTORIAS))
            .distinct()
            .count()
        ),
    }
