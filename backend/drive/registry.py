from __future__ import annotations

import datetime
from typing import Any

from database import SourceDocument


def parse_drive_time(value: str | None) -> datetime.datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.datetime.fromisoformat(normalized)
    return parsed.replace(tzinfo=None)


def build_source_uri(file_id: str) -> str:
    return f"google_drive:{file_id}"


def upsert_drive_source_document(db, file_metadata: dict[str, Any], source_config: dict[str, Any], source_key: str):
    file_id = file_metadata["id"]
    source_uri = build_source_uri(file_id)
    source_document = db.query(SourceDocument).filter(SourceDocument.source_uri == source_uri).first()
    created = source_document is None

    if source_document is None:
        source_document = SourceDocument(
            storage_provider="google_drive",
            google_drive_file_id=file_id,
            source_uri=source_uri,
            original_filename=file_metadata.get("name") or file_id,
            source_category=source_config["source_category"],
            insurer_id=source_config.get("insurer_id"),
            product_branch=source_config.get("product_branch"),
        )
        db.add(source_document)

    parents = file_metadata.get("parents") or []
    source_document.storage_provider = "google_drive"
    source_document.google_drive_file_id = file_id
    source_document.google_drive_parent_id = parents[0] if parents else source_config.get("folder_id")
    source_document.shared_drive_id = file_metadata.get("driveId")
    source_document.source_uri = source_uri
    source_document.web_view_link = file_metadata.get("webViewLink")
    source_document.original_filename = file_metadata.get("name") or source_document.original_filename
    source_document.mime_type = file_metadata.get("mimeType")
    source_document.source_category = source_config["source_category"]
    source_document.insurer_id = source_config.get("insurer_id")
    source_document.product_branch = source_config.get("product_branch")
    source_document.drive_created_at = parse_drive_time(file_metadata.get("createdTime"))
    source_document.drive_modified_at = parse_drive_time(file_metadata.get("modifiedTime"))
    source_document.metadata_json = {
        **(source_document.metadata_json or {}),
        "drive_name": file_metadata.get("name"),
        "drive_file_extension": (file_metadata.get("name") or "").split(".")[-1].lower(),
        "drive_size": file_metadata.get("size"),
        "drive_md5_checksum": file_metadata.get("md5Checksum"),
        "drive_version": file_metadata.get("version"),
        "configured_source_key": source_key,
        "configured_parser_name": source_config.get("parser_name"),
        "detected_by": "drive_scanner",
        "scanner_version": "1.0.0",
        "status": "registered",
    }
    db.flush()

    return source_document, created

