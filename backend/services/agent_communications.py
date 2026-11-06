"""Persistent agent opt-outs, enforced again immediately before outbound mail."""
import hashlib
from datetime import datetime
from email.utils import getaddresses
from database import SessionLocal, AgentCommunicationPreference, CampaignDelivery

class CommunicationOptOutError(RuntimeError):
    pass

def agent_key(agent):
    for field in ('rfc','clave_definitiva','clave_arranque'):
        value=str(agent.get(field) or '').strip().upper()
        if value:return field+':'+value
    return 'nombre:'+hashlib.sha256(str(agent.get('nombre') or '').strip().upper().encode()).hexdigest()

def blocked_emails():
    with SessionLocal() as db:
        return {email for p in db.query(AgentCommunicationPreference).filter_by(enabled=False) for email in p.emails}

def filter_recipients(recipients):
    blocked=blocked_emails()
    return [address for _,address in getaddresses(recipients) if address.strip().casefold() not in blocked]

def apply_preferences(directory):
    with SessionLocal() as db:
        prefs={p.agent_key:p.enabled for p in db.query(AgentCommunicationPreference)}
    for agent in directory['agents']:
        agent['recibir_comunicaciones']=prefs.get(agent_key(agent),True)
    return directory

def set_preference(agent, enabled, actor):
    with SessionLocal() as db:
        key=agent_key(agent);row=db.get(AgentCommunicationPreference,key)
        if not row:
            row=AgentCommunicationPreference(agent_key=key,agent_name=agent['nombre'],emails=[],enabled=True,history=[]);db.add(row)
        previous=row.enabled
        row.enabled=enabled
        row.emails=sorted(set(row.emails or [])|{str(agent.get('correo_personal') or '').strip().casefold()}-{''})
        row.history=[*(row.history or []),{'at':datetime.utcnow().isoformat(),'actor':actor,'previous':previous,'enabled':enabled}]
        if not enabled:
            db.query(CampaignDelivery).filter(CampaignDelivery.email.in_(row.emails),CampaignDelivery.status.in_(['pendiente','enviando'])).update({'status':'excluido_comunicaciones','error_detail':'El agente solicitó no recibir comunicaciones.'},synchronize_session=False)
        db.commit()

def sync_identity(old_agent,new_agent):
    with SessionLocal() as db:
        row=db.get(AgentCommunicationPreference,agent_key(old_agent))
        if row:
            row.agent_key=agent_key(new_agent);row.agent_name=new_agent['nombre']
            row.emails=sorted(set(row.emails or [])|{str(new_agent.get('correo_personal') or '').strip().casefold()}-{''})
            db.commit()
