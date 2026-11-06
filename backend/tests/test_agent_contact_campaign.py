import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from database import Campaign
from services.campaign_surveys import CONTACT_SURVEY, validate_answers
from services.campanas import _campaign_audience, CampaignInput


def test_contact_phone_normalization_and_optional_consent():
    answers = {'phone': '+52 (55) 1234-5678', 'has_whatsapp': 'Sí', 'whatsapp_consent': 'No'}
    result = validate_answers(CONTACT_SURVEY, answers)
    assert result['phone'] == '+525512345678'
    assert result['whatsapp_consent'] == 'No'


@pytest.mark.parametrize('changes', [
    {'phone': '5512345678'}, {'phone': '+52 123'}, {'phone': '+52abcdefghij'},
    {'whatsapp_consent': ''}, {'has_whatsapp': 'No', 'whatsapp_consent': 'Sí'},
])
def test_invalid_contact_submission_rejected(changes):
    answers = {'phone': '+525512345678', 'has_whatsapp': 'Sí', 'whatsapp_consent': 'No'}
    with pytest.raises(HTTPException):
        validate_answers(CONTACT_SURVEY, {**answers, **changes})


def test_contact_campaign_routes_to_agents():
    payload = CampaignInput(tipo='agentes_actualizacion_datos', nombre='Contacto', asunto='Actualiza', cuerpo='Hola')
    with patch('services.campanas.build_agent_audience', return_value={'rows': []}) as audience:
        assert _campaign_audience(Campaign(segment_json={'tipo': payload.tipo})) == {'rows': []}
        audience.assert_called_once_with(promotoria="TAIICO")


def test_taiico_scope_is_exact_and_applied_before_deduplication():
    from services.campaign_surveys import build_agent_audience
    rows = [
        {'row_number': 2, 'nombre': 'Otra', 'rfc': 'SAME', 'promotoria': 'ABONDANZA'},
        {'row_number': 3, 'nombre': 'Taiico', 'rfc': 'SAME', 'promotoria': ' taiico ', 'correo_personal': 'agent@example.com'},
        {'row_number': 4, 'nombre': 'Sin', 'rfc': 'NONE'},
        {'row_number': 5, 'nombre': 'Mixta', 'rfc': 'MIX', 'promotoria': 'TAIICO, ABONDANZA'},
        {'row_number': 6, 'nombre': 'Otra', 'rfc': 'OTHER', 'promotoria': 'OTRA'},
    ]
    with patch('services.campaign_surveys.load_agents_directory', return_value={'agents': rows}):
        result = build_agent_audience(promotoria='TAIICO')
    assert [row['nombre_cliente'] for row in result['rows']] == ['Taiico']
    assert result['summary']['source_records'] == 1
    assert result['summary']['duplicate_records'] == 0


def test_prepared_recipient_outside_taiico_is_never_sent(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from database import Base, CampaignDelivery
    from services import campanas
    engine = create_engine('sqlite:///' + str(tmp_path / 'scope.db'))
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(campanas, 'SessionLocal', factory)
    monkeypatch.setattr(campanas, 'smtp_settings_for', lambda _: {'configured': True})
    with factory() as db:
        db.add(Campaign(id='scope', name='Scoped', subject='Test', body='Test', created_by='test',
                        segment_json={'tipo': 'agentes_actualizacion_datos'}))
        db.add(CampaignDelivery(id='outside', campaign_id='scope', recipient_key='other',
                                client_name='Other', email='other@example.com', status='enviando'))
        db.commit()
    with patch.object(campanas, '_campaign_audience', return_value={'rows': []}), patch.object(campanas, 'send_email_smtp') as send:
        campanas.process_campaign_batch('scope', ['outside'], 'test')
        send.assert_not_called()
    with factory() as db:
        assert db.get(CampaignDelivery, 'outside').status == 'rechazado'
    engine.dispose()
