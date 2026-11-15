import os
import unittest
from unittest.mock import patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from database import Base, Lead, Candidate, CommercialOpportunity
from services import lead_capture as cap
from services.auth import AccessProfile


def profile(role='admin', promos=('TAIICO',), rfc='', permission='operacion'):
    return AccessProfile(username='test@taiico.com', role=role, promotorias=promos, rfc=rfc, aseguradoras=(), module_permissions={'gestion_comercial': permission, 'recluta': permission})

class LeadCaptureTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        self.payload = cap.Intake(nombre='Prueba local', telefono='5512345678', correo='test@example.invalid', ciudad='CDMX', interes='Vida', consentimiento='si', whatsapp='no', utm_source='facebook')

    def tearDown(self):
        self.engine.dispose()

    def test_atomic_capture_and_retry(self):
        with self.factory() as db:
            a, created = cap.save_intake(db, 'clientes', self.payload); db.commit()
            b, repeated = cap.save_intake(db, 'clientes', self.payload); db.commit()
            self.assertTrue(created); self.assertFalse(repeated); self.assertEqual(a.id, b.id)
            self.assertEqual(db.query(CommercialOpportunity).count(), 1)
            self.assertEqual(a.metadata_json['promotoria'], 'TAIICO')
            self.assertFalse(a.metadata_json['whatsapp_consent'])
            self.assertEqual(a.phone, '+525512345678')
            cap.save_intake(db, 'agentes', self.payload); db.commit()
            self.assertEqual(db.query(Candidate).count(), 1)
            self.assertEqual(db.query(Lead).count(), 2)

    def test_validation(self):
        for values in ({'telefono':'123'}, {'correo':'bad'}, {'consentimiento':'no'}, {'nombre':' '}):
            with self.assertRaises(ValueError): cap.Intake(**{**self.payload.model_dump(), **values})

    def test_scope_and_assignment(self):
        with self.factory() as db:
            lead, _ = cap.save_intake(db, 'clientes', self.payload); db.commit(); id = lead.id
        agent = {'rfc':'TAIICO1', 'name':'Agente prueba'}
        with patch.object(cap, 'SessionLocal', self.factory), patch.object(cap, 'eligible_agents', return_value=[agent]):
            with self.assertRaises(HTTPException): cap.list_leads('clientes', profile(promos=('ABONDANZA',)))
            self.assertEqual(cap.list_leads('clientes', profile(role='agente',rfc='TAIICO1'))['leads'], [])
            with self.assertRaises(HTTPException): cap.update_lead('clientes', id, cap.LeadUpdate(agent_rfc='OTHER'), profile())
            cap.update_lead('clientes', id, cap.LeadUpdate(agent_rfc='TAIICO1'), profile())
            self.assertEqual(len(cap.list_leads('clientes', profile(role='agente',rfc='TAIICO1'))['leads']), 1)
            result = cap.update_lead('clientes', id, cap.LeadUpdate(stage='contacted'), profile(role='agente',rfc='TAIICO1',permission='lectura'))
            self.assertEqual(result['lead']['stage'], 'contacted')
            with self.factory() as db:
                self.assertEqual(db.query(CommercialOpportunity).one().owner_agent_rfc, 'TAIICO1')
            with self.assertRaises(HTTPException): cap.update_lead('clientes', id, cap.LeadUpdate(stage='contacted'), profile(permission='lectura'))
            with self.assertRaises(HTTPException): cap.update_lead('clientes', id, cap.LeadUpdate(stage='contacted'), profile(role='agente',rfc='OTHER'))

    def test_http_auth_payload_and_limit(self):
        app = FastAPI(); app.include_router(cap.router)
        cap._attempts.clear()
        with patch.object(cap, 'SessionLocal', self.factory), patch.dict(os.environ, {'TAIICO_WEBSITE_WEBHOOK_KEY':'test-secret'}), TestClient(app) as client:
            url='/captacion/elementor/clientes'
            self.assertEqual(client.post(url,json=self.payload.model_dump()).status_code,401)
            self.assertEqual(client.post(url+'?key=test-secret',json={'bad':'data'}).status_code,422)
            self.assertEqual(client.post(url+'?key=test-secret',json=self.payload.model_dump()).status_code,200)
            self.assertEqual(client.post(url+'?key=test-secret',data=self.payload.model_dump()).status_code,200)
            self.assertEqual(client.post(url+'?key=test-secret',content=b'x'*33000).status_code,413)
            with self.factory() as db: self.assertEqual(db.query(Lead).count(),1)
            self.assertEqual(client.post(url+'?key=test-secret',json={**self.payload.model_dump(),'website':'spam'}).status_code,422)

if __name__ == '__main__': unittest.main()
