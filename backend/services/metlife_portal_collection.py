"""Read portal evidence separately from the insurer's uploaded snapshot."""
from datetime import date, datetime, timezone

from database import SessionLocal, Policy, Renewal, PolicyDocumentRetrievalTask, PolicyDocumentRetrievalStep, AgentAction


def portal_date(value):
    if not value:
        return None
    try:
        parsed = date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
    # The collection worker uses this sentinel when the portal check fails.
    return None if parsed == date(2000, 1, 1) else parsed.isoformat()


def checked_timestamp(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def portal_collection_index():
    """Match policy AND renewal period; never reuse evidence from another term."""
    db = SessionLocal()
    try:
        indexed = {}
        for renewal, number in db.query(Renewal, Policy.policy_number).join(
            Policy, Renewal.original_policy_id == Policy.id
        ).filter(Policy.insurer_id == 'metlife', Policy.product_id == 'prod_met_gmm').all():
            indexed[(number.strip(), renewal.renewal_deadline.isoformat())] = {
                'paid_until': portal_date(renewal.paid_until), 'checked_at': None,
            }
        tasks = db.query(PolicyDocumentRetrievalTask).filter(
            PolicyDocumentRetrievalTask.insurer_id == 'metlife',
            PolicyDocumentRetrievalTask.product_branch == 'GMM',
        ).all()
        task_keys = {task.id: (task.policy_number.strip(), task.renewal_deadline.isoformat()) for task in tasks}
        for task in tasks:
            check = (task.normalized_payload or {}).get('collection_check')
            if check:
                merge_check(indexed, task_keys[task.id], check)
        # Service-token workers record the same evidence in the action history.
        for action in db.query(AgentAction).filter(
            AgentAction.action_type == 'renewal_collection_check',
            AgentAction.status == 'completed',
        ).all():
            payload = action.input_payload or {}
            key = task_keys.get(payload.get('task_id'))
            if key:
                merge_check(indexed, key, {**payload, 'status': 'completed'})
        # Older checks retained the payment date in Renewal but lost the task
        # timestamp on a workbook refresh. Recover only matching successful reads.
        missing = {key for key, value in indexed.items() if value['paid_until'] and not value['checked_at']}
        if missing:
            task_ids = [task_id for task_id, key in task_keys.items() if key in missing]
            steps = db.query(PolicyDocumentRetrievalStep).filter(
                PolicyDocumentRetrievalStep.task_id.in_(task_ids),
                PolicyDocumentRetrievalStep.step_name == 'collection_read_paid_until',
                PolicyDocumentRetrievalStep.status == 'completed',
            ).all()
            for step in steps:
                key = task_keys.get(step.task_id)
                if key not in missing:
                    continue
                value = indexed[key]
                if portal_date((step.metadata_json or {}).get('paid_until')) != value['paid_until']:
                    continue
                timestamp = checked_timestamp(step.completed_at)
                if timestamp and (not value['checked_at'] or timestamp > value['checked_at']):
                    value['checked_at'] = timestamp
        return indexed
    finally:
        db.close()


def merge_check(indexed, key, check):
    timestamp = checked_timestamp(check.get('checked_at'))
    current = indexed.get(key, {})
    if current.get('checked_at') and (not timestamp or timestamp < current['checked_at']):
        return
    indexed[key] = {
        'paid_until': portal_date(check.get('paid_until')) if check.get('status') == 'completed' else None,
        'checked_at': timestamp,
    }


def display_checked_timestamp(value):
    timestamp = checked_timestamp(value)
    return datetime.fromisoformat(timestamp).strftime('%Y-%m-%d %H:%M') if timestamp else None
