import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from pypdf import PdfReader
from reportlab.pdfgen.canvas import Canvas
from services import mesa_documents as forms


@pytest.fixture
def verified(tmp_path, monkeypatch):
    path = tmp_path / 'state.json'
    path.write_text(json.dumps({'status': 'verified', 'checked_at': datetime.now(timezone.utc).isoformat(), 'notice': 'verified'}))
    monkeypatch.setenv('MESA_FORMS_STATE_PATH', str(path))
    return path


def test_extraction_preserves_page_evidence_and_never_assumes_identity():
    stream = io.BytesIO(); c = Canvas(stream)
    c.drawString(50, 700, 'RFC AAAA901001AB1 Correo prueba@example.com CURP AAAA901001MDFRRN09')
    c.showPage(); c.drawString(50, 700, 'Telefono 55 1234 5678'); c.save()
    result = forms.extract_candidates(stream.getvalue())
    assert {v['field'] for v in result['candidates']} == {'rfc', 'curp', 'email', 'phone'}
    assert next(v for v in result['candidates'] if v['field'] == 'phone')['page'] == 2
    assert all(v['value'] in v['excerpt'] for v in result['candidates'])
    with pytest.raises(HTTPException): forms.extract_candidates(b'not PDF')


def test_official_form_preserves_pages_and_interactive_values(verified):
    data = {'product': 'MédicaLife Familiar', 'paternal_surname': 'PRUEBA', 'given_names': 'ANA', 'rfc': 'AAAA901001AB1', 'email': 'prueba@example.com'}
    content, meta = forms.generate_form(data, 'case-test', 7)
    reader = PdfReader(io.BytesIO(content)); source = PdfReader(forms.TEMPLATE)
    assert len(reader.pages) == len(source.pages) == 15
    fields = reader.get_fields()
    assert {k: v['/V'] for k, v in fields.items()} == meta['fields']
    assert fields['Apellido paterno']['/V'] == 'PRUEBA'
    assert meta['case_revision'] == 7 and meta['template_sha256'] == forms.TEMPLATE_SHA
    widgets = [a.get_object() for page in reader.pages for a in page.get('/Annots', []) if a.get_object().get('/Subtype') == '/Widget']
    assert len(widgets) == len(meta['fields'])
    assert all(w.get('/AP', {}).get('/N') for w in widgets)
    assert not any('firma' in k.lower() or 'medic' in k.lower() for k in fields)


def test_unreviewed_or_stale_template_blocks_generation(verified):
    data = {'product': 'MédicaLife Familiar', 'paternal_surname': 'PRUEBA', 'given_names': 'ANA', 'rfc': 'AAAA901001AB1'}
    verified.write_text(json.dumps({'status': 'changed', 'checked_at': datetime.now(timezone.utc).isoformat(), 'notice': 'changed'}))
    with pytest.raises(HTTPException) as error: forms.generate_form(data, 'case', 1)
    assert error.value.status_code == 409
    verified.write_text(json.dumps({'status': 'verified', 'checked_at': '2020-01-01T00:00:00+00:00', 'notice': 'old'}))
    assert forms.form_status()['can_generate'] is False


def test_wrong_product_and_overflow_fail_closed(verified):
    data = {'product': 'Primordial', 'paternal_surname': 'PRUEBA', 'given_names': 'ANA', 'rfc': 'AAAA901001AB1'}
    with pytest.raises(HTTPException): forms.generate_form(data, 'case', 1)
    data.update(product='MédicaLife Familiar', given_names='NOMBRE DEMASIADO LARGO ' * 10)
    with pytest.raises(HTTPException): forms.generate_form(data, 'case', 1)


def test_daily_check_never_activates_a_changed_official_pdf(verified, monkeypatch):
    original = forms.TEMPLATE.read_bytes()
    def fetch(client, url, **kwargs):
        if url == forms.CATALOG_URL:
            from urllib.parse import urlparse
            return json.dumps({'response': {'docs': [{'file_title': 'MedicaLife: Solicitud de Seguro de Gastos Médicos Mayores', 'file_url': urlparse(forms.SOURCE_URL).path}]}}).encode()
        return b'%PDF-changed-official-version'
    monkeypatch.setattr(forms, '_bounded_get', fetch)
    result = forms.check_official_form()
    assert result['status'] == 'changed'
    assert forms.form_status()['can_generate'] is False
    assert forms.TEMPLATE.read_bytes() == original
