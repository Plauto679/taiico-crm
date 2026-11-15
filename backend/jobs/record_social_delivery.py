import json,sys
from services.social_media import *
doc=json.load(sys.stdin);v=doc['response'];pid=doc['post_id']
with SessionLocal() as db:
 p=get_post(db,pid)
 if db.get(SocialDelivery,pid):raise ValueError('Entrega existente')
 if p.status!='listo' or p.revision!=doc['revision']:raise ValueError('La pieza cambió; reconciliar envío antes de continuar')
 db.add(SocialDelivery(post_id=pid,provider_id=str(v['id']),planner_url=v['plannerUrl'],scheduled_at=doc['scheduled_at'],recorded_at=now(),response=v))
 change(db,p,p.revision,{'status':'programado'},OWNER,'programación confirmada en Metricool')
 print(pid,str(v['id']))
