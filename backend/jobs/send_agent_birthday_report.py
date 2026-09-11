from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env", override=True)

from services.agent_birthday_reports import (  # noqa: E402
    DEFAULT_WINDOW_DAYS,
    deliver_agent_birthday_report,
)
from services.automatic_mails import (  # noqa: E402
    automation_config,
    local_now_for,
    normalize_emails,
    schedule_matches,
    schedule_period_key,
)
from services.cumpleanos_agentes import load_agent_birthday_directory  # noqa: E402


AUTOMATION_IDS = (
    "agent_birthdays_weekly",
    "agent_birthdays_promotoria_abbondanza",
    "agent_birthdays_promotoria_ekilibra",
    "agent_birthdays_promotoria_fenix_prevision",
)


def state_path() -> Path:
    configured = os.getenv("AGENT_BIRTHDAY_AUTOMATION_STATE_FILE", "").strip()
    return (
        Path(configured).expanduser()
        if configured
        else REPOSITORY_ROOT / ".runtime" / "agent-birthday-report-state.json"
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


def due_reports(state: dict, *, force: bool = False) -> list[tuple[str, dict, object, str]]:
    completed = state.get("reports", {})
    due = []
    for automation_id in AUTOMATION_IDS:
        config = automation_config(automation_id)
        now = local_now_for(automation_id)
        period_key = schedule_period_key(config, now)
        last_period_key = (completed.get(automation_id) or {}).get("period_key")
        if force or (schedule_matches(config, now) and last_period_key != period_key):
            due.append((automation_id, config, now, period_key))
    return due


def run(*, force: bool = False, dry_run: bool = False) -> int:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        due = due_reports(state, force=force)
        if dry_run:
            print(json.dumps({
                "due": [
                    {
                        "id": automation_id,
                        "promotoria": config.get("promotoria"),
                        "recipients": normalize_emails(config["recipients"]),
                        "now": now.isoformat(),
                        "period_key": period_key,
                    }
                    for automation_id, config, now, period_key in due
                ]
            }, ensure_ascii=False))
            return 0
        if not due:
            return 0

        directory = load_agent_birthday_directory()
        new_state = dict(state)
        reports_state = dict(new_state.get("reports", {}))
        window_days = int(
            os.getenv("AGENT_BIRTHDAY_AUTOMATION_WINDOW_DAYS", str(DEFAULT_WINDOW_DAYS))
        )
        for automation_id, config, now, period_key in due:
            result = deliver_agent_birthday_report(
                directory,
                normalize_emails(config["recipients"]),
                sender_username=config["sender"],
                promotoria=config.get("promotoria"),
                window_days=window_days,
            )
            reports_state[automation_id] = {
                "period_key": period_key,
                "last_sent_at": now.isoformat(),
                "sender_username": config["sender"],
                "recipients": result["recipients"],
                "generated_on": result["generated_on"],
                "count": result["count"],
                "promotoria": result["promotoria"],
            }
            new_state["reports"] = reports_state
            write_state(path, new_state)
            scope = f" de {result['promotoria']}" if result["promotoria"] else ""
            print(
                f"Cumpleaños de agentes{scope} "
                f"enviado a {len(result['recipients'])} destinatarios el {now.isoformat()}"
            )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args()
    return run(force=arguments.force, dry_run=arguments.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
