from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services import metlife_portal_collection as service


def test_portal_evidence_is_scoped_to_policy_and_period():
    db = MagicMock()
    renewal = SimpleNamespace(paid_until=date(2026, 9, 1), renewal_deadline=date(2026, 10, 1))
    task = SimpleNamespace(id='task', policy_number='0001', renewal_deadline=date(2026, 10, 1),
                           normalized_payload={'collection_check': {
                               'status': 'completed', 'paid_until': '2026-10-01', 'checked_at': '2026-09-12T10:00:00'}})
    action = SimpleNamespace(input_payload={'task_id': 'task', 'paid_until': '2026-11-01', 'checked_at': '2026-09-14T10:00:00Z'})
    db.query.return_value.join.return_value.filter.return_value.all.return_value = [(renewal, '0001')]
    db.query.return_value.filter.return_value.all.side_effect = [[task], [action]]
    with patch.object(service, 'SessionLocal', return_value=db):
        result = service.portal_collection_index()
    assert result[('0001', '2026-10-01')] == {'paid_until': '2026-11-01', 'checked_at': '2026-09-14T10:00:00+00:00'}
    assert ('0001', '2027-10-01') not in result
    db.close.assert_called_once()


def test_failed_check_is_not_a_payment_date_and_older_evidence_does_not_override():
    index = {}
    service.merge_check(index, 'key', {'status': 'failed', 'paid_until': '2000-01-01', 'checked_at': '2026-09-14T10:00:00'})
    service.merge_check(index, 'key', {'status': 'completed', 'paid_until': '2026-10-01', 'checked_at': '2026-09-13T10:00:00'})
    assert index['key'] == {'paid_until': None, 'checked_at': '2026-09-14T10:00:00+00:00'}
    assert service.portal_date(date(2000, 1, 1)) is None
    assert service.portal_date(None) is None
    assert service.checked_timestamp(None) is None


def test_base_refresh_preserves_portal_check_separately():
    from services.renovaciones import upsert_retrieval_task
    check = {'status': 'completed', 'paid_until': '2026-10-01', 'checked_at': '2026-09-14T10:00:00'}
    existing = SimpleNamespace(rfc='', normalized_payload={'collection_check': check, 'paid_until_date': '2026-10-01'})
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = existing
    task, created = upsert_retrieval_task(db, {
        'insurer_id': 'metlife', 'product_branch': 'GMM', 'policy_number': '0001',
        'renewal_deadline': date(2026, 10, 1), 'rfc': '',
        'normalized_payload': {'paid_until_date': '2026-09-01'},
    })
    assert not created
    assert task.normalized_payload['paid_until_date'] == '2026-09-01'
    assert task.normalized_payload['collection_check'] == check


def test_recovers_latest_matching_successful_read_timestamp():
    from datetime import datetime
    db = MagicMock()
    renewal = SimpleNamespace(paid_until=date(2026, 9, 1), renewal_deadline=date(2026, 10, 1))
    task = SimpleNamespace(id='task', policy_number='0001', renewal_deadline=date(2026, 10, 1), normalized_payload={})
    steps = [SimpleNamespace(task_id='task', metadata_json={'paid_until': paid}, completed_at=datetime.fromisoformat(time))
             for paid, time in [('2026-09-01', '2026-08-29T10:15:59'),
                                ('2026-09-01', '2026-08-28T09:00:00'),
                                ('2026-10-01', '2026-08-30T11:00:00')]]
    db.query.return_value.join.return_value.filter.return_value.all.return_value = [(renewal, '0001')]
    db.query.return_value.filter.return_value.all.side_effect = [[task], [], steps]
    with patch.object(service, 'SessionLocal', return_value=db):
        result = service.portal_collection_index()
    assert result[('0001', '2026-10-01')] == {'paid_until': '2026-09-01', 'checked_at': '2026-08-29T10:15:59+00:00'}


def test_display_timestamp_uses_utc_minutes_and_preserves_empty_values():
    assert service.display_checked_timestamp('2026-09-03T05:41:55.339409+00:00') == '2026-09-03 05:41'
    assert service.display_checked_timestamp('2026-09-03T07:41:55+02:00') == '2026-09-03 05:41'
    assert service.display_checked_timestamp(None) is None
    assert service.display_checked_timestamp('') is None
