from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from services.client_folders import (
    FOLDER_MIME_TYPE,
    normalize_client_name,
    normalize_rfc,
    valid_client_rfc,
)


def _client_payload(client: dict) -> dict:
    return {
        "id": str(client.get("id") or ""),
        "nombre": str(client.get("nombre") or "").strip(),
        "rfc": normalize_rfc(client.get("rfc")),
        "expediente_id": str(client.get("expediente_id") or ""),
    }


def _folder_payload(folder: dict) -> dict:
    folder_id = str(folder.get("id") or "")
    return {
        "id": folder_id,
        "name": str(folder.get("name") or "").strip(),
        "url": str(folder.get("webViewLink") or "").strip()
        or (f"https://drive.google.com/drive/folders/{folder_id}" if folder_id else ""),
    }


def folder_rfc(folder: dict) -> str:
    return normalize_rfc(str(folder.get("name") or "").split(" - ", 1)[0])


def build_client_registry_audit(
    clients: Iterable[dict],
    drive_items: Iterable[dict],
    *,
    detail_limit: int = 200,
) -> dict:
    client_rows = [_client_payload(client) for client in clients]
    folders = [
        _folder_payload(item)
        for item in drive_items
        if item.get("mimeType") == FOLDER_MIME_TYPE
    ]

    clients_by_rfc: dict[str, list[dict]] = defaultdict(list)
    prospects: list[dict] = []
    invalid_clients: list[dict] = []
    for client in client_rows:
        rfc = client["rfc"]
        if not rfc:
            prospects.append(client)
        elif not valid_client_rfc(rfc):
            invalid_clients.append(client)
        else:
            clients_by_rfc[rfc].append(client)

    folders_by_rfc: dict[str, list[dict]] = defaultdict(list)
    malformed_folders: list[dict] = []
    for folder in folders:
        rfc = folder_rfc(folder)
        if valid_client_rfc(rfc):
            folders_by_rfc[rfc].append(folder)
        else:
            malformed_folders.append(folder)

    duplicate_clients = [
        {"rfc": rfc, "clients": rows}
        for rfc, rows in sorted(clients_by_rfc.items())
        if len(rows) > 1
    ]
    duplicate_folders = [
        {"rfc": rfc, "folders": rows}
        for rfc, rows in sorted(folders_by_rfc.items())
        if len(rows) > 1
    ]

    linkable: list[dict] = []
    linked: list[dict] = []
    stale_links: list[dict] = []
    missing_folders: list[dict] = []
    name_mismatches: list[dict] = []
    duplicate_client_rfcs = {item["rfc"] for item in duplicate_clients}
    duplicate_folder_rfcs = {item["rfc"] for item in duplicate_folders}

    for rfc, rows in sorted(clients_by_rfc.items()):
        if rfc in duplicate_client_rfcs or rfc in duplicate_folder_rfcs:
            continue
        client = rows[0]
        matching_folders = folders_by_rfc.get(rfc, [])
        if not matching_folders:
            missing_folders.append(client)
            continue
        folder = matching_folders[0]
        mapping = {"rfc": rfc, "client": client, "folder": folder}
        if client["expediente_id"] == folder["id"]:
            linked.append(mapping)
        else:
            linkable.append(mapping)
            if client["expediente_id"]:
                stale_links.append(mapping)

        normalized_name = normalize_client_name(client["nombre"], rfc)
        expected_name = f"{rfc} - {normalized_name}" if normalized_name else rfc
        if folder["name"] != expected_name:
            name_mismatches.append({**mapping, "expected_name": expected_name})

    registered_rfcs = set(clients_by_rfc)
    unregistered_folders = [
        {"rfc": rfc, "folder": folder}
        for rfc, rows in sorted(folders_by_rfc.items())
        if rfc not in registered_rfcs
        for folder in rows
    ]

    details = {
        "duplicate_client_rfcs": duplicate_clients,
        "duplicate_drive_rfcs": duplicate_folders,
        "invalid_clients": invalid_clients,
        "malformed_folders": malformed_folders,
        "missing_folders": missing_folders,
        "linkable_clients": linkable,
        "stale_links": stale_links,
        "folder_name_mismatches": name_mismatches,
        "unregistered_folders": unregistered_folders,
    }
    truncated = {
        key: len(rows) > detail_limit
        for key, rows in details.items()
    }
    details = {key: rows[:detail_limit] for key, rows in details.items()}

    return {
        "summary": {
            "total_clients": len(client_rows),
            "prospects_without_rfc": len(prospects),
            "identified_clients": sum(len(rows) for rows in clients_by_rfc.values()),
            "invalid_client_rfcs": len(invalid_clients),
            "duplicate_client_rfcs": len(duplicate_clients),
            "total_drive_folders": len(folders),
            "malformed_drive_folders": len(malformed_folders),
            "duplicate_drive_rfcs": len(duplicate_folders),
            "linked_clients": len(linked),
            "safe_links_available": len(linkable),
            "clients_missing_folder": len(missing_folders),
            "unregistered_drive_folders": len(unregistered_folders),
            "folder_name_mismatches": len(name_mismatches),
        },
        "details": details,
        "truncated": truncated,
        "safe_link_updates": linkable,
    }
