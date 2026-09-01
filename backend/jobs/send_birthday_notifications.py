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
load_dotenv(BACKEND_DIR / ".env", override=True)

from services.birthday_notifications import (  # noqa: E402
    birthday_email_html,
    birthday_email_subject,
    birthday_email_text,
    build_agent_birthday_notifications,
)
from services.automatic_mails import (  # noqa: E402
    automation_config,
    local_now_for,
    schedule_matches,
)
from services.cumpleanos import load_birthday_directory  # noqa: E402
from services.mail_configuration import smtp_settings_for  # noqa: E402
from services.renovaciones import send_email_smtp  # noqa: E402


DEFAULT_TIMEZONE = "America/Mexico_City"
DEFAULT_HOUR = 11
DEFAULT_SENDER_USERNAME = "alberto.alfaro@taiico.com"
DEFAULT_WINDOW_DAYS = 7


def local_now() -> datetime:
    return local_now_for("client_birthdays")


def scheduled_hour() -> int:
    return int(automation_config("client_birthdays")["hour"])


def should_send(now: datetime, last_completed_date: str | None) -> bool:
    return schedule_matches(automation_config("client_birthdays"), now) and (
        last_completed_date != now.date().isoformat()
    )


def state_path() -> Path:
    configured = os.getenv("BIRTHDAY_AUTOMATION_STATE_FILE", "").strip()
    return (
        Path(configured).expanduser()
        if configured
        else REPOSITORY_ROOT / ".runtime" / "birthday-notifications-state.json"
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


def _matching_notifications(report: dict, agent_rfc: str | None) -> list[dict]:
    notifications = report["notifications"]
    if not agent_rfc:
        return notifications
    normalized = agent_rfc.strip().upper()
    return [
        item
        for item in notifications
        if item.get("agent_rfc", "").strip().upper() == normalized
    ]


def run(
    *,
    force: bool = False,
    dry_run: bool = False,
    agent_rfc: str | None = None,
    test_recipient: str | None = None,
    preview_file: str | None = None,
) -> int:
    if test_recipient and not agent_rfc:
        raise RuntimeError("El envío de prueba requiere --agent-rfc")
    now = local_now()
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(".lock")
    with lock_path.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        controlled_test = bool(agent_rfc or test_recipient or preview_file)
        due = force or controlled_test or should_send(now, state.get("last_completed_date"))
        if not due:
            return 0

        directory = load_birthday_directory()
        report = build_agent_birthday_notifications(
            directory,
            window_days=int(
                os.getenv("BIRTHDAY_AUTOMATION_WINDOW_DAYS", str(DEFAULT_WINDOW_DAYS))
            ),
        )
        notifications = _matching_notifications(report, agent_rfc)
        if agent_rfc and not notifications:
            raise RuntimeError(
                f"No hay cumpleaños próximos con correo para el agente {agent_rfc}"
            )

        if preview_file:
            if len(notifications) != 1:
                raise RuntimeError("La vista previa requiere seleccionar exactamente un agente")
            preview_path = Path(preview_file).expanduser()
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            preview_path.write_text(birthday_email_html(notifications[0]))

        summary = {
            "due": due,
            "now": now.isoformat(),
            "sender_username": automation_config("client_birthdays")["sender"],
            "agents_with_email": len(notifications),
            "birthdays": sum(len(item["clients"]) for item in notifications),
            "agents_missing_email": len(report["missing_email"]),
            "test_recipient": test_recipient,
            "preview_file": preview_file,
        }
        if dry_run:
            print(json.dumps(summary, ensure_ascii=False))
            return 0

        sender_username = summary["sender_username"]
        settings = smtp_settings_for(sender_username)
        sent_keys = set(
            state.get("sent_agent_keys", [])
            if state.get("processing_date") == now.date().isoformat()
            else []
        )
        if not controlled_test:
            state = {
                "processing_date": now.date().isoformat(),
                "sent_agent_keys": sorted(sent_keys),
            }
            write_state(path, state)

        sent_count = 0
        for notification in notifications:
            agent_key = notification.get("agent_rfc") or notification["agent_label"]
            if not controlled_test and agent_key in sent_keys:
                continue
            recipient = test_recipient or notification["agent_email"]
            send_email_smtp(
                subject=birthday_email_subject(
                    notification,
                    test=bool(test_recipient),
                ),
                body=birthday_email_text(notification),
                html_body=birthday_email_html(notification),
                recipients=[recipient],
                cc_recipients=[],
                settings=settings,
            )
            sent_count += 1
            if not controlled_test:
                sent_keys.add(agent_key)
                state["sent_agent_keys"] = sorted(sent_keys)
                write_state(path, state)

        if not controlled_test:
            state.update(
                {
                    "last_completed_date": now.date().isoformat(),
                    "last_completed_at": now.isoformat(),
                    "sender_username": sender_username,
                    "sent_count": len(sent_keys),
                    "agents_missing_email": len(report["missing_email"]),
                }
            )
            write_state(path, state)
        summary["sent_count"] = sent_count
        print(json.dumps(summary, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--agent-rfc")
    parser.add_argument("--test-recipient")
    parser.add_argument("--preview-file")
    arguments = parser.parse_args()
    return run(
        force=arguments.force,
        dry_run=arguments.dry_run,
        agent_rfc=arguments.agent_rfc,
        test_recipient=arguments.test_recipient,
        preview_file=arguments.preview_file,
    )


if __name__ == "__main__":
    raise SystemExit(main())
