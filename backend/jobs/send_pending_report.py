from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from services.pendientes import (
    deliver_pending_report,
    deliver_pending_reminder_report,
    normalize_report_recipients,
)


DEFAULT_RECIPIENTS = (
    "pamela.alfaro@taiico.com,"
    "veronica.alfaro@taiico.com,"
    "alberto.alfaro@taiico.com,"
    "florgabriela.flores@taiico.com,"
    "juan.ibarraran@taiico.com,"
    "gilberto.gonzalez@taiico.com"
)
DEFAULT_TIMEZONE = "America/Mexico_City"
DEFAULT_HOUR = 19
DEFAULT_REMINDER_HOUR = 10
DEFAULT_SENDER_USERNAME = "alberto.alfaro@taiico.com"


def configured_recipients() -> list[str]:
    return normalize_report_recipients(
        [os.getenv("PENDING_REPORT_AUTOMATION_RECIPIENTS", DEFAULT_RECIPIENTS)]
    )


def local_now() -> datetime:
    timezone = ZoneInfo(
        os.getenv("PENDING_REPORT_AUTOMATION_TIMEZONE", DEFAULT_TIMEZONE)
    )
    return datetime.now(timezone)


def scheduled_hour() -> int:
    return int(os.getenv("PENDING_REPORT_AUTOMATION_HOUR", str(DEFAULT_HOUR)))


def should_send(now: datetime, last_sent_date: str | None) -> bool:
    return now.hour >= scheduled_hour() and last_sent_date != now.date().isoformat()


def reminder_scheduled_hour() -> int:
    return int(os.getenv("PENDING_REMINDER_AUTOMATION_HOUR", str(DEFAULT_REMINDER_HOUR)))


def should_send_reminder(now: datetime, last_sent_date: str | None) -> bool:
    return (
        now.weekday() == 0
        and now.hour >= reminder_scheduled_hour()
        and last_sent_date != now.date().isoformat()
    )


def state_path() -> Path:
    configured = os.getenv("PENDING_REPORT_AUTOMATION_STATE_FILE", "").strip()
    return (
        Path(configured).expanduser()
        if configured
        else REPOSITORY_ROOT / ".runtime" / "pending-report-state.json"
    )


def read_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def run(*, force: bool = False, force_reminder: bool = False, dry_run: bool = False) -> int:
    now = local_now()
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(".lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        due = force or should_send(now, state.get("last_sent_date"))
        reminder_due = force_reminder or should_send_reminder(
            now, state.get("last_reminder_sent_date")
        )
        if dry_run:
            print(
                json.dumps(
                    {
                        "due": due,
                        "reminder_due": reminder_due,
                        "now": now.isoformat(),
                        "last_sent_date": state.get("last_sent_date"),
                        "recipients": configured_recipients(),
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if not due and not reminder_due:
            return 0

        sender_username = os.getenv(
            "PENDING_REPORT_AUTOMATION_SENDER_USERNAME",
            DEFAULT_SENDER_USERNAME,
        ).strip().casefold()
        new_state = dict(state)
        if due:
            result = deliver_pending_report(
                configured_recipients(),
                sender_username=sender_username,
            )
            new_state.update({
                "last_sent_date": now.date().isoformat(),
                "last_sent_at": now.isoformat(),
                "sender_username": sender_username,
                "recipients": result["recipients"],
                "generated_on": result["generated_on"],
            })
            print(
                f"Informe de pendientes enviado a {len(result['recipients'])} destinatarios "
                f"el {now.isoformat()}"
            )
        if reminder_due:
            reminder_result = deliver_pending_reminder_report(
                configured_recipients(), sender_username=sender_username
            )
            new_state.update({
                "last_reminder_sent_date": now.date().isoformat(),
                "last_reminder_sent_at": now.isoformat(),
                "reminder_recipients": reminder_result["recipients"],
                "reminder_count": reminder_result["count"],
                "reminder_window_end": reminder_result["window_end"],
            })
            print(
                f"Recordatorio de pendientes enviado a "
                f"{len(reminder_result['recipients'])} destinatarios el {now.isoformat()}"
            )
        write_state(path, new_state)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--force-reminder", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    return run(
        force=arguments.force,
        force_reminder=arguments.force_reminder,
        dry_run=arguments.dry_run,
    )


if __name__ == "__main__":
    raise SystemExit(main())
