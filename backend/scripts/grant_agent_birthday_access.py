from __future__ import annotations

import io
import os
import sys
import zipfile
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from services import auth  # noqa: E402


ALBERTO_EMAIL = "alberto.alfaro@taiico.com"


def main() -> None:
    load_dotenv(BACKEND_DIR / ".env")
    file_id = os.getenv(auth.USERS_FILE_ID_ENV, "").strip()
    if not file_id:
        raise RuntimeError(f"{auth.USERS_FILE_ID_ENV} is not configured")

    original = auth._download_users_workbook(file_id)
    updated = auth._set_permission_column_in_xlsx(
        original,
        auth.MODULE_COLUMNS["cumpleanos_agentes"],
        {ALBERTO_EMAIL: "Lectura"},
        default_value="Ninguno",
    )
    with zipfile.ZipFile(io.BytesIO(updated)) as archive:
        if archive.testzip() is not None:
            raise ValueError("The updated access workbook failed ZIP validation")

    _, profiles = auth._read_user_directory(updated)
    if ALBERTO_EMAIL not in profiles:
        raise ValueError("Alberto is not registered in the access workbook")
    if not profiles[ALBERTO_EMAIL].can_read("cumpleanos_agentes"):
        raise ValueError("Alberto did not receive agent birthday access")
    unexpected = [
        username
        for username, profile in profiles.items()
        if username != ALBERTO_EMAIL
        and profile.can_read("cumpleanos_agentes")
    ]
    if unexpected:
        raise ValueError("Unexpected agent birthday access was granted")

    auth._upload_users_workbook(file_id, updated)
    auth.clear_credentials_cache()
    verified = auth._download_users_workbook(file_id)
    _, verified_profiles = auth._read_user_directory(verified)
    if not verified_profiles[ALBERTO_EMAIL].can_read("cumpleanos_agentes"):
        raise ValueError("Drive verification failed after upload")
    print(
        "Permiso_Cumpleanos_Agentes actualizado: "
        "Alberto=Lectura; todos los demás=Ninguno."
    )


if __name__ == "__main__":
    main()
