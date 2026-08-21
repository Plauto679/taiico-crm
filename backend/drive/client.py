from __future__ import annotations

import time
from pathlib import Path
from services.performance import timed


DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"


def build_drive_service():
    # googleapiclient's httplib2 transport is not thread-safe. FastAPI serves
    # requests concurrently, so sharing one cached service can reuse sockets
    # across threads and produce intermittent Errno 49/timeouts on macOS.
    # Build a lightweight service per operation while credentials remain
    # cached by google-auth itself.
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
    with timed("drive"):
        request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
        with destination_path.open("wb") as file_handle:
            downloader = MediaIoBaseDownload(file_handle, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

    return destination_path


def download_drive_file_bytes(file_id: str, *, timeout: int = 120) -> bytes:
    """Download one Drive file without googleapiclient's httplib2 transport.

    The CRM serves concurrent requests on macOS. The httplib2 downloader can
    intermittently exhaust/reuse sockets there (Errno 49), so this small read
    path uses Google Auth's requests transport and always closes its pool.
    """
    try:
        from google.auth import default
        from google.auth.exceptions import TransportError
        from google.auth.transport.requests import AuthorizedSession
        from requests.exceptions import RequestException
    except ImportError as exc:
        raise RuntimeError(
            "Google Drive dependencies are not installed. Run `pip install -r backend/requirements.txt`."
        ) from exc

    with timed("drive"):
        credentials, _ = default(scopes=[DRIVE_READONLY_SCOPE])
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
        last_error: Exception | None = None

        for attempt in range(3):
            session = AuthorizedSession(credentials)
            try:
                response = session.get(
                    url,
                    params={"alt": "media", "supportsAllDrives": "true"},
                    timeout=timeout,
                )
                response.raise_for_status()
                return response.content
            except (OSError, RequestException, TransportError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(0.25 * (2**attempt))
            finally:
                session.close()

        assert last_error is not None
        raise last_error
