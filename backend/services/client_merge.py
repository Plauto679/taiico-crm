from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import MetaData, Table, update

from database import Client
from services.client_folders import normalize_rfc


def _merge_metadata(canonical_value: Any, duplicate_value: Any, duplicate_id: str) -> dict:
    canonical = dict(canonical_value or {}) if isinstance(canonical_value, dict) else {}
    duplicate = dict(duplicate_value or {}) if isinstance(duplicate_value, dict) else {}
    merged = {**duplicate, **canonical}
    merged_ids = list(merged.get("merged_client_ids") or [])
    if duplicate_id not in merged_ids:
        merged_ids.append(duplicate_id)
    merged["merged_client_ids"] = merged_ids
    merged["last_client_merge_at"] = datetime.datetime.utcnow().isoformat()
    return merged


def merge_duplicate_client(db, *, canonical_id: str, duplicate_id: str) -> dict:
    if canonical_id == duplicate_id:
        raise ValueError("El cliente principal y el duplicado deben ser distintos.")

    canonical = db.query(Client).filter(Client.id == canonical_id).first()
    duplicate = db.query(Client).filter(Client.id == duplicate_id).first()
    if not canonical or not duplicate:
        raise ValueError("No se encontraron ambos clientes para consolidar.")

    canonical_rfc = normalize_rfc(canonical.rfc)
    duplicate_rfc = normalize_rfc(duplicate.rfc)
    if not canonical_rfc or canonical_rfc != duplicate_rfc:
        raise ValueError("Solo se pueden consolidar clientes con el mismo RFC válido.")

    bind = db.get_bind()
    metadata = MetaData()
    metadata.reflect(bind=bind)
    reference_counts: dict[str, int] = {}
    for table in metadata.sorted_tables:
        if table.name == Client.__tablename__ or "client_id" not in table.c:
            continue
        references_clients = any(
            foreign_key.column.table.name == Client.__tablename__
            for foreign_key in table.c.client_id.foreign_keys
        )
        if not references_clients:
            continue
        result = db.execute(
            update(table)
            .where(table.c.client_id == duplicate_id)
            .values(client_id=canonical_id)
        )
        if result.rowcount:
            reference_counts[table.name] = result.rowcount

    for attribute in (
        "email",
        "phone",
        "drive_folder_id",
        "drive_folder_url",
        "drive_folder_name",
        "drive_verified_at",
    ):
        if not getattr(canonical, attribute) and getattr(duplicate, attribute):
            setattr(canonical, attribute, getattr(duplicate, attribute))

    canonical.rfc = canonical_rfc
    canonical.identity_status = "identified"
    canonical.metadata_json = _merge_metadata(
        canonical.metadata_json,
        duplicate.metadata_json,
        duplicate.id,
    )
    if duplicate.created_at and (
        not canonical.created_at or duplicate.created_at < canonical.created_at
    ):
        canonical.created_at = duplicate.created_at

    db.delete(duplicate)
    db.flush()
    return {
        "rfc": canonical_rfc,
        "canonical_id": canonical.id,
        "canonical_name": canonical.full_name,
        "removed_duplicate_id": duplicate_id,
        "reassigned_references": reference_counts,
    }
