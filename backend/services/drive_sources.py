from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from config import GOOGLE_DRIVE_SHARED_DRIVE_ID, GOOGLE_DRIVE_SOURCE_FOLDERS
from database import SessionLocal, SourceDocument
from drive.client import build_drive_service, download_drive_file
from drive.registry import upsert_drive_source_document
from drive.scanner import is_supported_source_file, list_folder_files, matches_source_config
from parsers.metlife_cobranza import PARSER_VERSION as METLIFE_PARSER_VERSION
from parsers.metlife_cobranza import parse_metlife_cobranza_workbook
from parsers.sura_cobranza import PARSER_VERSION as SURA_PARSER_VERSION
from parsers.sura_cobranza import parse_sura_cobranza_workbook


router = APIRouter(prefix="/drive-sources", tags=["drive-sources"])


class DriveScanRequest(BaseModel):
    source_key: Optional[str] = None
    force: bool = False


class DriveDryRunRequest(BaseModel):
    parser_name: Optional[str] = None
    sheets: Optional[list[str]] = None


def format_drive_error(exc: Exception) -> str:
    try:
        from googleapiclient.errors import HttpError
    except ImportError:
        return str(exc)

    if isinstance(exc, HttpError):
        return f"Google Drive API error: {exc.reason}"
    return str(exc)


def serialize_source_document(source_document: SourceDocument) -> dict:
    return {
        "id": source_document.id,
        "storage_provider": source_document.storage_provider,
        "google_drive_file_id": source_document.google_drive_file_id,
        "google_drive_parent_id": source_document.google_drive_parent_id,
        "shared_drive_id": source_document.shared_drive_id,
        "source_uri": source_document.source_uri,
        "web_view_link": source_document.web_view_link,
        "original_filename": source_document.original_filename,
        "mime_type": source_document.mime_type,
        "source_category": source_document.source_category,
        "insurer_id": source_document.insurer_id,
        "product_branch": source_document.product_branch,
        "drive_created_at": source_document.drive_created_at.isoformat() if source_document.drive_created_at else None,
        "drive_modified_at": source_document.drive_modified_at.isoformat() if source_document.drive_modified_at else None,
        "detected_at": source_document.detected_at.isoformat() if source_document.detected_at else None,
        "archived_at": source_document.archived_at.isoformat() if source_document.archived_at else None,
        "metadata": source_document.metadata_json,
    }


def resolve_source_configs(source_key: str | None):
    if source_key:
        source_config = GOOGLE_DRIVE_SOURCE_FOLDERS.get(source_key)
        if not source_config:
            raise HTTPException(status_code=404, detail=f"Unknown Drive source key: {source_key}")
        return {source_key: source_config}
    return GOOGLE_DRIVE_SOURCE_FOLDERS


def parse_drive_source(parser_name: str, path: str, sheets: list[str] | None):
    if parser_name == "metlife_cobranza_workbook":
        return parse_metlife_cobranza_workbook(path, sheets=sheets), METLIFE_PARSER_VERSION
    if parser_name == "sura_cobranza_workbook":
        return parse_sura_cobranza_workbook(path, sheets=sheets), SURA_PARSER_VERSION
    raise HTTPException(status_code=400, detail=f"Unsupported parser for dry run: {parser_name}")


@router.post("/scan")
async def scan_drive_sources(request: DriveScanRequest = Body(default=DriveScanRequest())):
    source_configs = resolve_source_configs(request.source_key)
    missing = [key for key, config in source_configs.items() if not config.get("folder_id")]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing Google Drive folder ID configuration for: {', '.join(missing)}",
        )

    try:
        service = build_drive_service()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    db = SessionLocal()
    try:
        files_seen = 0
        unsupported_files = 0
        non_matching_files = 0
        created_count = 0
        updated_count = 0
        registered_documents = []

        for key, config in source_configs.items():
            try:
                files = list_folder_files(service, config["folder_id"], GOOGLE_DRIVE_SHARED_DRIVE_ID)
            except Exception as exc:
                raise HTTPException(status_code=502, detail=format_drive_error(exc)) from exc

            files_seen += len(files)

            for file_metadata in files:
                if not is_supported_source_file(file_metadata):
                    unsupported_files += 1
                    continue
                if not matches_source_config(file_metadata, config):
                    non_matching_files += 1
                    continue

                source_document, created = upsert_drive_source_document(db, file_metadata, config, key)
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                registered_documents.append(serialize_source_document(source_document))

        db.commit()
        return {
            "scanned_folders": len(source_configs),
            "files_seen": files_seen,
            "unsupported_files": unsupported_files,
            "non_matching_files": non_matching_files,
            "source_documents_created": created_count,
            "source_documents_updated": updated_count,
            "registered_documents": registered_documents,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("")
async def list_drive_source_documents(
    source_key: Optional[str] = Query(None),
    source_category: Optional[str] = Query(None),
    insurer_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    db = SessionLocal()
    try:
        query = db.query(SourceDocument).filter(SourceDocument.storage_provider == "google_drive")

        if source_key:
            query = query.filter(SourceDocument.metadata_json["configured_source_key"].as_string() == source_key)
        if source_category:
            query = query.filter(SourceDocument.source_category == source_category)
        if insurer_id:
            query = query.filter(SourceDocument.insurer_id == insurer_id)

        source_documents = query.order_by(SourceDocument.detected_at.desc()).limit(limit).all()
        return [serialize_source_document(source_document) for source_document in source_documents]
    finally:
        db.close()


@router.get("/{source_document_id}")
async def get_drive_source_document(source_document_id: str):
    db = SessionLocal()
    try:
        source_document = db.query(SourceDocument).filter(SourceDocument.id == source_document_id).first()
        if not source_document:
            raise HTTPException(status_code=404, detail="Source document not found")
        return serialize_source_document(source_document)
    finally:
        db.close()


@router.post("/{source_document_id}/dry-run")
async def dry_run_drive_source_document(source_document_id: str, request: DriveDryRunRequest = Body(default=DriveDryRunRequest())):
    db = SessionLocal()
    try:
        source_document = db.query(SourceDocument).filter(SourceDocument.id == source_document_id).first()
        if not source_document:
            raise HTTPException(status_code=404, detail="Source document not found")
        if source_document.storage_provider != "google_drive" or not source_document.google_drive_file_id:
            raise HTTPException(status_code=400, detail="Source document is not a Google Drive file")

        parser_name = request.parser_name or (source_document.metadata_json or {}).get("configured_parser_name")
        if not parser_name:
            raise HTTPException(status_code=400, detail=f"Unsupported parser for dry run: {parser_name}")

        try:
            service = build_drive_service()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        suffix = ""
        if source_document.original_filename and "." in source_document.original_filename:
            suffix = "." + source_document.original_filename.split(".")[-1]

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(prefix="taiico-drive-source-", suffix=suffix, delete=False) as temp_file:
                temp_path = temp_file.name

            download_drive_file(service, source_document.google_drive_file_id, Path(temp_path))
            (parsed_rows, workbook_issues), parser_version = parse_drive_source(parser_name, temp_path, request.sheets)

            sheet_counts = {}
            row_issue_count = 0
            for row in parsed_rows:
                sheet_counts[row.sheet_name] = sheet_counts.get(row.sheet_name, 0) + 1
                row_issue_count += len(row.issues)

            return {
                "dry_run": True,
                "source_document": serialize_source_document(source_document),
                "parser_name": parser_name,
                "parser_version": parser_version,
                "rows_read": len(parsed_rows),
                "sheet_counts": sheet_counts,
                "workbook_issues": workbook_issues,
                "row_issues_count": row_issue_count,
                "sample_rows": [
                    {
                        "sheet_name": row.sheet_name,
                        "row_number": row.row_number,
                        "row_hash": row.row_hash,
                        "normalized_payload": row.normalized_payload,
                        "issues": row.issues,
                    }
                    for row in parsed_rows[:3]
                ],
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail=format_drive_error(exc)) from exc
        finally:
            if temp_path:
                Path(temp_path).unlink(missing_ok=True)
    finally:
        db.close()
