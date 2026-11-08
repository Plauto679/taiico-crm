"""Real HTTP workflow with isolated storage and fake Drive (no external actions)."""
import io
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import MesaCase
from services import mesa_control as mesa
from services.auth import AccessProfile
from services.authorization import current_access_profile


def profile(role='agente', rfc='AGENTE1', scope=('TAIICO',), permission='operacion', username=None):
    return AccessProfile(username=username or rfc, role=role, rfc=rfc, promotorias=scope,
                         aseguradoras=('METLIFE',), module_permissions={'pendientes': permission})


@pytest.fixture
def app(monkeypatch):
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    MesaCase.__table__.create(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(mesa, 'SessionLocal', factory)
    monkeypatch.setattr(mesa, 'mesa_available', lambda p: True)
    monkeypatch.setattr(mesa.pendientes, 'resolve_agent_scope', lambda p: SimpleNamespace(keys=('key1',)))
    monkeypatch.setattr(mesa.pendientes, '_agent_options_for_profile', lambda p, service=None: [
        {'rfc': 'AGENTE1', 'name': 'Agente Uno', 'promotoria': 'TAIICO'},
        *([] if p.is_agent else [{'rfc': 'AGENTE2', 'name': 'Agente Dos', 'promotoria': 'TAIICO'}])])
    monkeypatch.setenv('PLAUTO_ENABLED', 'false')
    api = FastAPI()
    api.include_router(mesa.router)
    api.dependency_overrides[current_access_profile] = lambda: profile()
    yield api, TestClient(api), factory
    engine.dispose()


def create(client, **overrides):
    body = {'request_id': str(uuid4()), 'agent_rfc': 'AGENTE1', 'promotoria': 'TAIICO',
            'data': {'client_name': 'Cliente de Prueba', 'rfc': 'AAAA901001AB1', 'product': 'Producto de prueba'}}
    body.update(overrides)
    response = client.post('/mesa-control/cases', json=body)
    return response, body


def call(client, item, action, **kwargs):
    return client.post(f"/mesa-control/cases/{item['id']}/transition", json={
        'revision': item['revision'], 'action': action, **kwargs})


def complete(factory, item):
    with factory() as db:
        case = db.get(MesaCase, item['id'])
        case.documents = [{'id': str(uuid4()), 'kind': k, 'drive_id': 'private', 'name': k,
                           'sha256': 'hash', 'at': '2026-11-09T10:00:00Z'} for k in mesa.requirements(case)]
        db.commit()


def test_create_retry_and_scope(app):
    api, client, factory = app
    response, body = create(client)
    assert response.status_code == 200, response.text
    item = response.json()
    assert client.post('/mesa-control/cases', json=body).json()['id'] == item['id']
    with factory() as db:
        assert db.query(MesaCase).count() == 1
    api.dependency_overrides[current_access_profile] = lambda: profile(rfc='AGENTE2')
    assert client.get('/mesa-control/cases').json()['cases'] == []
    for path in ['', '/documents/random']:
        assert client.get(f"/mesa-control/cases/{item['id']}{path}").status_code == 404
    assert client.post(f"/mesa-control/cases/{item['id']}/guide", json={'message': 'Dame los datos'}).status_code == 404
    assert client.post('/mesa-control/cases', json=body).status_code == 409
    api.dependency_overrides[current_access_profile] = lambda: profile(role='admin', scope=('EKILIBRA',))
    assert client.get('/mesa-control/cases').json()['cases'] == []


def test_read_only_and_unknown_roles_fail_closed(app):
    api, client, _ = app
    response, _ = create(client)
    item = response.json()
    api.dependency_overrides[current_access_profile] = lambda: profile(permission='lectura')
    assert client.get('/mesa-control/cases').status_code == 200
    assert call(client, item, 'submit').status_code == 403
    assert create(client)[0].status_code == 403
    api.dependency_overrides[current_access_profile] = lambda: profile(role='auxiliar')
    assert client.get('/mesa-control/cases').status_code == 403


def test_required_human_review_and_revision_conflicts(app):
    api, client, factory = app
    item = create(client)[0].json()
    assert call(client, item, 'submit').status_code == 422
    assert call(client, item, 'validate', comment='sí').status_code == 403
    complete(factory, item)
    item = call(client, item, 'submit').json()
    assert item['status'] == 'submitted'
    assert all('drive_id' not in d for d in item['documents'])
    assert call(client, item, 'claim').status_code == 403
    api.dependency_overrides[current_access_profile] = lambda: profile(role='admin', username='reviewer')
    assert call(client, item, 'validate', comment='Revisado').status_code == 409
    item = call(client, item, 'claim').json()
    assert item['status'] == 'reviewing'
    api.dependency_overrides[current_access_profile] = lambda: profile(role='admin', username='other')
    assert call(client, item, 'validate', comment='Revisado').status_code == 409
    api.dependency_overrides[current_access_profile] = lambda: profile(role='admin', username='reviewer')
    assert call(client, item, 'correct', comment='Incompleto').status_code == 422
    item = call(client, item, 'correct', reason='firma', target='Solicitud', comment='Falta firma del contratante').json()
    assert item['status'] == 'correction'
    assert item['history'][-1]['target'] == 'Solicitud'
    item = call(client, item, 'submit').json()
    item = call(client, item, 'claim').json()
    previous = item
    item = call(client, item, 'validate', comment='Firma y contenido revisados').json()
    assert item['status'] == 'validated'
    assert item['history'][-1]['reviewed_revision'] == previous['revision']
    api.dependency_overrides[current_access_profile] = lambda: profile()
    assert client.patch(f"/mesa-control/cases/{item['id']}", json={'revision': previous['revision'], 'data': item['data']}).status_code == 409
    updated = {**item['data'], 'product': 'Otro producto'}
    response = client.patch(f"/mesa-control/cases/{item['id']}", json={'revision': item['revision'], 'data': updated})
    assert response.status_code == 200
    assert response.json()['status'] == 'draft'
    assert response.json()['history'][-1]['before']['product'] != updated['product']


def test_conditional_requirements_and_guide(app):
    _, client, _ = app
    item = create(client, data={'client_name': 'Persona Prueba', 'recognition': True})[0].json()
    assert len(item['requirements']) == 7
    assert 'RFC del contratante' in item['missing']
    response = client.post(f"/mesa-control/cases/{item['id']}/guide", json={'message': 'Qué falta'})
    assert response.status_code == 200
    assert response.json()['mode'] == 'checklist'
    assert 'RFC' in response.json()['answer']


class Drive:
    def __init__(self):
        self.files_saved = []
        self.folders = []
    def files(self):
        return self
    def list(self, **kw):
        self.result = {'files': self.folders}
        return self
    def get(self, **kw):
        self.result = {'id': 'folder', 'parents': ['rfc-parent']}
        return self
    def create(self, body, **kw):
        if body.get('mimeType') == 'application/vnd.google-apps.folder':
            self.folders.append({'id': 'folder'})
            self.result = {'id': 'folder'}
        else:
            self.files_saved.append(body)
            self.result = {'id': str(len(self.files_saved))}
        return self
    def execute(self):
        return self.result


def test_upload_versions_reuse_folder_and_reject_wrong_type(app, monkeypatch):
    _, client, _ = app
    drive = Drive()
    monkeypatch.setattr(mesa.pendientes, '_client_folder_for_row', lambda service, row, create: {'id': 'rfc-parent'})
    monkeypatch.setattr(mesa.pendientes, 'build_pending_drive_service', lambda: drive)
    item = create(client)[0].json()
    path = f"/mesa-control/cases/{item['id']}/documents"
    def upload(content, rev):
        return client.post(path, data={'revision': rev, 'kind': mesa.BASE_DOCS[0]},
                           files={'document': ('solicitud.pdf', io.BytesIO(content), 'application/pdf')})
    assert upload(b'<html>not a pdf', item['revision']).status_code == 422
    item = upload(b'%PDF-1.4 test', item['revision']).json()
    assert item['status'] == 'draft'
    first_revision = item['revision']
    duplicate = upload(b'%PDF-1.4 test', first_revision).json()
    assert duplicate['revision'] == first_revision
    assert len(drive.files_saved) == 1
    item = upload(b'%PDF-1.4 corrected', first_revision).json()
    assert len(item['documents']) == 2
    assert len(drive.folders) == 1
    assert upload(b'%PDF-1.4 stale', first_revision).status_code == 409
    assert len(drive.files_saved) == 2


def test_assignment_and_invalid_data(app):
    _, client, _ = app
    assert create(client, agent_rfc='AGENTE2')[0].status_code == 422
    assert create(client, data={'client_name': 'Cliente', 'rfc': 'invalid'})[0].status_code == 422
    assert create(client, data={'client_name': '   '})[0].status_code == 422


def test_plauto_proposal_requires_explicit_save_and_preserves_revision(app, monkeypatch):
    _, client, factory = app
    item = create(client)[0].json()
    proposed = {**item['data'], 'product': 'Producto confirmado por mensaje'}
    class Model:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def post(self, url, **kwargs):
            assert kwargs['json']['store'] is False
            assert kwargs['json']['tools'][0]['name'] == 'propose_case_data'
            return self
        def raise_for_status(self): pass
        def json(self):
            import json
            return {'output': [{'type': 'function_call', 'name': 'propose_case_data', 'arguments': json.dumps(proposed)}]}
    monkeypatch.setattr(mesa, 'httpx', SimpleNamespace(Client=Model, HTTPError=Exception))
    monkeypatch.setenv('PLAUTO_ENABLED', 'true')
    monkeypatch.setenv('PLAUTO_MODEL', 'test-model')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key-not-real')
    response = client.post(f"/mesa-control/cases/{item['id']}/guide", json={'message': 'Actualiza el producto'})
    assert response.status_code == 200, response.text
    proposal = response.json()['proposal']
    with factory() as db:
        assert db.get(MesaCase, item['id']).data['product'] == item['data']['product']
    assert proposal['revision'] == item['revision']
    saved = client.patch(f"/mesa-control/cases/{item['id']}", json=proposal)
    assert saved.status_code == 200
    assert saved.json()['data'] == proposed
    assert client.patch(f"/mesa-control/cases/{item['id']}", json=proposal).status_code == 409


def test_private_pilot_denies_all_routes_to_other_admins(app, monkeypatch):
    api, client, _ = app
    from services.mesa_access import mesa_available
    monkeypatch.setattr(mesa, 'mesa_available', mesa_available)
    monkeypatch.setenv('MESA_OWNER_USERNAME', 'owner@example.test')
    api.dependency_overrides[current_access_profile] = lambda: profile(role='admin', username='other@example.test')
    assert client.get('/mesa-control/config').status_code == 403
    assert client.get('/mesa-control/cases').status_code == 403
    assert create(client)[0].status_code == 403
    assert client.get('/mesa-control/cases/nonexistent').status_code == 403
    assert client.post('/mesa-control/cases/nonexistent/generate-form', json={'revision': 1}).status_code == 403
    api.dependency_overrides[current_access_profile] = lambda: profile(role='admin', username='OWNER@example.test')
    assert client.get('/mesa-control/config').status_code == 200
    monkeypatch.delenv('MESA_OWNER_USERNAME')
    assert client.get('/mesa-control/config').status_code == 403


def test_folder_parent_uses_existing_rfc_resolver_and_identity_is_immutable(app, monkeypatch):
    _, client, _ = app
    calls = []
    def parent(service, row, create):
        calls.append(row['summary'])
        assert create is True
        return {'id': 'rfc-parent'}
    monkeypatch.setattr(mesa.pendientes, '_client_folder_for_row', parent)
    drive = Drive()
    monkeypatch.setattr(mesa.pendientes, 'build_pending_drive_service', lambda: drive)
    item = create(client)[0].json()
    item = client.post(f"/mesa-control/cases/{item['id']}/documents", data={'revision': item['revision'], 'kind': mesa.BASE_DOCS[0]}, files={'document': ('solicitud.pdf', b'%PDF-1.4 test', 'application/pdf')}).json()
    assert calls == [{'RFC': 'AAAA901001AB1', 'Contratante': 'Cliente de Prueba'}]
    assert drive.files_saved[0]['parents'] == ['folder']
    response = client.patch(f"/mesa-control/cases/{item['id']}", json={'revision': item['revision'], 'data': {**item['data'], 'rfc': 'BBBB900101AB1'}})
    assert response.status_code == 409


def test_extracted_value_must_match_document_and_is_audited(app, monkeypatch):
    _, client, factory = app
    from reportlab.pdfgen.canvas import Canvas
    import hashlib
    stream = io.BytesIO(); canvas = Canvas(stream)
    canvas.drawString(40, 700, 'Correo del contratante: prueba@example.com')
    canvas.save(); content = stream.getvalue()
    item = create(client)[0].json()
    doc_id = str(uuid4())
    doc = {'id': doc_id, 'sha256': hashlib.sha256(content).hexdigest(), 'name': 'contacto.pdf', 'kind': 'Documentos adicionales'}
    monkeypatch.setattr(mesa, 'read_case_document', lambda item, key: (doc, content))
    path = f"/mesa-control/cases/{item['id']}/documents/{doc_id}"
    extracted = client.post(path + '/extract').json()
    assert extracted['candidates'][0]['page'] == 1
    payload = {'revision': item['revision'], 'field': 'email', 'value': 'inventado@example.com', 'page': 1}
    assert client.post(path + '/confirm-extraction', json=payload).status_code == 422
    payload['value'] = 'prueba@example.com'
    confirmed = client.post(path + '/confirm-extraction', json=payload)
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()['data']['email'] == payload['value']
    with factory() as db:
        event = db.get(MesaCase, item['id']).history[-1]
        assert event['action'] == 'extraction_confirmed'
        assert event['evidence']['page'] == 1 and event['sha256'] == doc['sha256']
    assert client.post(path + '/confirm-extraction', json=payload).status_code == 409
