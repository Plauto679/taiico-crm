from __future__ import annotations

import hmac
import io
import os
import posixpath
import re
import threading
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape

import pandas as pd
from dotenv import load_dotenv

from drive.client import build_drive_service


load_dotenv(Path(__file__).resolve().parents[1] / ".env")


USERS_FILE_ID_ENV = "GOOGLE_DRIVE_USERS_FILE_ID"
USERS_CACHE_SECONDS_ENV = "AUTH_USERS_CACHE_SECONDS"
DEFAULT_CACHE_SECONDS = 300
REQUIRED_COLUMNS = {"Usuario", "Password"}

_cache_lock = threading.RLock()
_cached_credentials: dict[str, str] | None = None
_cache_expires_at = 0.0


def _download_users_workbook(file_id: str) -> bytes:
    try:
        from googleapiclient.http import MediaIoBaseDownload
    except ImportError as exc:
        raise RuntimeError(
            "Google Drive dependencies are not installed. "
            "Run `pip install -r backend/requirements.txt`."
        ) from exc

    output = io.BytesIO()
    request = build_drive_service().files().get_media(
        fileId=file_id,
        supportsAllDrives=True,
    )
    downloader = MediaIoBaseDownload(output, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return output.getvalue()


def _build_writable_drive_service():
    try:
        from google.auth import default
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Google Drive dependencies are not installed. "
            "Run `pip install -r backend/requirements.txt`."
        ) from exc

    credentials, _ = default(scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _upload_users_workbook(file_id: str, workbook: bytes) -> None:
    try:
        from googleapiclient.http import MediaIoBaseUpload
    except ImportError as exc:
        raise RuntimeError(
            "Google Drive dependencies are not installed. "
            "Run `pip install -r backend/requirements.txt`."
        ) from exc

    media = MediaIoBaseUpload(
        io.BytesIO(workbook),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        resumable=False,
    )
    _build_writable_drive_service().files().update(
        fileId=file_id,
        media_body=media,
        supportsAllDrives=True,
    ).execute()


def _read_credentials(workbook: bytes) -> dict[str, str]:
    table = pd.read_excel(io.BytesIO(workbook), dtype=str, keep_default_na=False)
    missing_columns = REQUIRED_COLUMNS.difference(table.columns)
    if missing_columns:
        raise ValueError(
            "Users workbook is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    credentials: dict[str, str] = {}
    for _, row in table.iterrows():
        username = str(row["Usuario"]).strip().casefold()
        password = str(row["Password"])
        if username and password:
            credentials[username] = password
    return credentials


def _cache_seconds() -> int:
    value = int(os.getenv(USERS_CACHE_SECONDS_ENV, str(DEFAULT_CACHE_SECONDS)))
    return max(0, value)


def _load_credentials() -> dict[str, str]:
    global _cached_credentials, _cache_expires_at

    file_id = os.getenv(USERS_FILE_ID_ENV, "").strip()
    if not file_id:
        raise RuntimeError(f"{USERS_FILE_ID_ENV} is not configured")

    now = time.monotonic()
    with _cache_lock:
        if _cached_credentials is not None and now < _cache_expires_at:
            return _cached_credentials

        credentials = _read_credentials(_download_users_workbook(file_id))
        _cached_credentials = credentials
        _cache_expires_at = now + _cache_seconds()
        return credentials


def clear_credentials_cache() -> None:
    """Clear the in-memory workbook cache (primarily for tests)."""
    global _cached_credentials, _cache_expires_at
    with _cache_lock:
        _cached_credentials = None
        _cache_expires_at = 0.0


def verify_credentials(username, password) -> bool:
    """Verify credentials against the configured read-only Drive workbook."""
    try:
        stored_password = _load_credentials().get(str(username).strip().casefold())
        if stored_password is None:
            return False
        return hmac.compare_digest(stored_password, str(password))
    except Exception as exc:
        # Fail closed without logging credential values.
        print(f"Authentication unavailable: {type(exc).__name__}: {exc}")
        return False


def registered_user(username: str) -> bool:
    """Return whether an email exists without exposing any stored password."""
    try:
        return str(username).strip().casefold() in _load_credentials()
    except Exception as exc:
        print(f"Authentication directory unavailable: {type(exc).__name__}: {exc}")
        return False


_SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _xlsx_cell_text(cell, shared_strings: list[str]) -> str:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        return "".join(
            node.text or ""
            for node in cell.findall(f".//{{{_SPREADSHEET_NS}}}t")
        )
    value = cell.find(f"{{{_SPREADSHEET_NS}}}v")
    if value is None or value.text is None:
        return ""
    if cell_type == "s":
        return shared_strings[int(value.text)]
    return value.text


def _replace_password_in_xlsx(
    workbook_bytes: bytes,
    normalized_username: str,
    new_password: str,
) -> bytes:
    source = io.BytesIO(workbook_bytes)
    with zipfile.ZipFile(source, "r") as archive:
        names = archive.namelist()
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in names:
            shared_root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            shared_strings = [
                "".join(
                    node.text or ""
                    for node in item.findall(f".//{{{_SPREADSHEET_NS}}}t")
                )
                for item in shared_root.findall(f"{{{_SPREADSHEET_NS}}}si")
            ]

        workbook_root = ElementTree.fromstring(archive.read("xl/workbook.xml"))
        relationship_root = ElementTree.fromstring(
            archive.read("xl/_rels/workbook.xml.rels")
        )
        targets = {
            relationship.get("Id"): relationship.get("Target")
            for relationship in relationship_root.findall(
                f"{{{_PACKAGE_REL_NS}}}Relationship"
            )
        }

        updated_path = None
        updated_xml = None
        for sheet in workbook_root.findall(
            f".//{{{_SPREADSHEET_NS}}}sheet"
        ):
            relationship_id = sheet.get(f"{{{_OFFICE_REL_NS}}}id")
            target = targets.get(relationship_id)
            if not target:
                continue
            cleaned_target = target.lstrip("/")
            sheet_path = (
                posixpath.normpath(cleaned_target)
                if cleaned_target.startswith("xl/")
                else posixpath.normpath(posixpath.join("xl", cleaned_target))
            )
            sheet_root = ElementTree.fromstring(archive.read(sheet_path))
            rows = sheet_root.findall(
                f".//{{{_SPREADSHEET_NS}}}sheetData/{{{_SPREADSHEET_NS}}}row"
            )
            if not rows:
                continue

            headers = {}
            for cell in rows[0].findall(f"{{{_SPREADSHEET_NS}}}c"):
                reference = cell.get("r", "")
                column = "".join(character for character in reference if character.isalpha())
                headers[_xlsx_cell_text(cell, shared_strings).strip()] = column
            if not REQUIRED_COLUMNS.issubset(headers):
                continue

            username_column = headers["Usuario"]
            password_column = headers["Password"]
            for row in rows[1:]:
                cells = {
                    "".join(
                        character
                        for character in cell.get("r", "")
                        if character.isalpha()
                    ): cell
                    for cell in row.findall(f"{{{_SPREADSHEET_NS}}}c")
                }
                username_cell = cells.get(username_column)
                if username_cell is None:
                    continue
                if (
                    _xlsx_cell_text(username_cell, shared_strings).strip().casefold()
                    != normalized_username
                ):
                    continue
                password_cell = cells.get(password_column)
                if password_cell is None:
                    raise ValueError(
                        "Registered user has no password cell in the workbook"
                    )

                cell_reference = password_cell.get("r", "")
                original_xml = archive.read(sheet_path)
                encoded_reference = re.escape(cell_reference.encode("utf-8"))
                cell_pattern = re.compile(
                    rb"<c\b(?=[^>]*\br=[\"']"
                    + encoded_reference
                    + rb"[\"'])[^>]*>.*?</c>",
                    re.DOTALL,
                )
                match = cell_pattern.search(original_xml)
                prefix = b""
                if match is None:
                    prefixed_cell_pattern = re.compile(
                        rb"<(?P<prefix>[A-Za-z_][\w.-]*:)c\b"
                        rb"(?=[^>]*\br=[\"']"
                        + encoded_reference
                        + rb"[\"'])[^>]*>.*?</(?P=prefix)c>",
                        re.DOTALL,
                    )
                    match = prefixed_cell_pattern.search(original_xml)
                    if match is not None:
                        prefix = match.group("prefix")
                if match is None:
                    raise ValueError(
                        f"Password cell {cell_reference} was not found in worksheet XML"
                    )

                original_cell = match.group(0)
                start_tag_end = original_cell.find(b">")
                start_tag = original_cell[: start_tag_end + 1]
                start_tag = re.sub(
                    rb"\s+t=[\"'][^\"']*[\"']",
                    b"",
                    start_tag,
                    count=1,
                )
                start_tag = start_tag[:-1] + b' t="inlineStr">'

                password_text = str(new_password)
                preserve_space = (
                    ' xml:space="preserve"'
                    if password_text != password_text.strip()
                    else ""
                )
                escaped_password = escape(password_text).encode("utf-8")
                replacement = (
                    start_tag
                    + b"<"
                    + prefix
                    + b"is><"
                    + prefix
                    + b"t"
                    + preserve_space.encode("utf-8")
                    + b">"
                    + escaped_password
                    + b"</"
                    + prefix
                    + b"t></"
                    + prefix
                    + b"is></"
                    + prefix
                    + b"c>"
                )
                updated_path = sheet_path
                updated_xml = (
                    original_xml[: match.start()]
                    + replacement
                    + original_xml[match.end() :]
                )
                break
            if updated_path:
                break

        if not updated_path or updated_xml is None:
            raise KeyError("Registered user not found")

        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as updated_archive:
            for item in archive.infolist():
                content = updated_xml if item.filename == updated_path else archive.read(item.filename)
                updated_archive.writestr(item, content)
        return output.getvalue()


def update_password(username: str, new_password: str) -> None:
    """Update one password cell while preserving the existing workbook."""
    global _cached_credentials, _cache_expires_at

    normalized_username = str(username).strip().casefold()
    file_id = os.getenv(USERS_FILE_ID_ENV, "").strip()
    if not file_id:
        raise RuntimeError(f"{USERS_FILE_ID_ENV} is not configured")

    with _cache_lock:
        workbook_bytes = _download_users_workbook(file_id)
        updated_workbook = _replace_password_in_xlsx(
            workbook_bytes,
            normalized_username,
            new_password,
        )
        _upload_users_workbook(file_id, updated_workbook)
        _cached_credentials = None
        _cache_expires_at = 0.0
