from __future__ import annotations

import argparse
import fcntl
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / '.env')

from services.automatic_mails import automation_config, local_now_for, schedule_matches, schedule_period_key
from services.renewal_portfolio_report import load_report, report_html, report_csv, deliver_report
from jobs.send_pending_report import read_state, write_state

AUTOMATION_ID = 'renewal_portfolio_weekly'


def run(*, dry_run: bool = False) -> int:
    config = automation_config(AUTOMATION_ID)
    now = local_now_for(AUTOMATION_ID)
    period = schedule_period_key(config, now)
    folder = REPOSITORY_ROOT / '.runtime' / 'renewal-portfolio-reports'
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'state.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        state_file = folder / 'state.json'
        state = read_state(state_file)
        due = schedule_matches(config, now) and period not in state
        if not due and not dry_run:
            return 0
        report = load_report(now.date())
        if dry_run:
            (folder / 'preview.html').write_text(report_html(report))
            print(json.dumps({'due': due, 'now': now.isoformat(), 'recipients': config['recipients'], 'counts': report['counts'], 'count': report['count']}, ensure_ascii=False))
            return 0
        # Persist the exact report and claim the period before SMTP. An ambiguous
        # delivery is reviewed manually, never automatically sent a second time.
        (folder / f'{period}.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        (folder / f'{period}.html').write_text(report_html(report))
        (folder / f'{period}.csv').write_bytes(report_csv(report))
        state[period] = {'status': 'sending', 'started_at': now.isoformat(), 'recipients': config['recipients'], 'counts': report['counts']}
        write_state(state_file, state)
        try:
            deliver_report(report, config)
        except Exception as exc:
            state[period].update(status='delivery_uncertain', error=str(exc))
            write_state(state_file, state)
            raise
        state[period].update(status='sent', sent_at=local_now_for(AUTOMATION_ID).isoformat())
        write_state(state_file, state)
        print(f"Informe de renovaciones enviado: {report['count']} pólizas, periodo {period}")
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    raise SystemExit(run(dry_run=args.dry_run))
