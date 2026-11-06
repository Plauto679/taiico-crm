from types import SimpleNamespace
import pytest
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base, Campaign, CampaignDelivery
from services import campanas as c


def test_launch_claims_all_pending_once_and_rejects_unapproved(tmp_path, monkeypatch):
    engine=create_engine('sqlite:///'+str(tmp_path/'campaign.db'))
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine)
    monkeypatch.setattr(c,'SessionLocal',factory)
    monkeypatch.setattr(c,'smtp_settings_for',lambda _: {'configured':True})
    with factory() as db:
        db.add(Campaign(id='c',name='Approved',subject='Test',body='Body',status='preparada',created_by='test'))
        for i in range(29):
            db.add(CampaignDelivery(id=str(i),campaign_id='c',recipient_key=str(i),client_name='Test',status='pendiente' if i<27 else ('enviado' if i==27 else 'sin_correo'),attempts=0))
        db.commit()
    actor=SimpleNamespace(username='test')
    with pytest.raises(HTTPException):
        c.launch_campaign('c',c.CampaignLaunchRequest(confirmation='Wrong'),BackgroundTasks(),actor)
    tasks=BackgroundTasks()
    result=c.launch_campaign('c',c.CampaignLaunchRequest(confirmation='Approved'),tasks,actor)
    assert result['accepted']==27 and len(tasks.tasks)==1
    with pytest.raises(HTTPException):
        c.launch_campaign('c',c.CampaignLaunchRequest(confirmation='Approved'),BackgroundTasks(),actor)
    with factory() as db:
        assert db.query(CampaignDelivery).filter_by(status='enviando',attempts=1).count()==27
        assert db.get(CampaignDelivery,'27').status=='enviado'
        assert db.get(CampaignDelivery,'28').status=='sin_correo'
    engine.dispose()
