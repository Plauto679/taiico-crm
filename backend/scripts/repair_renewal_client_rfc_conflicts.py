from __future__ import annotations

import argparse
import datetime
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import MetaData


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import (  # noqa: E402
    DATABASE_URL,
    Client,
    IngestionRecord,
    IngestionRun,
    Renewal,
    SessionLocal,
)
from services.client_folders import normalize_rfc  # noqa: E402
from services.client_merge import merge_duplicate_client  # noqa: E402


CREATED_FROM = "canonical_metlife_renewal_ingestion"


def affected_clients(db, created_date: datetime.date) -> list[Client]:
    return [
        client
        for client in db.query(Client).all()
        if client.created_at
        and client.created_at.date() == created_date
        and (client.metadata_json or {}).get("created_from") == CREATED_FROM
        and (client.metadata_json or {}).get("source_rfc_conflict_client_id")
        and not normalize_rfc(client.rfc)
    ]


def source_rfcs_by_client(db, client_ids: set[str]) -> dict[str, set[str]]:
    run_ids = [
        row[0]
        for row in db.query(IngestionRun.id)
        .filter(IngestionRun.parser_name == "metlife_vida_renewal_workbook")
        .all()
    ]
    if not run_ids or not client_ids:
        return {}
    records = (
        db.query(IngestionRecord)
        .filter(
            IngestionRecord.ingestion_run_id.in_(run_ids),
            IngestionRecord.related_object_type == "renewal",
            IngestionRecord.related_object_id.is_not(None),
        )
        .all()
    )
    renewal_ids = {record.related_object_id for record in records}
    renewal_clients = {
        renewal_id: client_id
        for renewal_id, client_id in db.query(Renewal.id, Renewal.client_id)
        .filter(Renewal.id.in_(renewal_ids))
        .all()
        if client_id in client_ids
    }
    result: dict[str, set[str]] = {}
    for record in records:
        client_id = renewal_clients.get(record.related_object_id)
        if not client_id:
            continue
        source_rfc = normalize_rfc((record.normalized_payload or {}).get("rfc"))
        if source_rfc:
            result.setdefault(client_id, set()).add(source_rfc)
    return result


def validate_plan(
    db, duplicates: list[Client]
) -> tuple[list[tuple[Client, Client]], list[dict]]:
    plan: list[tuple[Client, Client]] = []
    ambiguous: list[dict] = []
    errors: list[str] = []
    duplicate_ids = {client.id for client in duplicates}
    source_rfcs = source_rfcs_by_client(db, duplicate_ids)
    for duplicate in duplicates:
        metadata = duplicate.metadata_json or {}
        canonical_id = str(metadata.get("source_rfc_conflict_client_id") or "")
        source_rfc = normalize_rfc(metadata.get("source_rfc"))
        canonical = db.query(Client).filter(Client.id == canonical_id).first()
        observed_rfcs = source_rfcs.get(duplicate.id, set())
        if observed_rfcs != {source_rfc}:
            ambiguous.append(
                {
                    "id": duplicate.id,
                    "name": duplicate.full_name,
                    "expected_rfc": source_rfc,
                    "observed_rfcs": sorted(observed_rfcs),
                }
            )
            continue
        if canonical is None:
            errors.append(f"{duplicate.id}: no existe el cliente maestro {canonical_id}")
            continue
        if canonical.id in duplicate_ids:
            errors.append(f"{duplicate.id}: el cliente maestro también está marcado como duplicado")
            continue
        if not source_rfc or normalize_rfc(canonical.rfc) != source_rfc:
            errors.append(
                f"{duplicate.id}: el RFC fuente {source_rfc or '-'} no coincide con el maestro"
            )
            continue
        plan.append((duplicate, canonical))
    if errors:
        raise RuntimeError("Plan de reparación inválido: " + "; ".join(errors[:20]))
    return plan, ambiguous


def sqlite_path() -> Path:
    prefix = "sqlite:///"
    if not DATABASE_URL.startswith(prefix):
        raise RuntimeError("Esta reparación controlada requiere la base SQLite local")
    raw_path = DATABASE_URL[len(prefix):]
    path = Path(raw_path)
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def create_pre_repair_backup(created_date: datetime.date) -> Path:
    source = sqlite_path()
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    destination = (
        PROJECT_ROOT
        / ".runtime"
        / "repairs"
        / f"pre-client-rfc-repair-{created_date.isoformat()}-{timestamp}.sqlite3"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as current, sqlite3.connect(destination) as backup:
        current.backup(backup)
    return destination


def clear_self_conflict_markers(db) -> int:
    cleaned = 0
    for client in db.query(Client).all():
        metadata = dict(client.metadata_json or {})
        if metadata.get("source_rfc_conflict_client_id") != client.id:
            continue
        metadata.pop("source_rfc_conflict_client_id", None)
        client.metadata_json = metadata
        cleaned += 1
    return cleaned


def execute(created_date: datetime.date, apply: bool) -> dict:
    db = SessionLocal()
    try:
        duplicates = affected_clients(db, created_date)
        plan, ambiguous = validate_plan(db, duplicates)
        summary = {
            "created_date": created_date.isoformat(),
            "mode": "apply" if apply else "dry_run",
            "affected_clients": len(duplicates),
            "candidates": len(plan),
            "canonical_clients": len({canonical.id for _, canonical in plan}),
            "skipped_ambiguous": ambiguous,
        }
        if not apply:
            db.rollback()
            return summary

        backup_path = create_pre_repair_backup(created_date)
        reflected_metadata = MetaData()
        reflected_metadata.reflect(bind=db.get_bind())
        references: Counter[str] = Counter()
        for duplicate, canonical in plan:
            result = merge_duplicate_client(
                db,
                canonical_id=canonical.id,
                duplicate_id=duplicate.id,
                reflected_metadata=reflected_metadata,
            )
            references.update(result["reassigned_references"])
        cleaned_markers = clear_self_conflict_markers(db)
        db.commit()
        return {
            **summary,
            "merged": len(plan),
            "reassigned_references": dict(sorted(references.items())),
            "cleaned_self_conflict_markers": cleaned_markers,
            "pre_repair_backup": str(backup_path),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repara clientes provisionales enlazándolos por su RFC fuente"
    )
    parser.add_argument("--created-date", required=True, help="Fecha UTC YYYY-MM-DD")
    parser.add_argument("--apply", action="store_true", help="Aplica la reparación; sin esto solo simula")
    args = parser.parse_args()
    result = execute(datetime.date.fromisoformat(args.created_date), args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
