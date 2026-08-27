from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.exc import OperationalError


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env", override=True)

from adapters.metlife_gmm_collection import (  # noqa: E402
    COLLECTION_FAILURE_DATE,
    check_metlife_gmm_collection,
    collection_result_to_dict,
)
from adapters.metlife_gmm_portal import MetLifeGmmPortalTask  # noqa: E402
from database import (  # noqa: E402
    PolicyDocumentRetrievalStep,
    PolicyDocumentRetrievalTask,
    SessionLocal,
)
from jobs.run_renewal_agent import persist_collection_check  # noqa: E402
from services.renovaciones import persist_adapter_steps  # noqa: E402


def emit(event: str, **payload) -> None:
    print(json.dumps({"event": event, **payload}, ensure_ascii=False), flush=True)


def failed_tasks_for_run(
    run_id: str,
    policies: set[str] | None = None,
) -> list[PolicyDocumentRetrievalTask]:
    db = SessionLocal()
    try:
        tasks = (
            db.query(PolicyDocumentRetrievalTask)
            .join(
                PolicyDocumentRetrievalStep,
                PolicyDocumentRetrievalStep.task_id
                == PolicyDocumentRetrievalTask.id,
            )
            .filter(
                PolicyDocumentRetrievalStep.run_id == run_id,
                PolicyDocumentRetrievalStep.status == "failed",
            )
            .order_by(PolicyDocumentRetrievalStep.started_at.asc())
            .all()
        )
        unique = []
        seen = set()
        for task in tasks:
            if task.id in seen:
                continue
            if policies and str(task.policy_number) not in policies:
                continue
            seen.add(task.id)
            db.expunge(task)
            unique.append(task)
        return unique
    finally:
        db.close()


def persist_steps(run_id: str, task_id: str, steps: list[dict]) -> None:
    for attempt in range(6):
        db = SessionLocal()
        try:
            persist_adapter_steps(db, run_id, task_id, steps)
            db.commit()
            return
        except OperationalError as exc:
            db.rollback()
            if "database is locked" not in str(exc).lower() or attempt == 5:
                raise
            time.sleep(attempt + 1)
        finally:
            db.close()


def persist_collection_with_retry(task_id: str, **kwargs) -> bool:
    for attempt in range(6):
        try:
            return persist_collection_check(task_id, **kwargs)
        except OperationalError as exc:
            if "database is locked" not in str(exc).lower() or attempt == 5:
                raise
            time.sleep(attempt + 1)
    return False


def run(run_id: str, policies: set[str] | None = None) -> int:
    tasks = failed_tasks_for_run(run_id, policies)
    emit("collection_batch_started", run_id=run_id, selected=len(tasks))
    completed = 0
    failed = 0
    manual_review = 0
    for index, task in enumerate(tasks, start=1):
        emit(
            "collection_task_started",
            index=index,
            total=len(tasks),
            policy=task.policy_number,
            rfc=task.rfc,
            client=task.client_name,
        )
        result = check_metlife_gmm_collection(
            MetLifeGmmPortalTask(
                id=task.id,
                policy_number=task.policy_number,
                original_policy_number=task.original_policy_number,
                rfc=task.rfc or "",
                client_name=task.client_name,
                renewal_deadline=task.renewal_deadline,
            ),
            headless=False,
        )
        result_data = collection_result_to_dict(result)
        error_lower = str(result.error_message or "").lower()
        if "mfa_required" in error_lower or "operator_action_required" in error_lower:
            emit(
                "collection_batch_paused",
                run_id=run_id,
                policy=task.policy_number,
                reason=result.error_message,
            )
            return 2
        persist_steps(run_id, task.id, result_data["steps"])
        paid_until = result.paid_until or COLLECTION_FAILURE_DATE
        assigned = persist_collection_with_retry(
            task.id,
            paid_until=paid_until,
            succeeded=result.status == "completed",
            error=result.error_message,
        )
        if result.status == "completed":
            completed += 1
        else:
            failed += 1
        if assigned:
            manual_review += 1
        emit(
            "collection_task_finished",
            index=index,
            total=len(tasks),
            policy=task.policy_number,
            status=result.status,
            paid_until=paid_until.strftime("%d/%m/%Y"),
            manual_review=assigned,
            error=result.error_message,
        )
    emit(
        "collection_batch_finished",
        run_id=run_id,
        selected=len(tasks),
        completed=completed,
        failed=failed,
        manual_review=manual_review,
    )
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--policy",
        action="append",
        default=[],
        help="Process only this policy from the failed run; may be repeated.",
    )
    arguments = parser.parse_args()
    return run(arguments.run_id, set(arguments.policy) or None)


if __name__ == "__main__":
    raise SystemExit(main())
