import io
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from pypdf import PdfReader
from services import mesa_claims as claims, mesa_hospital as hospital, mesa_documents as forms
from services.mesa_control import CaseData, claim_tool_properties
from test_mesa_claims import claim_data


def hospital_data(workflow='cirugia_programada_gmm', **changes):
    data = claim_data()
    data.update(workflow=workflow, hospital_name='Hospital ficticio', event_date=(date.today()+timedelta(days=15)).isoformat(),
                admission_date=date.today().isoformat(), hospital_phase='stay', hospital_in_network=True,
                doctors_in_network=True, policy_current_paid=True, has_surgery_pass=False,
                hospital_reported=True, stay_over_24h=True, mp_required=False)
    data.update(changes)
    return CaseData.model_validate(data).model_dump()


@pytest.mark.parametrize('workflow', hospital.WORKFLOWS)
def test_requirements_do_not_inherit_reimbursement_banking_or_invoices(workflow):
    data = hospital_data(workflow)
    assert claims.missing_data(data) == []
    required=claims.requirements(data)
    assert 'Consentimiento informado firmado' in required
    assert not any('bancario' in x.lower() or 'Facturas' in x for x in required)
    assert not any(f['key'] in {'bank_changed','bank_statement_date','invoices_itemized','includes_medicines'} for f in claims.questions(data))
    for key in ['hospital_in_network','policy_current_paid','doctors_in_network']:
        assert claims.missing_data(hospital_data(workflow,**{key:None}))
    # Negative condition must reach human review, rather than falsely approving coverage.
    assert claims.missing_data(hospital_data(workflow,hospital_in_network=False,policy_current_paid=False)) == []
    assert 'coverage' in claims.review_checks(data) and 'invoices' not in claims.review_checks(data)


def test_conditional_pass_documents_hospital_stages_and_physician_budget():
    data=hospital_data('pago_directo_gmm',has_surgery_pass=True,mp_required=True,hospital_phase='discharge',doctors_in_network=False,doctors_accept_tariff=None)
    required=claims.requirements(data)
    for name in ['Carta pase de programación de cirugía','Expediente clínico completo','Actas del Ministerio Público','Nota de alta firmada','Estado de cuenta hospitalario y desglose','Presupuesto y aceptación de honorarios en informe médico']:
        assert name in required
    assert 'Consentimiento informado firmado' not in required
    assert 'Aceptación de tabulador' in claims.missing_data(data)
    data['has_surgery_pass']=None
    assert 'Consentimiento informado firmado' in claims.requirements(data)
    assert 'Carta pase de cirugía' in claims.missing_data(data)
    data.update(hospital_phase='admission',patient_has_curp=False)
    assert 'Nota de alta firmada' not in claims.requirements(data)
    assert 'Acta de nacimiento del paciente' in claims.requirements(data)


def test_dates_and_short_lead_time_are_reviewed_not_promised():
    past=hospital_data(event_date=(date.today()-timedelta(days=1)).isoformat())
    assert any('ya pasó' in x for x in claims.missing_data(past))
    urgent=hospital_data(event_date=(date.today()+timedelta(days=2)).isoformat())
    assert claims.missing_data(urgent)==[]
    assert any('menos de 10' in x for x in hospital.notices(urgent))
    assert any('seis meses' in x for x in claims.missing_data(hospital_data(medical_report_date='2020-01-01')))
    assert any('Reporte hospitalario sin confirmar' in x for x in hospital.notices(hospital_data('pago_directo_gmm',hospital_reported=False)))
    for key,value in [('event_date','2026-02-30'),('admission_date','2099-01-01'),('hospital_phase','other')]:
        with pytest.raises(ValueError):hospital_data(**{key:value})


@pytest.mark.parametrize('workflow,button', [('cirugia_programada_gmm','PROGRAMACION'),('pago_directo_gmm','INGRRESO')])
def test_pdf_marks_only_requested_claim_type_and_uses_own_verification(tmp_path,monkeypatch,workflow,button):
    monkeypatch.setenv('MESA_FORMS_STATE_PATH',str(tmp_path/'state.json'))
    claims.state_path().write_text(json.dumps({'status':'verified','checked_at':datetime.now(timezone.utc).isoformat()}))
    data=hospital_data(workflow)
    with pytest.raises(HTTPException) as error:forms.generate_form(data,'fixture',1)
    assert error.value.status_code==409 # Reimbursement verification cannot unlock hospital forms.
    claims.state_path(workflow).write_text(json.dumps({'status':'verified','checked_at':datetime.now(timezone.utc).isoformat()}))
    content,meta=forms.generate_form(data,'fixture',1)
    reader=PdfReader(io.BytesIO(content)); fields=reader.get_fields()
    for name in ['REMBOLSO','PROGRAMACION','INGRRESO']:
        assert fields[name]['/V']==('/Yes' if name==button else '/Off')
    assert fields['Nombre de la institución bancaria']['/V']==''
    assert fields['SIEXPUESTA']['/V']=='/Off' and fields['1']['/V']=='/Off'
    assert fields['Nombres']['/V']=='ANA' and meta['partial']
    for page in reader.pages:
        for ref in page.get('/Annots',[]):
            widget=ref.get_object()
            if widget.get('/Subtype')!='/Widget':continue
            field=widget.get('/Parent',widget).get_object()
            assert widget.get('/V',field.get('/V'))==fields[field['/T']]['/V']
            assert widget.get('/AP',{}).get('/N')


def test_plauto_schema_preserves_nullable_conditions():
    schema=claim_tool_properties(hospital_data())
    for key in ['hospital_in_network','doctors_in_network','doctors_accept_tariff','has_surgery_pass','mp_required']:
        assert schema[key]['type']==['boolean','null']
    assert schema['hospital_phase']['enum']==['','admission','stay','discharge']
    assert 'workflow' not in schema


def test_daily_verification_checks_consent_and_direct_medical_link(tmp_path,monkeypatch):
    import hashlib
    monkeypatch.setenv('MESA_FORMS_STATE_PATH',str(tmp_path/'state.json'))
    content={claims.CLAIM_URL:(claims.ASSETS/claims.FORMS['claim']['file']).read_bytes(),
             hospital.DIRECT_MEDICAL_URL:(claims.ASSETS/claims.FORMS['medical']['file']).read_bytes(),
             hospital.CONSENT_URL:(claims.ASSETS/hospital.CONSENT_FORM['file']).read_bytes()}
    assert hashlib.sha256(content[hospital.CONSENT_URL]).hexdigest()==hospital.CONSENT_FORM['sha256']
    html=''.join(f'<a href="{url}">form</a>' for url in content).encode()
    def fetch(client,url):return html if url==hospital.DIRECT_PAGE else content[url]
    monkeypatch.setattr(forms,'_bounded_get',fetch)
    assert claims.check_sources('pago_directo_gmm')['status']=='verified'
    content[hospital.CONSENT_URL]=b'changed'
    assert claims.check_sources('pago_directo_gmm')['status']=='changed'
    assert not claims.status('pago_directo_gmm')['can_generate']
