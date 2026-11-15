import io
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from services import social_media as sm
from services.authorization import current_access_profile
from services.auth import AccessProfile

class SocialTests(unittest.TestCase):
 def setUp(self):
  self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
  sm.Base.metadata.create_all(self.engine,tables=[sm.SocialCampaign.__table__,sm.SocialPost.__table__,sm.SocialAsset.__table__,sm.SocialEvent.__table__,sm.SocialDelivery.__table__])
  self.factory=sessionmaker(bind=self.engine)
  self.app=FastAPI();self.app.include_router(sm.router)
  self.owner=AccessProfile(sm.OWNER,'admin',('TAIICO',),'',(),{'redes_sociales':'operacion'})
  self.app.dependency_overrides[current_access_profile]=lambda:self.owner
  self.patcher=patch.object(sm,'SessionLocal',self.factory);self.patcher.start()
  self.client=TestClient(self.app)
 def tearDown(self):self.patcher.stop();self.engine.dispose()
 def make(self):
  c=self.client.post('/redes-sociales/campaigns',json={'name':'Prueba','objective':'Orgánico'}).json()
  p={'title':'Tema','channel':'instagram','copy':'Copy','status':'revision'}
  r=self.client.post('/redes-sociales/campaigns/'+c['id']+'/posts',json=p);self.assertEqual(r.status_code,200);return r.json()
 def test_other_admin_denied_every_route(self):
  self.app.dependency_overrides[current_access_profile]=lambda:AccessProfile('pamela.alfaro@taiico.com','admin',('TAIICO',),'',(),{})
  for method,path in [('get',''),('post','/campaigns'),('put','/posts/x'),('post','/assets'),('get','/assets/x'),('get','/posts/x/history'),('post','/posts/x/publication'),('put','/posts/x/metrics')]:
   self.assertEqual(getattr(self.client,method)('/redes-sociales'+path).status_code,403)
 def test_anonymous_denied(self):
  self.app.dependency_overrides.clear();self.assertEqual(self.client.get('/redes-sociales').status_code,401)
 def test_edit_history_and_stale_revision(self):
  p=self.make();url='/redes-sociales/posts/'+p['id'];p['copy']='Nuevo'
  r=self.client.put(url,json=p);self.assertEqual(r.status_code,200);self.assertEqual(r.json()['revision'],2)
  self.assertEqual(self.client.put(url,json=p).status_code,409)
  self.assertEqual(len(self.client.get(url+'/history').json()),2)
 def test_published_immutable_and_metrics(self):
  p=self.make();url='/redes-sociales/posts/'+p['id']
  r=self.client.post(url+'/publication',json={'revision':1,'publication_url':'https://www.instagram.com/p/example/','published_at':'2026-01-01T12:00:00Z'});self.assertEqual(r.status_code,200)
  p['revision']=2;self.assertEqual(self.client.put(url,json=p).status_code,409)
  r=self.client.put(url+'/metrics',json={'revision':2,'reach':10,'impressions':20,'interactions':3,'clicks':1});self.assertEqual(r.status_code,200);self.assertEqual(r.json()['metrics']['source'],'manual')
 def test_validation(self):
  p=self.make();url='/redes-sociales/posts/'+p['id'];p['copy']='x'*2201
  self.assertEqual(self.client.put(url,json=p).status_code,422)
  p['copy']='';p['status']='listo';self.assertEqual(self.client.put(url,json=p).status_code,422)
  self.assertEqual(self.client.post('/redes-sociales/assets',files={'file':('bad.png',b'<script>','image/png')}).status_code,422)
  self.assertEqual(self.client.post(url+'/publication',json={'revision':1,'publication_url':'https://instagram.com.evil.example/p/a','published_at':'2026-01-01T12:00:00Z'}).status_code,422)
 def test_uploaded_asset_is_private_and_preserves_previous_version(self):
  import tempfile
  from pathlib import Path
  from PIL import Image
  image=io.BytesIO();Image.new('RGB',(20,20),'blue').save(image,format='PNG')
  with tempfile.TemporaryDirectory() as folder,patch.object(sm,'ASSETS',Path(folder)):
   r=self.client.post('/redes-sociales/assets',files={'file':('art.png',image.getvalue(),'image/png')});self.assertEqual(r.status_code,200);aid=r.json()['id']
   self.assertEqual(self.client.get('/redes-sociales/assets/'+aid).status_code,200)
   p=self.make();p['asset_id']=aid;p['status']='listo';r=self.client.put('/redes-sociales/posts/'+p['id'],json=p);self.assertEqual(r.status_code,200)
   self.app.dependency_overrides[current_access_profile]=lambda:AccessProfile('other@taiico.com','admin',('TAIICO',),'',(),{})
   self.assertEqual(self.client.get('/redes-sociales/assets/'+aid).status_code,403)

 def test_configurable_access_and_read_only(self):
  self.app.dependency_overrides[current_access_profile]=lambda:AccessProfile('katia.gonzalez@taiico.com','admin',('TAIICO',),'',(),{'redes_sociales':'operacion'})
  p=self.make()
  self.assertTrue(self.client.get('/redes-sociales').json()['can_operate'])
  self.app.dependency_overrides[current_access_profile]=lambda:AccessProfile('reader@taiico.com','admin',('TAIICO',),'',(),{'redes_sociales':'lectura'})
  self.assertFalse(self.client.get('/redes-sociales').json()['can_operate'])
  self.assertEqual(self.client.get('/redes-sociales/posts/'+p['id']+'/history').status_code,200)
  for method,path in [('post','/campaigns'),('post','/campaigns/x/posts'),('put','/posts/x'),('post','/assets'),('post','/posts/x/publication'),('put','/posts/x/metrics')]:
   self.assertEqual(getattr(self.client,method)('/redes-sociales'+path).status_code,403)
 def test_other_promotoria_denied(self):
  self.app.dependency_overrides[current_access_profile]=lambda:AccessProfile('other@example.com','admin',('ABBONDANZA',),'',(),{'redes_sociales':'operacion'})
  self.assertEqual(self.client.get('/redes-sociales').status_code,403)
 def test_scheduled_content_locked_but_publication_can_be_recorded(self):
  p=self.make()
  with self.factory() as db:
   db.get(sm.SocialPost,p['id']).status='programado';db.commit()
  url='/redes-sociales/posts/'+p['id']
  self.assertEqual(self.client.put(url,json=p).status_code,409)
  self.assertEqual(self.client.post(url+'/publication',json={'revision':1,'publication_url':'https://www.instagram.com/p/example/','published_at':'2026-01-01T12:00:00Z'}).status_code,200)
 def test_new_permission_defaults_closed(self):
  from services.auth import _default_module_permissions, PROMOTORIAS, MODULES
  self.assertIn('redes_sociales',MODULES)
  self.assertEqual(_default_module_permissions('admin',PROMOTORIAS)['redes_sociales'],'ninguno')
