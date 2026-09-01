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

from jobs.send_pending_report import (  # noqa: E402
    DEFAULT_SENDER_USERNAME,
    configured_recipients,
)
from services.automatic_mails import (  # noqa: E402
    automation_config,
    local_now_for,
    schedule_matches,
    schedule_period_key,
)
from services.agent_license_notifications import (  # noqa: E402
    deliver_agent_license_expiration_report,
)


DEFAULT_TIMEZONE = "America/Mexico_City"
DEFAULT_HOUR = 10
DEFAULT_MONTHS_AHEAD = 3


def local_now() -> datetime:
    return local_now_for("agent_license_expiration")


def scheduled_hour() -> int:
    return int(automation_config("agent_license_expiration")["hour"])


def should_send(now: datetime, last_sent_period: str | None) -> bool:
    config = automation_config("agent_license_expiration")
    return schedule_matches(config, now) and (
        last_sent_period != schedule_period_key(config, now)
    )


def state_path() -> Path:
    configured = os.getenv("AGENT_LICENSE_AUTOMATION_STATE_FILE", "").strip()
    return (
        Path(configured).expanduser()
        if configured
        else REPOSITORY_ROOT / ".runtime" / "agent-license-report-state.json"
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


def run(*, force: bool = False, dry_run: bool = False) -> int:
    now = local_now()
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state = read_state(path)
        automation = automation_config("agent_license_expiration")
        last_sent_period = state.get("last_sent_period") or state.get("last_sent_month")
        due = force or should_send(now, last_sent_period)
        summary = {
            "due": due,
            "now": now.isoformat(),
            "last_sent_month": state.get("last_sent_month"),
            "recipients": configured_recipients("agent_license_expiration"),
        }
        if dry_run:
            print(json.dumps(summary, ensure_ascii=False))
            return 0
        if not due:
            return 0

        sender_username = automation["sender"]
        result = deliver_agent_license_expiration_report(
            configured_recipients("agent_license_expiration"),
            sender_username=sender_username,
            generated_on=now.date(),
            months_ahead=int(
                os.getenv(
                    "AGENT_LICENSE_AUTOMATION_MONTHS_AHEAD",
                    str(DEFAULT_MONTHS_AHEAD),
                )
            ),
        )
        write_state(
            path,
            {
                "last_sent_month": now.strftime("%Y-%m"),
                "last_sent_period": schedule_period_key(automation, now),
                "last_sent_at": now.isoformat(),
                "sender_username": sender_username,
                "recipients": result["recipients"],
                "generated_on": result["generated_on"],
                "window_end": result["window_end"],
                "agent_count": result["count"],
            },
        )
        print(
            f"Informe mensual de cédulas enviado a {len(result['recipients'])} "
            f"destinatarios con {result['count']} agentes el {now.isoformat()}"
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
