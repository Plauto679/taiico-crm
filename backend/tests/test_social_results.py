import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from services import social_results as sr, social_media as sm

class ResultsTests(unittest.TestCase):
 def setUp(self):
  self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
  sm.Base.metadata.create_all(self.engine,tables=[sm.SocialCampaign.__table__,sm.SocialPost.__table__,sr.SocialAnalyticsSnapshot.__table__])
  self.factory=sessionmaker(bind=self.engine);self.mock=patch.object(sr,'SessionLocal',self.factory);self.mock.start()
  with self.factory() as db:
   db.add(sm.SocialCampaign(id='c',name='Campaña',objective='Orgánica',created_at=sm.now()))
   db.add(sm.SocialPost(id='p',campaign_id='c',title='Tema',channel='facebook',copy='Exacto',status='publicado',published_at='2026-11-12T19:00:00+01:00',publication_url='https://facebook.com/page/posts/123',updated_at=sm.now()))
   db.commit()
 def tearDown(self):self.mock.stop();self.engine.dispose()
 def doc(self,rows):return {'brand_id':'7964298','fetched_at':'2026-11-15T10:00:00+00:00','from':'2026-11-01','to':'2026-11-15','datasets':{'facebook_posts':{'fields':sr.FIELDS['facebook_posts'],'rows':rows}}}
 def test_facebook_alternate_id_match_and_missing(self):
  sr.import_snapshot(self.doc([['20261112180000','Exacto','https://facebook.com/page/posts/456','0','0','66','36','7','3']]))
  m=sr.results()['posts'][0]['analytics'];self.assertEqual(m['match'],'copy_and_date');self.assertEqual(m['interactions'],10);self.assertEqual(m['clicks'],0);self.assertIsNone(m['views'])
 def test_unmatched_never_assigned(self):
  sr.import_snapshot(self.doc([['20261112180000','Otro','https://facebook.com/page/posts/456','0','0',None,'36','7',None]]))
  r=sr.results();self.assertIsNone(r['posts'][0]['analytics']);self.assertEqual(r['unmatched_rows'],1)
 def test_invalid_brand_and_rows(self):
  doc=self.doc([]);doc['brand_id']='another'
  with self.assertRaises(ValueError):sr.import_snapshot(doc)
  with self.assertRaises(ValueError):sr.import_snapshot(self.doc([['bad']]))
 def test_stale_does_not_replace_newer(self):
  sr.import_snapshot(self.doc([['20261112180000','Exacto','https://facebook.com/page/posts/123',0,0,9,8,2,1]]))
  old=self.doc([]);old['fetched_at']='2026-11-14T00:00:00Z';sr.import_snapshot(old)
  self.assertEqual(sr.results()['posts'][0]['analytics']['impressions'],9)
 def test_non_numbers_not_zero(self):
  for v in [None,'','NaN','Infinity',-1,'bad']:self.assertIsNone(sr.number(v))
  self.assertEqual(sr.number('0'),0)
 def test_midnight_publication_matches_utc_metric(self):
  self.assertTrue(sr.same_publication_time('20261114232024','2026-11-15T00:20:00+01:00'))
  self.assertFalse(sr.same_publication_time('20261113232024','2026-11-15T00:20:00+01:00'))
