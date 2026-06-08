from __future__ import annotations

from functools import lru_cache
from pathlib import Path


DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"


@lru_cache(maxsize=1)
def build_drive_service():
    try:
        from google.auth import default
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise RuntimeError(
            "Google Drive dependencies are not installed. Run `pip install -r backend/requirements.txt`."
        ) from exc

    credentials, _ = default(scopes=[DRIVE_READONLY_SCOPE])
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def download_drive_file(service, file_id: str, destination_path: Path) -> Path:
    try:
        from googleapiclient.http import MediaIoBaseDownload
    except ImportError as exc:
        raise RuntimeError(
            "Google Drive dependencies are not installed. Run `pip install -r backend/requirements.txt`."
        ) from exc

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with destination_path.open("wb") as file_handle:
        downloader = MediaIoBaseDownload(file_handle, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

    return destination_path
