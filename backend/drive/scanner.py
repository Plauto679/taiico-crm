from __future__ import annotations

from typing import Any


SUPPORTED_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}

FILE_METADATA_FIELDS = (
    "id, name, mimeType, parents, webViewLink, createdTime, modifiedTime, "
    "md5Checksum, size, version, driveId"
)


def get_drive_file(service, file_id: str) -> dict[str, Any]:
    return service.files().get(
        fileId=file_id,
        fields=FILE_METADATA_FIELDS,
        supportsAllDrives=True,
    ).execute()


def list_folder_files(service, folder_id: str, shared_drive_id: str | None = None) -> list[dict[str, Any]]:
    query = f"'{folder_id}' in parents and trashed = false"
    fields = f"nextPageToken, files({FILE_METADATA_FIELDS})"

    files: list[dict[str, Any]] = []
    page_token = None

    while True:
        request = service.files().list(
            q=query,
            fields=fields,
            pageToken=page_token,
            pageSize=1000,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            corpora="drive" if shared_drive_id else "user",
            driveId=shared_drive_id,
        )
        response = request.execute()
        files.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return files


def is_supported_source_file(file_metadata: dict[str, Any]) -> bool:
    if file_metadata.get("mimeType") == "application/vnd.google-apps.folder":
        return False
    return file_metadata.get("mimeType") in SUPPORTED_MIME_TYPES


def matches_source_config(file_metadata: dict[str, Any], source_config: dict[str, Any]) -> bool:
    filename_contains = source_config.get("filename_contains")
    if not filename_contains:
        return True
    return filename_contains.lower() in (file_metadata.get("name") or "").lower()
