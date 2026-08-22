from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any, Iterable


LEGAL_NAME_WORDS = {
    "A", "C", "CV", "DE", "DEL", "E", "LA", "LAS", "LOS", "S", "SA", "SC",
    "SOCIEDAD", "ANONIMA", "V", "VARIABLE",
}


def _plain(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").upper())
    return "".join(character for character in text if not unicodedata.combining(character))


def normalized_name_signature(value: object) -> str:
    tokens = re.findall(r"[A-Z0-9]+", _plain(value))
    meaningful = [token for token in tokens if token not in LEGAL_NAME_WORDS]
    return " ".join(sorted(meaningful))


def _normalized_email(value: object) -> str:
    return str(value or "").strip().casefold()


def _normalized_phone(value: object) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[-10:] if len(digits) >= 10 else ""


class _UnionFind:
    def __init__(self, ids: Iterable[str]):
        self.parent = {item: item for item in ids}

    def find(self, item: str) -> str:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, first: str, second: str) -> None:
        left, right = self.find(first), self.find(second)
        if left != right:
            self.parent[right] = left


def build_identity_candidates(clients: list[dict[str, Any]], counts: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
    active = [client for client in clients if client.get("status") != "inactive"]
    union = _UnionFind(str(client["id"]) for client in active)
    reasons_by_pair: dict[frozenset[str], set[str]] = defaultdict(set)

    indexes: dict[str, dict[str, list[str]]] = {
        "RFC coincidente": defaultdict(list),
        "Correo coincidente": defaultdict(list),
        "Teléfono coincidente": defaultdict(list),
        "Nombre equivalente": defaultdict(list),
    }
    for client in active:
        client_id = str(client["id"])
        values = {
            "RFC coincidente": str(client.get("rfc") or "").strip().upper(),
            "Correo coincidente": _normalized_email(client.get("email")),
            "Teléfono coincidente": _normalized_phone(client.get("phone")),
            "Nombre equivalente": normalized_name_signature(client.get("name")),
        }
        for reason, value in values.items():
            if value and (reason != "Nombre equivalente" or len(value) >= 6):
                indexes[reason][value].append(client_id)

    for reason, index in indexes.items():
        for ids in index.values():
            if len(ids) < 2:
                continue
            anchor = ids[0]
            for other in ids[1:]:
                union.union(anchor, other)
                reasons_by_pair[frozenset((anchor, other))].add(reason)

    by_id = {str(client["id"]): client for client in active}
    groups: dict[str, list[str]] = defaultdict(list)
    for client_id in by_id:
        groups[union.find(client_id)].append(client_id)

    candidates = []
    for ids in groups.values():
        if len(ids) < 2:
            continue
        reasons = set()
        for index, first in enumerate(ids):
            for second in ids[index + 1:]:
                reasons.update(reasons_by_pair.get(frozenset((first, second)), set()))
        members = []
        rfcs = set()
        for client_id in ids:
            client = by_id[client_id]
            rfc = str(client.get("rfc") or "").strip().upper()
            if rfc:
                rfcs.add(rfc)
            members.append({
                "id": client_id,
                "nombre": client.get("name") or "",
                "rfc": rfc or None,
                "correo": client.get("email"),
                "telefono": client.get("phone"),
                "estado_identidad": client.get("identity_status") or "prospect",
                "expediente_url": client.get("drive_folder_url"),
                "relaciones": {
                    label: values.get(client_id, 0) for label, values in counts.items()
                },
            })
        members.sort(key=lambda member: (not bool(member["rfc"]), member["nombre"].casefold()))
        conflicting_rfcs = len(rfcs) > 1
        canonical_options = [member["id"] for member in members if member["rfc"]] if not conflicting_rfcs else []
        confidence = "alta" if reasons.intersection({"RFC coincidente", "Correo coincidente", "Teléfono coincidente"}) else "media"
        candidates.append({
            "group_id": "|".join(sorted(ids)),
            "confidence": confidence,
            "reasons": sorted(reasons),
            "conflicting_rfcs": conflicting_rfcs,
            "canonical_options": canonical_options,
            "members": members,
        })

    return sorted(
        candidates,
        key=lambda group: (
            group["conflicting_rfcs"],
            0 if group["confidence"] == "alta" else 1,
            -len(group["members"]),
            group["members"][0]["nombre"].casefold(),
        ),
    )
