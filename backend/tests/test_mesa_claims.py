import hashlib
import io
import json
from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException
from pypdf import PdfReader
from services import mesa_claims as claims
from services import mesa_documents as forms
from services.mesa_control import CaseData


def claim_data(**changes):
    return CaseData(client_name='Ana Prueba', rfc='AAAA901001AB1', workflow='reembolso_gmm',
        **{'claim_stage': 'initial', 'policy_number': '12345678', 'contractor_name': 'ANA PRUEBA',
           'paternal_surname': 'PRUEBA', 'given_names': 'ANA', 'patient_paternal_surname': 'PRUEBA',
           'patient_given_names': 'LUIS', 'patient_minor': True, 'patient_has_curp': True,
           'responding_request': False, 'includes_medicines': False, 'includes_studies': False,
           'includes_histopathology': False, 'invoices_itemized': True, 'digital_signature': False,
           'medical_report_date': date.today().isoformat(), 'bank_statement_date': date.today().isoformat(),
           'address_proof_date': date.today().isoformat(), 'bank_holder_complete': True, **changes}).model_dump()


@pytest.fixture
def verified_claims(tmp_path, monkeypatch):
    monkeypatch.setenv('MESA_FORMS_STATE_PATH', str(tmp_path / 'state.json'))
    claims.state_path().write_text(json.dumps({'status': 'verified', 'checked_at': datetime.now(timezone.utc).isoformat()}))


def test_unknown_conditions_block_review_and_no_emission_requirements():
    data = CaseData(client_name='Titular Prueba', workflow='reembolso_gmm').model_dump()
    assert claims.progress(data)['next_field'] == 'claim_stage'
    assert 'Gastos de medicamentos' in claims.missing_data(data)
    assert 'Tipo de reembolso' in claims.missing_data(data)
    assert not any('Cotización' in x or 'Cambios' in x for x in claims.requirements(data))
    assert claims.missing_data(claim_data()) == []


def test_initial_minor_and_complement_bank_conditions():
    initial = claims.requirements(claim_data(patient_has_curp=False, bank_holder_complete=False))
    assert 'Acta de nacimiento del paciente' in initial
    assert 'Identificación de los padres o representantes' in initial
    assert 'Identificación oficial del paciente' not in initial
    assert 'Contrato de la cuenta bancaria' in initial
    assert 'CURP del titular' in initial
    data = claim_data(claim_stage='complement', bank_changed=False, claim_number='SIN123')
    required = claims.requirements(data)
    assert 'Estado de cuenta bancario' not in required
    assert 'Identificación oficial del titular' not in required
    assert claims.missing_data(data) == []
    data.update(bank_changed=True, bank_statement_date='', includes_medicines=True,
                includes_studies=True, includes_histopathology=True, responding_request=True,
                digital_signature=True, invoices_itemized=False)
    required = claims.requirements(data)
    for value in ['Estado de cuenta bancario', 'Receta médica desglosada', 'Resultados e interpretación de estudios',
                  'Reporte histopatológico', 'Requerimiento de MetLife y respuesta',
                  'Fotografías del titular sosteniendo identificación por ambos lados',
                  'Desglose de gastos por concepto y costo unitario']:
        assert value in required
    assert 'DCN del trámite anterior' in claims.missing_data(data)
    assert 'Fecha del estado de cuenta' in claims.missing_data(data)


def test_dates_and_complement_number_are_not_optional():
    data = claim_data(claim_stage='complement', bank_changed=True, medical_report_date='2020-01-01',
                      bank_statement_date='2020-01-01', address_proof_date='2020-01-01')
    missing = claims.missing_data(data)
    assert 'Número de siniestro' in missing
    assert sum('Actualizar' in v for v in missing) == 3
    assert not claims.progress(data)['ready_for_partial_draft']
    for invalid in ['2099-01-01', '2026-02-30', '01/01/2026']:
        with pytest.raises(ValueError): claim_data(medical_report_date=invalid)
    assert 'Resolver CURP del paciente adulto con mesa' in claims.missing_data(claim_data(patient_minor=False, patient_has_curp=False))


@pytest.mark.parametrize('stage', ['initial', 'complement'])
def test_official_pdf_canonical_values_widgets_and_no_sample_date(verified_claims, stage):
    data = claim_data(claim_stage=stage, claim_number='SIN123', curp='AAAA901001MDFRRN09',
                      patient_curp='AAAA151001HDFRRN09', phone='+52 55 1234 5678', email='prueba@example.com')
    original = (claims.ASSETS / claims.FORMS['claim']['file']).read_bytes()
    content, meta = forms.generate_form(data, 'fixture', 4)
    reader = PdfReader(io.BytesIO(content)); fields = reader.get_fields()
    assert len(reader.pages) == 6 and len(fields) == 173
    assert fields['D1']['/V'] == fields['M1']['/V'] == fields['A1']['/V'] == ''
    assert fields['Nombres']['/V'] == 'ANA' and fields['Nombres_2']['/V'] == 'LUIS'
    assert fields['REMBOLSO']['/V'] == '/Yes'
    assert fields['PRIMERA']['/V'] == ('/Yes' if stage == 'initial' else '/Off')
    assert fields['SUBSECUENTE']['/V'] == ('/Yes' if stage == 'complement' else '/Off')
    assert fields['NUMSIN']['/V'] == ('SIN123' if stage == 'complement' else '')
    assert fields['undefined']['/V'] == 'AB1' and fields['Celular']['/V'] == '5512345678'
    assert fields['Nombre de la institución bancaria']['/V'] == ''
    assert fields['1']['/V'] == '/Off' and fields['SIPOLH2']['/V'] == '/Off'
    assert meta['partial'] and meta['case_revision'] == 4
    for page in reader.pages:
        for ref in page.get('/Annots', []):
            w = ref.get_object()
            if w.get('/Subtype') != '/Widget': continue
            f = w.get('/Parent', w).get_object(); key = f['/T']
            assert w.get('/V', f.get('/V')) == fields[key]['/V']
            assert w.get('/AP', {}).get('/N')
            if f.get('/MaxLen'):
                assert w.get('/MaxLen') == f['/MaxLen']
    assert hashlib.sha256(original).hexdigest() == claims.FORMS['claim']['sha256']
    assert (claims.ASSETS / claims.FORMS['claim']['file']).read_bytes() == original


def test_source_changes_staleness_and_overflow_block_drafts(verified_claims, monkeypatch):
    monkeypatch.setattr(forms, '_bounded_get', lambda client, url, **kw:
        ('<a href="'+claims.CLAIM_URL+'">claim</a><a href="'+claims.MEDICAL_URL+'">medical</a>').encode()
        if url == claims.SOURCE_PAGE else b'changed PDF')
    assert claims.check_sources()['status'] == 'changed'
    with pytest.raises(HTTPException) as error: claims.generate(claim_data(), 'test', 1)
    assert error.value.status_code == 409
    claims.state_path().write_text(json.dumps({'status': 'verified', 'checked_at': '2020-01-01T00:00:00+00:00'}))
    assert not claims.status()['can_generate']
    claims.state_path().write_text(json.dumps({'status': 'verified', 'checked_at': datetime.now(timezone.utc).isoformat()}))
    with pytest.raises(HTTPException) as error: claims.generate(claim_data(policy_number='A'*40), 'test', 1)
    assert error.value.status_code == 422
