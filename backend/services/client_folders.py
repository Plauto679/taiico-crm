from __future__ import annotations

import datetime
import os
import re
import threading
import time
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterable

from config import METLIFE_PATHS


DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
DEFAULT_CLIENT_FOLDERS_PARENT_ID = "18RdnheKa6uRpVcRrPmR1dmD3jXG-Rw9w"
RFC_PATTERN = re.compile(
    r"^(?:[A-ZÑ&]{3}|[A-ZÑ&]{4})(?P<date>\d{6})[A-Z0-9]{3}$",
    re.IGNORECASE,
)
_CLIENT_FOLDER_LOCKS: dict[str, threading.RLock] = {}
_CLIENT_FOLDER_LOCKS_GUARD = threading.Lock()


@contextmanager
def client_folder_creation_lock(rfc: object):
    """Serializes find-or-create operations for one RFC in this CRM process."""
    key = normalize_rfc(rfc)
    with _CLIENT_FOLDER_LOCKS_GUARD:
        lock = _CLIENT_FOLDER_LOCKS.setdefault(key, threading.RLock())
    with lock:
        yield


@dataclass(frozen=True)
class ClientFolderCandidate:
    rfc: str
    client_name: str
    folder_name: str
    policy_count: int
    aliases: tuple[str, ...]


def clean_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\xa0", " ").strip().split())


def normalize_rfc(value: object) -> str:
    return re.sub(r"[\s-]+", "", clean_text(value)).upper()


def valid_client_rfc(value: object) -> bool:
    rfc = normalize_rfc(value)
    match = RFC_PATTERN.fullmatch(rfc)
    if not match:
        return False
    try:
        datetime.datetime.strptime(f"20{match.group('date')}", "%Y%m%d")
    except ValueError:
        return False
    return True


def safe_folder_component(value: object) -> str:
    text = clean_text(value)
    text = re.sub(r"[\x00-\x1f]", "", text)
    text = text.replace("/", "-")
    return text.strip(" .")[:180]


def normalize_client_name(value: object, rfc: str) -> str:
    text = safe_folder_component(value).replace("#", "Ñ")
    if not text:
        return ""
    trimmed = text.rstrip("-")
    if len(rfc) == 13 and "-" in trimmed:
        surname, given_names = trimmed.split("-", 1)
        surname_initial = _initial(surname)
        given_initial = _initial(given_names)
        if surname_initial == rfc[0] and given_initial == rfc[3]:
            text = f"{given_names.replace('-', ' ')} {surname}"
    text = clean_text(text.replace("--", " "))
    return text.title() if len(rfc) == 13 else text


def _initial(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", clean_text(value))
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))
    return normalized[:1].upper()


def _person_name_quality(name: str, rfc: str) -> int:
    if len(rfc) != 13:
        return 0
    tokens = name.split()
    score = 0
    if tokens and _initial(tokens[0]) == rfc[3]:
        score += 4
    if len(tokens) > 1 and _initial(tokens[1]) == rfc[0]:
        score += 2
    if "#" not in name:
        score += 3
    if "-" not in name:
        score += 1
    return score


def _preferred_name(names: Iterable[str], rfc: str) -> tuple[str, tuple[str, ...]]:
    counts = Counter(name for name in names if name)
    aliases = tuple(sorted(counts, key=str.casefold))
    if not counts:
        return "", aliases
    preferred = min(
        counts,
        key=lambda name: (
            -_person_name_quality(name, rfc),
            -counts[name],
            -len(name),
            name.casefold(),
        ),
    )
    return preferred, aliases


def build_client_folder_plan(
    records: Iterable[dict],
    existing_items: Iterable[dict],
) -> dict:
    grouped_names: dict[str, list[str]] = defaultdict(list)
    policy_keys: dict[str, set[tuple[str, str]]] = defaultdict(set)
    invalid_rfcs: Counter[str] = Counter()
    missing_name_rfcs: set[str] = set()

    for record in records:
        rfc = normalize_rfc(record.get("rfc"))
        if not valid_client_rfc(rfc):
            invalid_rfcs[rfc or "(vacío)"] += 1
            continue
        name = normalize_client_name(record.get("client_name"), rfc)
        if name:
            grouped_names[rfc].append(name)
        else:
            missing_name_rfcs.add(rfc)
        policy_number = clean_text(record.get("policy_number"))
        branch = clean_text(record.get("product_branch")).upper()
        if policy_number:
            policy_keys[rfc].add((branch, policy_number))

    existing_by_rfc: dict[str, list[dict]] = defaultdict(list)
    for item in existing_items:
        if item.get("mimeType") != FOLDER_MIME_TYPE:
            continue
        prefix = clean_text(item.get("name")).split(" - ", 1)[0]
        rfc = normalize_rfc(prefix)
        if valid_client_rfc(rfc):
            existing_by_rfc[rfc].append(item)

    candidates: list[ClientFolderCandidate] = []
    missing_name_clients: list[str] = []
    conflicts: list[dict] = []
    already_exists: list[dict] = []
    name_mismatches: list[dict] = []

    for rfc in sorted(set(grouped_names) | missing_name_rfcs):
        name, aliases = _preferred_name(grouped_names[rfc], rfc)
        if not name:
            missing_name_clients.append(rfc)
            continue
        candidate = ClientFolderCandidate(
            rfc=rfc,
            client_name=name,
            folder_name=f"{rfc} - {name}",
            policy_count=len(policy_keys[rfc]),
            aliases=aliases,
        )
        if len(aliases) > 1:
            conflicts.append({"rfc": rfc, "selected_name": name, "aliases": aliases})
        if rfc in existing_by_rfc:
            existing_folders = existing_by_rfc[rfc]
            already_exists.append(
                {
                    "rfc": rfc,
                    "expected_name": candidate.folder_name,
                    "folders": existing_folders,
                }
            )
            if len(existing_folders) == 1 and existing_folders[0].get("name") != candidate.folder_name:
                name_mismatches.append(
                    {
                        "rfc": rfc,
                        "folder_id": existing_folders[0]["id"],
                        "current_name": existing_folders[0].get("name", ""),
                        "expected_name": candidate.folder_name,
                    }
                )
        else:
            candidates.append(candidate)

    return {
        "candidates": candidates,
        "already_exists": already_exists,
        "name_mismatches": name_mismatches,
        "invalid_rfcs": dict(sorted(invalid_rfcs.items())),
        "missing_name_rfcs": sorted(missing_name_clients),
        "name_conflicts": conflicts,
        "duplicate_existing_rfcs": sorted(
            rfc for rfc, items in existing_by_rfc.items() if len(items) > 1
        ),
        "summary": {
            "valid_clients": len(candidates) + len(already_exists),
            "folders_to_create": len(candidates),
            "folders_already_present": len(already_exists),
            "invalid_distinct_rfcs": len(invalid_rfcs),
            "invalid_rows": sum(invalid_rfcs.values()),
            "clients_without_name": len(missing_name_clients),
            "clients_with_name_conflicts": len(conflicts),
            "folder_name_mismatches": len(name_mismatches),
        },
    }


def load_metlife_client_records() -> tuple[list[dict], list[dict]]:
    from parsers.metlife_gmm_renovaciones import parse_metlife_gmm_renewal_workbook
    from parsers.metlife_vida_renovaciones import parse_metlife_vida_renewal_workbook

    gmm_rows, gmm_issues = parse_metlife_gmm_renewal_workbook(
        METLIFE_PATHS["RENOVACIONES_GMM"]
    )
    vida_rows, vida_issues = parse_metlife_vida_renewal_workbook(
        METLIFE_PATHS["RENOVACIONES_VIDA"]
    )
    issues = [*gmm_issues, *vida_issues]
    critical = [issue for issue in issues if issue.get("severity") == "critical"]
    if critical:
        raise ValueError("; ".join(issue["issue_summary"] for issue in critical))
    return [row.normalized_payload for row in (*gmm_rows, *vida_rows)], issues


def build_client_folder_drive_service():
    from google.auth import default
    from googleapiclient.discovery import build

    credentials, _ = default(scopes=[DRIVE_SCOPE])
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def client_folders_parent_id() -> str:
    return os.getenv(
        "GOOGLE_DRIVE_CLIENT_FOLDERS_PARENT_ID",
        DEFAULT_CLIENT_FOLDERS_PARENT_ID,
    ).strip()


def list_folder_children(service, parent_id: str) -> list[dict]:
    items: list[dict] = []
    page_token = None
    while True:
        response = service.files().list(
            q=f"'{parent_id}' in parents and trashed=false",
            spaces="drive",
            fields="nextPageToken,files(id,name,mimeType,webViewLink)",
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        items.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return items


def create_client_folders(
    service,
    parent_id: str,
    candidates: Iterable[ClientFolderCandidate],
    *,
    progress: Callable[[int, ClientFolderCandidate, dict], None] | None = None,
    workers: int = 1,
    service_factory: Callable[[], object] | None = None,
) -> list[dict]:
    candidate_list = list(candidates)

    def create_one(worker_service, candidate: ClientFolderCandidate) -> dict:
        from googleapiclient.errors import HttpError

        last_error: HttpError | None = None
        for attempt in range(5):
            try:
                return worker_service.files().create(
                    body={
                        "name": candidate.folder_name,
                        "mimeType": FOLDER_MIME_TYPE,
                        "parents": [parent_id],
                    },
                    fields="id,name,mimeType,webViewLink",
                    supportsAllDrives=True,
                ).execute()
            except HttpError as exc:
                last_error = exc
                status = getattr(exc.resp, "status", None)
                if status not in {429, 500, 502, 503, 504} or attempt == 4:
                    raise
                time.sleep(0.5 * (2**attempt))
        assert last_error is not None  # pragma: no cover - defensive
        raise last_error

    created: list[dict] = []
    if workers <= 1:
        for index, candidate in enumerate(candidate_list, start=1):
            folder = create_one(service, candidate)
            created.append(folder)
            if progress:
                progress(index, candidate, folder)
        return created

    if service_factory is None:
        raise ValueError("service_factory is required when workers is greater than one")

    thread_services = threading.local()

    def create_with_private_service(candidate: ClientFolderCandidate) -> dict:
        worker_service = getattr(thread_services, "drive", None)
        if worker_service is None:
            worker_service = service_factory()
            thread_services.drive = worker_service
        return create_one(worker_service, candidate)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(create_with_private_service, candidate): candidate
            for candidate in candidate_list
        }
        for index, future in enumerate(as_completed(futures), start=1):
            candidate = futures[future]
            folder = future.result()
            created.append(folder)
            if progress:
                progress(index, candidate, folder)
    return created


def rename_client_folders(service, mismatches: Iterable[dict]) -> list[dict]:
    renamed: list[dict] = []
    for mismatch in mismatches:
        updated = service.files().update(
            fileId=mismatch["folder_id"],
            body={"name": mismatch["expected_name"]},
            fields="id,name,mimeType,webViewLink",
            supportsAllDrives=True,
        ).execute()
        renamed.append(updated)
    return renamed
