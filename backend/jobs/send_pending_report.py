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
from services.automatic_mails import (  # noqa: E402
    automation_config,
    local_now_for,
    schedule_matches,
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
PROMOTORIA_AUTOMATION_IDS = (
    "pending_promotoria_abbondanza",
    "pending_promotoria_ekilibra",
    "pending_promotoria_fenix_prevision",
)


def configured_recipients(automation_id: str = "pending_daily") -> list[str]:
    return normalize_report_recipients(
        automation_config(automation_id)["recipients"]
    )


def local_now() -> datetime:
    return local_now_for("pending_daily")


def scheduled_hour() -> int:
    return int(automation_config("pending_daily")["hour"])


def should_send(now: datetime, last_sent_date: str | None) -> bool:
    return schedule_matches(automation_config("pending_daily"), now) and (
        last_sent_date != now.date().isoformat()
    )


def reminder_scheduled_hour() -> int:
    return int(automation_config("pending_weekly_reminder")["hour"])


def should_send_reminder(now: datetime, last_sent_date: str | None) -> bool:
    return schedule_matches(automation_config("pending_weekly_reminder"), now) and (
        last_sent_date != now.date().isoformat()
    )


def due_promotoria_reports(state: dict) -> list[tuple[str, dict, datetime]]:
    sent = state.get("promotoria_reports", {})
    due: list[tuple[str, dict, datetime]] = []
    for automation_id in PROMOTORIA_AUTOMATION_IDS:
        config = automation_config(automation_id)
        now = local_now_for(automation_id)
        last_sent_date = (sent.get(automation_id) or {}).get("last_sent_date")
        if schedule_matches(config, now) and last_sent_date != now.date().isoformat():
            due.append((automation_id, config, now))
    return due


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
    reminder_now = local_now_for("pending_weekly_reminder")
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(".lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        due = force or should_send(now, state.get("last_sent_date"))
        reminder_due = force_reminder or should_send_reminder(
            reminder_now, state.get("last_reminder_sent_date")
        )
        promotoria_due = due_promotoria_reports(state)
        if dry_run:
            print(
                json.dumps(
                    {
                        "due": due,
                        "reminder_due": reminder_due,
                        "now": now.isoformat(),
                        "last_sent_date": state.get("last_sent_date"),
                        "recipients": configured_recipients(),
                        "reminder_recipients": configured_recipients(
                            "pending_weekly_reminder"
                        ),
                        "promotoria_reports_due": [
                            {
                                "id": automation_id,
                                "promotoria": config["promotoria"],
                                "recipients": configured_recipients(automation_id),
                            }
                            for automation_id, config, _ in promotoria_due
                        ],
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if not due and not reminder_due and not promotoria_due:
            return 0

        sender_username = automation_config("pending_daily")["sender"]
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
            write_state(path, new_state)
        if reminder_due:
            reminder_config = automation_config("pending_weekly_reminder")
            reminder_result = deliver_pending_reminder_report(
                configured_recipients("pending_weekly_reminder"),
                sender_username=reminder_config["sender"],
            )
            new_state.update({
                "last_reminder_sent_date": reminder_now.date().isoformat(),
                "last_reminder_sent_at": reminder_now.isoformat(),
                "reminder_recipients": reminder_result["recipients"],
                "reminder_count": reminder_result["count"],
                "reminder_window_end": reminder_result["window_end"],
            })
            print(
                f"Recordatorio de pendientes enviado a "
                f"{len(reminder_result['recipients'])} destinatarios el {reminder_now.isoformat()}"
            )
            write_state(path, new_state)
        for automation_id, config, promotoria_now in promotoria_due:
            promotoria_result = deliver_pending_report(
                configured_recipients(automation_id),
                sender_username=config["sender"],
                promotoria=config["promotoria"],
            )
            reports_state = dict(new_state.get("promotoria_reports", {}))
            reports_state[automation_id] = {
                "last_sent_date": promotoria_now.date().isoformat(),
                "last_sent_at": promotoria_now.isoformat(),
                "sender_username": config["sender"],
                "recipients": promotoria_result["recipients"],
                "generated_on": promotoria_result["generated_on"],
                "promotoria": config["promotoria"],
            }
            new_state["promotoria_reports"] = reports_state
            write_state(path, new_state)
            print(
                f"Informe de pendientes de {config['promotoria']} enviado a "
                f"{len(promotoria_result['recipients'])} destinatarios el "
                f"{promotoria_now.isoformat()}"
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
