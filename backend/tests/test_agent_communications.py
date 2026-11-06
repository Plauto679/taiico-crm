from unittest.mock import patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, Campaign, CampaignDelivery, AgentCommunicationPreference
from services import agent_communications as c
from services import campanas
from services.renovaciones import send_email_smtp

@pytest.fixture
def store(tmp_path,monkeypatch):
    engine=create_engine('sqlite:///'+str(tmp_path/'prefs.db'));Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine);monkeypatch.setattr(c,'SessionLocal',factory)
    yield factory
    engine.dispose()

AGENT={'rfc':'RFC1','nombre':'Agente Uno','correo_personal':'agent@example.com'}

def test_preference_survives_directory_reload_and_reactivation(store):
    c.set_preference(AGENT,False,'admin')
    assert c.apply_preferences({'agents':[dict(AGENT,row_number=500)]})['agents'][0]['recibir_comunicaciones'] is False
    assert c.filter_recipients(['Agente <AGENT@example.com>','other@example.com'])==['other@example.com']
    c.set_preference(AGENT,True,'admin')
    assert c.filter_recipients(['agent@example.com'])==['agent@example.com']
    with store() as db:assert len(db.get(AgentCommunicationPreference,c.agent_key(AGENT)).history)==2

def test_changed_email_retains_opt_out(store):
    c.set_preference(AGENT,False,'admin');c.sync_identity(AGENT,{**AGENT,'correo_personal':'new@example.com'})
    assert c.filter_recipients(['agent@example.com','new@example.com'])==[]

def test_opt_out_cancels_queued_not_historical_deliveries(store):
    with store() as db:
        db.add(Campaign(id='c',name='Test',subject='Test',body='Test',created_by='admin'))
        for i,status in enumerate(['pendiente','enviando','enviado']):
            db.add(CampaignDelivery(id=str(i),campaign_id='c',recipient_key=str(i),client_name='Test',email='agent@example.com',status=status))
        db.commit()
    c.set_preference(AGENT,False,'admin')
    with store() as db:
        assert db.get(CampaignDelivery,'0').status=='excluido_comunicaciones'
        assert db.get(CampaignDelivery,'1').status=='excluido_comunicaciones'
        assert db.get(CampaignDelivery,'2').status=='enviado'

def test_mail_is_blocked_before_smtp_and_security_mail_can_be_requested(store):
    c.set_preference(AGENT,False,'admin')
    with patch('services.renovaciones.smtplib.SMTP') as smtp:
        settings={'host':'smtp.test','user':'test','password':'test','sender':'test@example.com'}
        with pytest.raises(c.CommunicationOptOutError):send_email_smtp('Reminder','Body',['agent@example.com'],settings=settings)
        smtp.assert_not_called()
        send_email_smtp('Reset','Body',['agent@example.com'],settings=settings,respect_agent_preferences=False)
        assert smtp.called

def test_prepared_campaign_rechecks_before_delivery(store,monkeypatch):
    monkeypatch.setattr(campanas,'SessionLocal',store)
    monkeypatch.setattr(campanas,'smtp_settings_for',lambda _: {'host':'smtp.test','user':'test','password':'test','sender':'test@example.com'})
    c.set_preference(AGENT,False,'admin')
    with store() as db:
        db.add(Campaign(id='c',name='Test',subject='Test',body='Test',created_by='admin'))
        db.add(CampaignDelivery(id='d',campaign_id='c',recipient_key='x',client_name='Test',email='agent@example.com',status='enviando'))
        db.commit()
    with patch('services.renovaciones.smtplib.SMTP') as smtp:
        campanas.process_campaign_batch('c',['d'],'admin');smtp.assert_not_called()
    with store() as db:assert db.get(CampaignDelivery,'d').status=='excluido_comunicaciones'
