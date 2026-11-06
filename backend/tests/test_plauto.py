from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, Client, ClientPromotoria, User, PlautoAction, AuditLog
from services import plauto, plauto_drive
from services.auth import AccessProfile, PROMOTORIAS


def profile(username='admin@example.test', scope=('TAIICO',), permission='operacion'):
    return AccessProfile(username=username, role='admin', promotorias=scope, rfc='', aseguradoras=(), module_permissions={'clientes': permission})


@pytest.fixture
def db(monkeypatch):
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(plauto, 'SessionLocal', factory)
    monkeypatch.setenv('PLAUTO_ENABLED', 'true')
    with factory() as session:
        session.add(User(id='owner', name='Owner', email='owner@example.test', role='admin'))
        for id, name, scope in [('a', 'Ana Perez', 'TAIICO'), ('b', 'Beatriz Perez', 'EKILIBRA')]:
            session.add(Client(id=id, full_name=name, responsible_user_id='owner', status='active', email='old@example.test', promotorias=[ClientPromotoria(promotoria=scope)]))
        session.commit()
    yield factory
    engine.dispose()


def test_search_and_direct_id_do_not_cross_promotorias(db):
    result = plauto.search_clients('Perez', profile())
    assert [c['id'] for c in result['clients']] == ['a']
    with pytest.raises(HTTPException) as denied:
        plauto.client_overview('b', profile())
    assert denied.value.status_code == 404
    assert len(plauto.search_clients('Perez', profile(scope=PROMOTORIAS))['clients']) == 2


def test_module_permission_is_required_even_for_central_admin(db):
    with pytest.raises(HTTPException) as denied:
        plauto.search_clients('Perez', profile(scope=PROMOTORIAS, permission='ninguno'))
    assert denied.value.status_code == 403


def test_wildcards_are_literal_not_a_directory_dump(db):
    assert plauto.search_clients('%%', profile())['clients'] == []


def test_proposal_does_not_write_until_confirmed_and_cannot_repeat(db):
    action = plauto.propose_contact('a', 'new@example.test', None, profile())['proposal']
    with db() as session:
        assert session.get(Client, 'a').email == 'old@example.test'
    background = BackgroundTasks()
    assert plauto.confirm_action(action['id'], plauto.ConfirmRequest(confirm=True), background, profile())['status'] == 'completed'
    assert plauto.confirm_action(action['id'], plauto.ConfirmRequest(confirm=True), background, profile())['status'] == 'completed'
    with db() as session:
        assert session.get(Client, 'a').email == 'new@example.test'
        assert session.query(AuditLog).count() == 1
    assert len(background.tasks) == 1


def test_proposals_are_user_owned_and_permissions_rechecked(db):
    action = plauto.propose_contact('a', 'new@example.test', None, profile())['proposal']
    for user, code in [(profile(username='other@example.test'), 404), (profile(permission='lectura'), 403), (profile(scope=('EKILIBRA',)), 404)]:
        with pytest.raises(HTTPException) as denied:
            plauto.confirm_action(action['id'], plauto.ConfirmRequest(confirm=True), BackgroundTasks(), user)
        assert denied.value.status_code == code


def test_stale_proposal_does_not_overwrite_newer_data(db):
    action = plauto.propose_contact('a', 'new@example.test', None, profile())['proposal']
    with db() as session:
        session.get(Client, 'a').email = 'changed@example.test'
        session.commit()
    with pytest.raises(HTTPException) as denied:
        plauto.confirm_action(action['id'], plauto.ConfirmRequest(confirm=True), BackgroundTasks(), profile())
    assert denied.value.status_code == 409
    with db() as session:
        assert session.get(Client, 'a').email == 'changed@example.test'
        assert session.get(PlautoAction, action['id']).status == 'pending'


def test_expiration_and_cancel_never_change_contact(db):
    action = plauto.propose_contact('a', 'new@example.test', None, profile())['proposal']
    with db() as session:
        session.get(PlautoAction, action['id']).expires_at = datetime.utcnow() - timedelta(seconds=1)
        session.commit()
    with pytest.raises(HTTPException):
        plauto.confirm_action(action['id'], plauto.ConfirmRequest(confirm=True), BackgroundTasks(), profile())
    other = plauto.propose_contact('a', None, '5551234567', profile())['proposal']
    assert plauto.confirm_action(other['id'], plauto.ConfirmRequest(confirm=False), BackgroundTasks(), profile())['status'] == 'cancelled'
    with db() as session:
        assert session.get(Client, 'a').phone is None


def test_read_only_users_cannot_propose(db):
    with pytest.raises(HTTPException):
        plauto.propose_contact('a', 'new@example.test', None, profile(permission='lectura'))


def test_unknown_tools_cannot_invoke_arbitrary_code(db):
    with pytest.raises(HTTPException):
        plauto.execute_tool('delete_client', {'client_id': 'a'}, profile())


def test_drive_never_reads_file_outside_authorized_inventory():
    with patch.object(plauto_drive, 'drive_session') as session, patch.object(plauto_drive, 'inventory', return_value=([{'id': 'allowed'}], False)):
        with pytest.raises(HTTPException) as denied:
            plauto_drive.read_document(SimpleNamespace(), 'other-client-file')
        assert denied.value.status_code == 404
        session.return_value.__enter__.return_value.get.assert_not_called()


def test_duplicate_rfc_folders_fail_closed(monkeypatch):
    monkeypatch.setenv('PLAUTO_LEGACY_DRIVE_ROOT_ID', 'legacy')
    client = SimpleNamespace(rfc='AAMA950203I52', drive_folder_id=None)
    with patch.object(plauto_drive, 'get_json', return_value={'files': [{'id': '1', 'name': 'AAMA950203I52 - A'}, {'id': '2', 'name': 'AAMA950203I52 - B'}]}):
        assert plauto_drive.client_folders(None, client) == []


def test_missing_key_is_explicit_but_search_works(db, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    user = profile(username='search@example.test')
    result = plauto.chat(plauto.ChatRequest(message='Ana', search_only=True), user)
    assert result['mode'] == 'search' and result['clients']
    with pytest.raises(HTTPException) as missing:
        plauto.chat(plauto.ChatRequest(message='Hola'), user)
    assert missing.value.status_code == 503


def test_stateless_model_only_receives_user_questions_and_verified_tool_output(db, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    monkeypatch.setenv('PLAUTO_MODEL', 'test-model')
    first = MagicMock(); first.json.return_value = {'output': [{'type': 'function_call', 'name': 'search_clients', 'call_id': '1', 'arguments': '{"query":"Perez"}'}]}
    second = MagicMock(); second.json.return_value = {'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': 'Encontré a Ana.'}]}]}
    calls = []
    def post(*args, **kwargs):
        import copy
        calls.append(copy.deepcopy(kwargs['json']))
        return first if len(calls) == 1 else second
    with patch.object(plauto.httpx, 'Client') as http:
        http.return_value.__enter__.return_value.post.side_effect = post
        answer = plauto.model_answer(plauto.ChatRequest(message='Busca Perez'), profile(permission='lectura'))
    assert calls[0]['store'] is False
    assert all(t['name'] != 'propose_contact' for t in calls[0]['tools'])
    assert 'Beatriz' not in calls[1]['input'][-1]['output']
    assert answer['sources'][0]['title'] == 'Ana Perez'
    assert answer['answer'] == 'Encontré a Ana.'


def test_endpoint_requires_real_session(db):
    app = FastAPI(); app.include_router(plauto.router)
    with TestClient(app) as client:
        assert client.get('/plauto/status').status_code == 401
        assert client.post('/plauto/chat', json={'message': 'Ana'}).status_code == 401


def test_legacy_search_requires_central_admin(db):
    with patch.object(plauto_drive, 'search_legacy_folders', return_value={'folders': []}) as search:
        with pytest.raises(HTTPException) as denied:
            plauto.execute_tool('search_legacy_folders', {'query': 'Ana'}, profile())
        assert denied.value.status_code == 403
        search.assert_not_called()
        plauto.execute_tool('search_legacy_folders', {'query': 'Ana'}, profile(scope=PROMOTORIAS))
        search.assert_called_once_with('Ana')


def test_legacy_ancestry_rejects_shortcut_and_wrong_root(monkeypatch):
    monkeypatch.setenv('PLAUTO_LEGACY_DRIVE_ROOT_ID', 'approved')
    with patch.object(plauto_drive, 'get_json', return_value={'mimeType': 'application/vnd.google-apps.shortcut', 'parents': ['approved']}):
        assert not plauto_drive.under_legacy_root(None, 'shortcut')
    with patch.object(plauto_drive, 'get_json', return_value={'mimeType': plauto_drive.FOLDER, 'parents': []}):
        assert not plauto_drive.under_legacy_root(None, 'other')
    with patch.object(plauto_drive, 'get_json', side_effect=[{'mimeType': plauto_drive.FOLDER, 'parents': ['agent']}, {'mimeType': plauto_drive.FOLDER, 'parents': ['approved']}]):
        assert plauto_drive.under_legacy_root(None, 'client')


def test_document_endpoint_rechecks_client_scope(db):
    with patch.object(plauto_drive, 'search_documents', return_value={'documents': [], 'partial': True}) as search:
        with pytest.raises(HTTPException) as denied:
            plauto.documents('b', profile())
        assert denied.value.status_code == 404
        search.assert_not_called()
        assert 'parcial' in plauto.documents('a', profile())['answer']


def test_drive_inventory_marks_truncated_and_ignores_shortcuts():
    with patch.object(plauto_drive, 'get_json', return_value={'nextPageToken': 'more', 'files': [{'id': 'link', 'name': 'secret', 'mimeType': 'application/vnd.google-apps.shortcut'}, {'id': 'pdf', 'name': 'Policy.pdf', 'mimeType': 'application/pdf'}]}):
        files, partial = plauto_drive.folder_inventory(None, [('Drive nuevo', 'root')])
        assert partial and [f['id'] for f in files] == ['pdf']


def test_chat_audit_omits_conversation():
    import asyncio
    from starlette.requests import Request
    from services import audit_logs
    payload = b'{"message":"private dossier details","previous_questions":["sensitive"],"search_only":true}'
    async def receive():
        return {'type': 'http.request', 'body': payload, 'more_body': False}
    request = Request({'type': 'http', 'method': 'POST', 'path': '/plauto/chat', 'headers': [(b'cookie', (audit_logs.COOKIE_NAME + '=token').encode()), (b'content-type', b'application/json')]}, receive)
    with patch.object(audit_logs, 'read_session_token', return_value='admin'):
        username, logged = asyncio.run(audit_logs.capture_request(request))
    assert username == 'admin' and logged == {'search_only': True, 'message_length': 23}


def test_overview_respects_module_permissions_and_agent_policy_scope(db):
    from datetime import date
    from database import Policy, Renewal
    with db() as session:
        for key in ['p1', 'p2']:
            session.add(Policy(id=key, policy_number=key, client_id='a', insurer_id='carrier', product_id='product', effective_start_date=date(2026,1,1), effective_end_date=date(2027,1,1), premium_amount=100, payment_frequency='annual', responsible_user_id='owner'))
            session.add(Renewal(id='r'+key, original_policy_id=key, client_id='a', renewal_deadline=date(2027,1,1)))
        session.commit()
    assert plauto.client_overview('a', profile())['policies'] == []
    agent = AccessProfile(username='agent', role='agente', promotorias=('TAIICO',), rfc='agent', aseguradoras=('METLIFE',), module_permissions={'clientes':'lectura','cartera':'lectura','renovaciones':'lectura'})
    with patch.object(plauto, 'profile_policy_numbers', return_value=frozenset({'p1'})), patch('services.client_promotorias.profile_policy_numbers', return_value=frozenset({'p1'})):
        result = plauto.client_overview('a', agent)
        assert [p['numero'] for p in result['policies']] == ['p1']
        assert [r['poliza'] for r in result['renewals']] == ['p1']
        with pytest.raises(HTTPException) as denied:
            plauto.execute_tool('search_documents', {'client_id':'a','query':''}, agent)
        assert denied.value.status_code == 403


def test_legacy_file_cannot_escape_validated_folder():
    session = MagicMock()
    with patch.object(plauto_drive, 'drive_session') as session_context, patch.object(plauto_drive, 'under_legacy_root', return_value=True), patch.object(plauto_drive, 'folder_inventory', return_value=([], False)), patch.object(plauto_drive, 'read_file') as read:
        session_context.return_value.__enter__.return_value = session
        with pytest.raises(HTTPException) as denied:
            plauto_drive.read_legacy_document('allowed-folder', 'unrelated-file')
        assert denied.value.status_code == 404
        read.assert_not_called()
