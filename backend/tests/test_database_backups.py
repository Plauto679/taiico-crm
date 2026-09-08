from __future__ import annotations

import sqlite3
import sys
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobs import backup_databases_to_drive as backups


def test_inventory_has_unique_configured_drive_sources() -> None:
    sources = backups.configured_drive_sources()

    assert len(sources) == 23
    assert len({source.key for source in sources}) == len(sources)
    assert len({source.file_id for source in sources}) == len(sources)
    assert all(source.file_id for source in sources)


def test_daily_backup_is_idempotent_when_copy_already_exists() -> None:
    service = Mock()
    service.files.return_value.get.return_value.execute.return_value = {
        "id": "source-id",
        "name": "Fuente.xlsx",
        "trashed": False,
    }
    source = backups.DriveSource("source", "Fuente", "source-id")

    with patch.object(
        backups,
        "_list_files",
        return_value=[{"id": "backup-id", "name": "2026-09-08 - Fuente.xlsx"}],
    ):
        result = backups._daily_backup_in_folder(
            service, "folder-id", source, date(2026, 9, 8)
        )

    assert result["status"] == "already_exists"
    service.files.return_value.copy.assert_not_called()


def test_retention_only_trashes_marked_backups_older_than_30_days() -> None:
    service = Mock()
    listed = [
        {
            "id": "old",
            "name": "2026-08-09 - Fuente.xlsx",
            "appProperties": {"taiico_backup_date": "2026-08-09"},
        },
        {
            "id": "boundary",
            "name": "2026-08-10 - Fuente.xlsx",
            "appProperties": {"taiico_backup_date": "2026-08-10"},
        },
        {
            "id": "invalid",
            "name": "manual.xlsx",
            "appProperties": {"taiico_backup_date": "manual"},
        },
    ]

    with patch.object(backups, "_list_files", return_value=listed):
        deleted = backups.prune_old_backups(
            service, "folder-id", date(2026, 9, 8)
        )

    assert deleted == 1
    service.files.return_value.update.assert_called_once_with(
        fileId="old",
        body={"trashed": True},
        fields="id,trashed",
        supportsAllDrives=True,
    )


def test_sqlite_snapshot_is_consistent(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite3"
    destination = tmp_path / "backup.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("create table example (value text not null)")
        connection.execute("insert into example values ('ok')")
        connection.commit()

    backups._snapshot_sqlite(source, destination)

    with sqlite3.connect(destination) as connection:
        assert connection.execute("select value from example").fetchone() == ("ok",)


def test_successful_date_state_round_trip(tmp_path: Path) -> None:
    with patch.object(backups, "STATE_PATH", tmp_path / "state.json"):
        assert backups._last_successful_date() is None
        backups._remember_successful_date(date(2026, 9, 8))
        assert backups._last_successful_date() == date(2026, 9, 8)
