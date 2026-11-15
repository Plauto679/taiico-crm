"""Metricool snapshots; missing values remain missing, separate from manual metrics."""
import math
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
from sqlalchemy import Column, String, JSON
from database import Base, engine, SessionLocal

FIELDS = {
 'facebook_posts': ['FBPO02','FBPO03','FBPO06','FBPO08','FBPO09','FBPO11','FBPO12','FBPO13','FBPO14'],
 'instagram_posts': ['IGPO02','IGPO03','IGPO06','IGPO08','IGPO12','IGPO13','IGPO14','IGPO15','IGPO27','IGPO28'],
 'facebook_evolution': ['FBEV17','FBEV30','FBEV10'],
 'instagram_evolution': ['IGEV01','IGEV05','IGEV09'],
}
class SocialAnalyticsSnapshot(Base):
 __tablename__='social_analytics_snapshots'
 key=Column(String,primary_key=True)
 fetched_at=Column(String,nullable=False)
 range_from=Column(String,nullable=False)
 range_to=Column(String,nullable=False)
 payload=Column(JSON,nullable=False)

def init_schema(): Base.metadata.create_all(engine,tables=[SocialAnalyticsSnapshot.__table__])
def number(v):
 if v is None or v=='':return None
 try:
  n=float(v)
  return n if math.isfinite(n) and n>=0 else None
 except (TypeError,ValueError):return None

def date_value(v):
 text=str(v or '')
 if re.fullmatch(r'\d{8}(\d{6})?',text):return f'{text[:4]}-{text[4:6]}-{text[6:8]}'
 return ''

def same_publication_time(metric_date, published_at):
 try:
  observed=datetime.strptime(str(metric_date),'%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
  published=datetime.fromisoformat(published_at.replace('Z','+00:00'))
  return published.tzinfo is not None and abs((observed-published).total_seconds())<=3600
 except (ValueError,TypeError,AttributeError):return False

def post_key(url):
 p=urlparse(url or '')
 if p.hostname in ('instagram.com','www.instagram.com'):
  m=re.search(r'/(?:p|reel)/([^/]+)',p.path);return m.group(1) if m else ''
 if p.hostname in ('facebook.com','www.facebook.com'):
  m=re.search(r'/posts/(\d+)',p.path);return m.group(1) if m else ''
 return ''

def import_snapshot(document):
 if str(document.get('brand_id'))!='7964298':raise ValueError('Solo Taiico')
 fetched=datetime.fromisoformat(document['fetched_at'].replace('Z','+00:00'))
 if fetched.tzinfo is None:raise ValueError('Zona horaria requerida')
 with SessionLocal() as db:
  for key,part in document['datasets'].items():
   if key not in FIELDS or part['fields']!=FIELDS[key]:raise ValueError('Campos no reconocidos')
   rows=part['rows'];expected=len(FIELDS[key])+(1 if key.endswith('evolution') else 0)
   if not isinstance(rows,list) or any(not isinstance(r,list) or len(r)!=expected for r in rows):raise ValueError('Filas inválidas')
   old=db.get(SocialAnalyticsSnapshot,key)
   if old and datetime.fromisoformat(old.fetched_at)>fetched:continue
   if not old:old=SocialAnalyticsSnapshot(key=key);db.add(old)
   old.fetched_at=fetched.isoformat();old.range_from=document['from'];old.range_to=document['to'];old.payload=part
  db.commit()

def results():
 from services.social_media import SocialPost,SocialCampaign
 with SessionLocal() as db:
  posts=db.query(SocialPost).filter_by(status='publicado').all()
  snapshots={s.key:s for s in db.query(SocialAnalyticsSnapshot)}
  measured={};accounts=[];unmatched=0
  for key,s in snapshots.items():
   channel=key.split('_')[0]
   for row in s.payload['rows']:
    if key.endswith('evolution'):
     accounts.append({'date':date_value(row[-1]),'channel':channel,'followers':number(row[0]),'impressions':number(row[1]) if channel=='facebook' else None,'views':number(row[1]) if channel=='instagram' else None,'interactions':number(row[2]),'fetched_at':s.fetched_at});continue
    dt,copy,url=row[:3]
    candidates=[p for p in posts if p.channel==channel and post_key(p.publication_url) and post_key(p.publication_url)==post_key(url)]
    match='url'
    if not candidates:
     # Facebook may return a photo ID distinct from the planner's post ID.
     candidates=[p for p in posts if p.channel==channel and p.copy.strip()==str(copy).strip() and same_publication_time(dt,p.published_at)]
     match='copy_and_date'
    if len(candidates)!=1:unmatched+=1;continue
    p=candidates[0]
    if p.id in measured:raise ValueError('Más de una fila corresponde a la misma publicación')
    if channel=='facebook':
     comments,clicks,impressions,reach,likes,shares=map(number,row[3:])
     interactions=sum([comments,likes,shares]) if all(x is not None for x in [comments,likes,shares]) else None
     values={'comments':comments,'clicks':clicks,'impressions':impressions,'reach':reach,'likes':likes,'shares':shares,'interactions':interactions,'views':None,'saved':None}
    else:
     comments,interactions,likes,reach,saved,shares,views=map(number,row[3:])
     values={'comments':comments,'interactions':interactions,'likes':likes,'reach':reach,'saved':saved,'shares':shares,'views':views,'clicks':None,'impressions':None}
    measured[p.id]={**values,'source':'Metricool','fetched_at':s.fetched_at,'source_url':url,'match':match}
  return {'posts':[{'id':p.id,'title':p.title,'channel':p.channel,'campaign_id':p.campaign_id,'published_at':p.published_at,'publication_url':p.publication_url,'analytics':measured.get(p.id)} for p in posts], 'campaigns':[{'id':c.id,'name':c.name} for c in db.query(SocialCampaign)],'accounts':sorted(accounts,key=lambda x:x['date']),'snapshots':[{'key':s.key,'fetched_at':s.fetched_at,'from':s.range_from,'to':s.range_to,'rows':len(s.payload['rows'])} for s in snapshots.values()],'unmatched_rows':unmatched}
