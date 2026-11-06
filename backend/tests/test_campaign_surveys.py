import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from database import Campaign
from services.campaign_surveys import build_agent_audience, AI_SURVEY
from services.campanas import CampaignInput, _campaign_audience, prepare_campaign_deliveries


class AgentSurveyTests(unittest.TestCase):
    def test_all_agents_included_missing_email_and_duplicate_identity_handled(self):
        agents = [
            {'row_number':2,'nombre':'Ana','rfc':'RFC1','correo_personal':'ANA@example.com','estatus_met':'BAJA'},
            {'row_number':3,'nombre':'Ana','rfc':'RFC1','correo_personal':'ana@example.com'},
            {'row_number':4,'nombre':'Beto','rfc':'RFC2','correo_personal':'incorrecto'},
            {'row_number':5,'nombre':'Caro','rfc':'RFC3','correo_personal':'ANA@example.com'},
        ]
        with patch('services.campaign_surveys.load_agents_directory',return_value={'agents':agents}):
            result=build_agent_audience()
        self.assertEqual(len(result['rows']),3)
        self.assertEqual(result['summary']['clients_missing_email'],1)
        self.assertEqual(result['summary']['duplicate_records'],1)
        self.assertEqual(len({r['key'] for r in result['rows']}),3)

    def test_survey_audience_does_not_use_client_policy_source(self):
        c=Campaign(segment_json={'tipo':'agentes_encuesta_ia'})
        with patch('services.campanas.build_agent_audience',return_value={'rows':[]}) as build:
            self.assertEqual(_campaign_audience(c),{'rows':[]})
            build.assert_called_once()

    def test_legacy_input_defaults_preserved_and_open_question_present(self):
        payload=CampaignInput(nombre='Test',asunto='Hello',cuerpo='Message')
        self.assertEqual(payload.tipo,'gmm_deducible')
        self.assertEqual(AI_SURVEY['questions'][0]['max_choices'],3)
        self.assertTrue(any(q['id']=='open' and q['type']=='text' for q in AI_SURVEY['questions']))

    def test_answers_reject_invalid_or_exclusive_choices(self):
        from services.campaign_surveys import validate_answers
        answers={'priorities':['Llenar solicitudes y formatos'],'time':'Menos de 1 hora','pilot':'Por ahora no'}
        self.assertEqual(validate_answers(AI_SURVEY,answers)['priorities'],answers['priorities'])
        for options in [['invalid'],['Por ahora no necesito apoyo de IA','Llenar solicitudes y formatos'],['Llenar solicitudes y formatos']*2]:
            with self.assertRaises(HTTPException): validate_answers(AI_SURVEY,{**answers,'priorities':options})

    def test_submission_is_single_use_and_tests_excluded(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from database import Base, CampaignSurveyResponse
        from services import campaign_surveys as surveys
        from datetime import datetime, timedelta
        engine=create_engine('sqlite://')
        Base.metadata.create_all(engine)
        factory=sessionmaker(bind=engine)
        with factory() as db:
            db.add(CampaignSurveyResponse(id='token',campaign_id='c',recipient_key='test:x',recipient_name='Internal',is_test=True,questionnaire=AI_SURVEY,expires_at=datetime.utcnow()+timedelta(days=1)))
            db.commit()
        answers={'priorities':['Llenar solicitudes y formatos'],'time':'Menos de 1 hora','pilot':'Por ahora no'}
        with patch.object(surveys,'SessionLocal',factory):
            self.assertTrue(surveys.submit_survey('token',surveys.SurveySubmission(answers=answers))['saved'])
            with self.assertRaises(HTTPException) as error: surveys.submit_survey('token',surveys.SurveySubmission(answers=answers))
            self.assertEqual(error.exception.status_code,409)
            self.assertEqual(surveys.survey_results('c',None)['responded'],0)
            with self.assertRaises(HTTPException): surveys.public_survey('unknown')

    def test_test_email_uses_isolated_link_and_only_internal_recipient(self):
        from services import campanas
        from types import SimpleNamespace
        campaign=Campaign(id='c',subject='Hola {{agente}}',body='Contesta aquí',segment_json={'encuesta':AI_SURVEY})
        db=MagicMock()
        row={'key':'agent:1','agente':'Ana','nombre_cliente':'Ana','email':'agent@example.com'}
        with patch.object(campanas,'SessionLocal',return_value=db), patch.object(campanas,'_campaign_or_404',return_value=campaign), patch.object(campanas,'_campaign_audience',return_value={'rows':[row]}), patch.object(campanas,'survey_link',return_value='https://taiico-crm.com/encuesta/test') as link, patch.object(campanas,'smtp_settings_for',return_value={'ok':True}), patch.object(campanas,'send_email_smtp') as send:
            campanas.send_campaign_test('c',campanas.CampaignTestRequest(recipient_key='agent:1',test_email='review@taiico.com'),SimpleNamespace(username='admin'))
            self.assertTrue(link.call_args.kwargs['is_test'])
            self.assertEqual(send.call_args.args[2],['review@taiico.com'])
            self.assertIn('/encuesta/test',send.call_args.args[1])

    def test_survey_test_email_does_not_require_loading_audience(self):
        from services import campanas
        from types import SimpleNamespace
        campaign=Campaign(id='c',subject='Hola {{agente}}',body='Encuesta',segment_json={'encuesta':AI_SURVEY})
        with patch.object(campanas,'SessionLocal',return_value=MagicMock()), patch.object(campanas,'_campaign_or_404',return_value=campaign), patch.object(campanas,'_campaign_audience') as audience, patch.object(campanas,'survey_link',return_value='https://taiico-crm.com/encuesta/test'), patch.object(campanas,'smtp_settings_for',return_value={'ok':True}), patch.object(campanas,'send_email_smtp') as send:
            result=campanas.send_campaign_test('c',campanas.CampaignTestRequest(test_email='review@taiico.com'),SimpleNamespace(username='admin'))
            audience.assert_not_called()
            self.assertTrue(result['sent'])
            self.assertEqual(send.call_args.args[2],['review@taiico.com'])
            self.assertEqual(send.call_args.args[0],'[PRUEBA CAMPAÑA] Hola Equipo TAIICO')
