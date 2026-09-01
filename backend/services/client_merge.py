from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import MetaData, Table, update

from database import Client, ClientPromotoria
from services.client_folders import normalize_rfc


def _merge_metadata(canonical_value: Any, duplicate_value: Any, duplicate_id: str) -> dict:
    canonical = dict(canonical_value or {}) if isinstance(canonical_value, dict) else {}
    duplicate = dict(duplicate_value or {}) if isinstance(duplicate_value, dict) else {}
    merged = {**duplicate, **canonical}
    merged_ids = list(merged.get("merged_client_ids") or [])
    if duplicate_id not in merged_ids:
        merged_ids.append(duplicate_id)
    merged["merged_client_ids"] = merged_ids
    aliases = list(merged.get("name_aliases") or [])
    duplicate_name = duplicate.get("previous_full_name")
    if duplicate_name and duplicate_name not in aliases:
        aliases.append(duplicate_name)
    merged["name_aliases"] = aliases
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
    if not canonical_rfc:
        raise ValueError("El cliente maestro debe tener un RFC válido.")
    if duplicate_rfc and canonical_rfc != duplicate_rfc:
        raise ValueError("Solo se pueden consolidar registros con el mismo RFC; los RFC son distintos.")

    bind = db.get_bind()

    canonical_promotorias = {
        row.promotoria: row
        for row in db.query(ClientPromotoria).filter(ClientPromotoria.client_id == canonical_id).all()
    }
    duplicate_promotorias = (
        db.query(ClientPromotoria).filter(ClientPromotoria.client_id == duplicate_id).all()
    )
    moved_promotorias = 0
    new_promotorias: list[tuple[str, list]] = []
    for duplicate_promotoria in duplicate_promotorias:
        existing = canonical_promotorias.get(duplicate_promotoria.promotoria)
        if existing:
            combined_sources = list(existing.sources_json or [])
            for source in duplicate_promotoria.sources_json or []:
                if source not in combined_sources:
                    combined_sources.append(source)
            existing.sources_json = combined_sources
            db.delete(duplicate_promotoria)
        else:
            new_promotorias.append((
                duplicate_promotoria.promotoria,
                list(duplicate_promotoria.sources_json or []),
            ))
            db.delete(duplicate_promotoria)
        moved_promotorias += 1
    db.flush()
    db.expire(canonical, ["promotorias"])

    metadata = MetaData()
    metadata.reflect(bind=bind)
    reference_counts: dict[str, int] = {}
    for table in metadata.sorted_tables:
        if table.name in {Client.__tablename__, ClientPromotoria.__tablename__} or "client_id" not in table.c:
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
    duplicate_metadata = dict(duplicate.metadata_json or {})
    duplicate_metadata["previous_full_name"] = duplicate.full_name
    if duplicate.drive_folder_id:
        legacy_folders = list(duplicate_metadata.get("legacy_drive_folders") or [])
        legacy_folders.append({
            "id": duplicate.drive_folder_id,
            "url": duplicate.drive_folder_url,
            "name": duplicate.drive_folder_name,
        })
        duplicate_metadata["legacy_drive_folders"] = legacy_folders
    canonical.metadata_json = _merge_metadata(
        canonical.metadata_json,
        duplicate_metadata,
        duplicate.id,
    )
    if duplicate.created_at and (
        not canonical.created_at or duplicate.created_at < canonical.created_at
    ):
        canonical.created_at = duplicate.created_at

    db.delete(duplicate)
    db.flush()
    for promotoria, sources in new_promotorias:
        db.add(ClientPromotoria(
            client_id=canonical_id,
            promotoria=promotoria,
            sources_json=sources,
        ))
    db.flush()
    if moved_promotorias:
        reference_counts[ClientPromotoria.__tablename__] = moved_promotorias
    return {
        "rfc": canonical_rfc,
        "canonical_id": canonical.id,
        "canonical_name": canonical.full_name,
        "removed_duplicate_id": duplicate_id,
        "reassigned_references": reference_counts,
    }
