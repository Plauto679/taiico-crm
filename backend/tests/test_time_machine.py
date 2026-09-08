from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import auth
from services import time_machine


def test_time_machine_is_an_explicit_access_module() -> None:
    config = auth.access_modules_configuration()
    module = next(item for item in config["modules"] if item["key"] == "time_machine")

    assert module == {
        "key": "time_machine",
        "label": "Time Machine",
        "column": "Permiso_Time_Machine",
    }
    assert auth._default_module_permissions("admin", ("TAIICO",))["time_machine"] == "ninguno"


def test_catalog_groups_only_managed_restore_points() -> None:
    source = time_machine.DriveSource("clientes", "Clientes", "source-id")
    files = [
        {
            "id": "backup-1",
            "name": "2026-09-08 - Clientes.xlsx",
            "createdTime": "2026-09-08T06:00:00Z",
            "size": "1200",
            "webViewLink": "https://drive.example/backup-1",
            "appProperties": {
                "taiico_backup_source_key": "clientes",
                "taiico_backup_date": "2026-09-08",
            },
        },
        {
            "id": "unknown",
            "name": "Otro.xlsx",
            "appProperties": {},
        },
    ]
    with patch.object(time_machine, "all_sources", return_value=[source]), patch.object(
        time_machine, "_build_writable_drive_service", return_value=Mock()
    ), patch.object(time_machine, "_list_files", return_value=files):
        catalog = time_machine.list_restore_points()

    assert catalog["sources"][0]["version_count"] == 1
    assert catalog["sources"][0]["versions"][0]["id"] == "backup-1"
    assert catalog["sources"][0]["latest_backup_date"] == "2026-09-08"


def test_validated_backup_rejects_a_restore_point_from_another_source() -> None:
    service = Mock()
    service.files.return_value.get.return_value.execute.return_value = {
        "id": "backup-id",
        "parents": ["folder-id"],
        "appProperties": {
            "taiico_backup_kind": time_machine.BACKUP_MARKER,
            "taiico_backup_source_key": "otra_base",
        },
    }
    source = time_machine.DriveSource("clientes", "Clientes", "source-id")

    with pytest.raises(ValueError, match="corresponde a otra base"):
        time_machine._validated_backup(service, source, "backup-id")


def test_drive_restore_preserves_canonical_id_and_creates_safety_copy() -> None:
    source = time_machine.DriveSource("clientes", "Clientes", "canonical-id")
    service = Mock()
    service.files.return_value.get.return_value.execute.return_value = {
        "id": "canonical-id",
        "name": "Clientes.xlsx",
        "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "trashed": False,
    }
    service.files.return_value.copy.return_value.execute.return_value = {
        "id": "safety-id",
        "name": "Pre-restauración - Clientes.xlsx",
    }
    service.files.return_value.update.return_value.execute.return_value = {
        "id": "canonical-id",
        "name": "Clientes.xlsx",
    }
    backup = {
        "id": "backup-id",
        "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    with patch.object(time_machine, "ensure_source_folder", return_value="folder-id"), patch.object(
        time_machine, "_download_file", return_value=b"restored workbook"
    ):
        result = time_machine._restore_drive_source(service, source, backup)

    assert result["safety_backup"]["id"] == "safety-id"
    service.files.return_value.copy.assert_called_once()
    assert service.files.return_value.update.call_args.kwargs["fileId"] == "canonical-id"


def test_sqlite_validation_accepts_valid_database_and_rejects_other_bytes(tmp_path: Path) -> None:
    valid = tmp_path / "valid.sqlite3"
    with sqlite3.connect(valid) as connection:
        connection.execute("create table example (value text)")
    time_machine._validate_sqlite(valid)

    invalid = tmp_path / "invalid.sqlite3"
    invalid.write_bytes(b"not sqlite")
    with pytest.raises(ValueError, match="SQLite válida"):
        time_machine._validate_sqlite(invalid)


def test_restore_requires_operation_permission() -> None:
    dependency = next(
        dependency.call
        for route in time_machine.router.routes
        if route.path == "/time-machine/restore"
        for dependency in route.dependant.dependencies
    )
    profile = SimpleNamespace(can_operate=lambda module: False, can_read=lambda module: True)

    with pytest.raises(Exception) as error:
        dependency(profile)

    assert getattr(error.value, "status_code", None) == 403
