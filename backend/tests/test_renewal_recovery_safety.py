from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest
from jobs import run_renewal_agent as job


def test_connection_failure_before_first_step_trips_circuit_breaker():
    assert job.is_portal_failure({'error_message': 'BrowserType.connect_over_cdp: Timeout 30000ms exceeded', 'steps': []})


def test_failed_collection_preserves_verified_payment():
    task = SimpleNamespace(normalized_payload={'paid_until_date': '2026-11-01'}, policy_number='123', renewal_deadline=date(2026,11,1))
    db = MagicMock()
    db.get.return_value = task
    with patch.object(job, 'SessionLocal', return_value=db):
        assert job.persist_collection_check('test', paid_until=date(2000,1,1), succeeded=False, error='offline') is False
    assert task.normalized_payload['paid_until_date'] == '2026-11-01'
    assert task.normalized_payload['collection_check']['paid_until'] is None
    # Failed evidence must not query/create a renewal or replace its paid_until.
    assert db.query.call_count == 1


def test_delivery_intent_committed_before_smtp_and_blocks_retry(tmp_path):
    task = SimpleNamespace(id='test-recovery', policy_number='123', renewal_deadline=date(2026,11,1))
    db = MagicMock()
    db.__enter__.return_value = db
    db.query.return_value.join.return_value.filter.return_value.all.return_value = []
    actions = []
    db.query.return_value.filter.return_value.all.side_effect = lambda: actions
    events=[]
    def record(**kwargs):
        events.append('intent')
        actions.append(SimpleNamespace(input_payload={'task_id':task.id}))
    def smtp(**kwargs):
        events.append('smtp')
        raise RuntimeError('crash after sending')
    with patch.object(job,'REPOSITORY_ROOT',tmp_path), patch.object(job,'SessionLocal',return_value=db), patch.object(job,'record_action',side_effect=record), patch.object(job,'send_email_smtp',side_effect=smtp):
        with pytest.raises(RuntimeError, match='crash'):
            job.send_renewal_email_once(task=task, subject='test', recipients=[])
        with pytest.raises(job.SmtpDeliveryUncertainError):
            job.send_renewal_email_once(task=task, subject='test', recipients=[])
    assert events == ['intent','smtp']


def test_completed_old_portal_upload_prevents_browser_retry():
    result = SimpleNamespace(error_message='browser has been closed', steps=[
        SimpleNamespace(step_name='upload_to_client_folder',status='completed')])
    assert not job.is_browser_interruption(result)


def test_search_uses_first_visible_icon_when_portal_repeats_test_id():
    from adapters.metlife_gmm_portal import MetLifeGmmPortalAdapter
    adapter=MetLifeGmmPortalAdapter(username='test',password='test')
    page=MagicMock()
    hidden,main,secondary=MagicMock(),MagicMock(),MagicMock()
    hidden.is_visible.return_value=False
    main.is_visible.return_value=secondary.is_visible.return_value=True
    icons=page.get_by_test_id.return_value
    icons.count.return_value=3
    icons.nth.side_effect=[hidden,main,secondary]
    with patch.object(adapter,'close_residual_search_menu'),patch.object(adapter,'select_search_option'):
        adapter.search(page,'No. de Póliza','123')
    main.click.assert_called_once()
    hidden.click.assert_not_called()
    secondary.click.assert_not_called()


@pytest.mark.parametrize('paid_until, error, expected_delivery', [
    (date(2026,12,1), None, False),
    (date(2026,11,1), None, True),
    (None, 'connect_over_cdp: Timeout', False),
])
def test_reconciliation_precedes_delivery(paid_until,error,expected_delivery):
    from adapters.metlife_gmm_collection import MetLifeGmmCollectionResult
    task=SimpleNamespace(id='test',policy_number='123',client_name='Test',rfc='',
                         renewal_deadline=date(2026,11,1),original_policy_number='123')
    db=MagicMock(); db.__enter__.return_value=db
    db.get.side_effect=[task,SimpleNamespace(processed_count=0,succeeded_count=0)]
    result=MetLifeGmmCollectionResult(status='failed' if error else 'completed',task_id=task.id,
        policy_number='123',rfc='',paid_until=paid_until,steps=[],error_message=error)
    with patch.object(job,'SessionLocal',return_value=db),patch.object(job,'selected_tasks',return_value=[task]),patch.object(job,'check_metlife_gmm_collection',return_value=result),patch.object(job,'persist_collection_check'),patch.object(job,'persist_result'),patch.object(job,'persist_adapter_steps'),patch.object(job,'process_one',return_value=({'status':'completed'},False)) as delivery:
        item,failed=job.process_one_reconciled('run',task.id)
    assert delivery.called is expected_delivery
    assert failed is bool(error)


def test_shared_browser_operations_hold_exclusive_profile_lock(tmp_path):
    import fcntl
    from adapters.metlife_gmm_portal import chrome_operation_lock
    path=tmp_path / '.taiico-portal-operation.lock'
    with chrome_operation_lock(tmp_path):
        with path.open('a+') as other:
            with pytest.raises(BlockingIOError):
                fcntl.flock(other.fileno(),fcntl.LOCK_EX | fcntl.LOCK_NB)
    with path.open('a+') as other:
        fcntl.flock(other.fileno(),fcntl.LOCK_EX | fcntl.LOCK_NB)


def test_no_match_precheck_is_reused_without_repeating_new_portal_queries():
    from adapters.metlife_gmm_portal import MetLifeGmmPortalResult, AdapterStepResult
    from adapters.metlife_gmm_collection import MetLifeGmmCollectionResult
    task=SimpleNamespace(id='reuse',policy_number='123',client_name='Test',rfc='SABM7809274J4',
        renewal_deadline=date(2026,11,1),original_policy_number='123',attempt_count=1)
    old=MetLifeGmmPortalResult(status='failed',task_id=task.id,policy_number='123',rfc=task.rfc,
        steps=[AdapterStepResult(step_name='search_policy',status='failed',started_at='2026-11-15',error_message='produjo 0 coincidencias exactas de póliza')],
        error_message='produjo 0 coincidencias exactas de póliza')
    check=MetLifeGmmCollectionResult(status='failed',task_id=task.id,policy_number='123',rfc=task.rfc,paid_until=None,
        steps=[AdapterStepResult(step_name='search_policy',status='failed',started_at='2026-11-15',error_message='found 0 matches')],error_message='found 0 matches')
    with patch.object(job,'update_task_attempt',return_value=task),patch.object(job,'MetLifeGmmOldPortalAdapter') as old_adapter,patch.object(job,'MetLifeGmmPortalAdapter') as new_adapter,patch.object(job,'check_metlife_gmm_collection') as collector,patch.object(job,'persist_collection_check',return_value=False),patch.object(job,'persist_manual_review',return_value=True),patch.object(job,'persist_result'),patch.object(job,'record_action'),patch.object(job,'emit'):
        old_adapter.return_value.run.return_value=old
        result,outage=job.process_one('run',task.id,prechecked_collection=check)
    new_adapter.assert_not_called()
    collector.assert_not_called()
    assert not outage
    assert result['status']=='failed'
