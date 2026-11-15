"""Idempotent import of existing local editorial drafts; never publishes."""
import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image
from services import social_media as sm

def main():
 sm.init_schema()
 source=sm.ROOT/'docs/marketing/calendario-taiico-2026-11.json'
 calendar=json.loads(source.read_text())
 with sm.SessionLocal() as db:
  cid='taiico-organico-2026-11'
  if db.get(sm.SocialCampaign,cid):
   print('Calendar already imported; preserving edits.');return
  db.add(sm.SocialCampaign(id=cid,name='Taiico · Noviembre 2026 · Revisión editorial',objective='Reconocimiento y tráfico orgánico hacia Taiico. Material previo pendiente de adaptar al kit oficial, variar temas y conectar con el blog. Fechas propuestas por revisar; no programadas.',created_at=sm.now()))
  sm.ASSETS.mkdir(parents=True,exist_ok=True)
  for index,item in enumerate(calendar['posts']):
   aid=None
   path=source.parent/item['artwork']
   if path.is_file():
    aid=str(uuid.uuid4())
    with Image.open(path) as im:im.convert('RGBA').save(sm.ASSETS/f'{aid}.png')
    db.add(sm.SocialAsset(id=aid,filename=path.name,created_at=sm.now()))
   for channel in ('facebook','instagram'):
    planned=datetime.fromisoformat(item['date']+'T'+item['time_madrid']).replace(tzinfo=ZoneInfo('Europe/Madrid')).isoformat()
    p=sm.SocialPost(id=str(uuid.uuid4()),campaign_id=cid,title=item['title'],channel=channel,copy=item[channel],status='revision',planned_at=planned,landing_url=item.get('landing',''),notes='Material anterior: revisar colores y variedad editorial antes de publicar. '+item.get('visual_brief',''),asset_id=aid,revision=1,publication_url='',updated_at=sm.now())
    db.add(p);db.flush();sm.event(db,p,sm.OWNER,'importación de borrador previo')
  db.commit();print('Imported',len(calendar['posts'])*2,'draft posts; no publication scheduled.')
if __name__=='__main__':main()
