"""Agent audience and survey drafts for campaign review (no outbound delivery)."""
import hashlib
import re
from datetime import date

from services.agentes import load_agents_directory

AI_SURVEY = {
    "title": "¿Cómo puede la IA ayudarte en tu operación?",
    "description": "Queremos desarrollar herramientas de TAIICO a partir de tus necesidades reales. Responder toma aproximadamente 3 minutos.",
    "questions": [
        {"id": "priorities", "type": "multiple", "required": True, "max_choices": 3,
         "label": "¿En cuáles tareas te gustaría recibir apoyo de una herramienta de IA de TAIICO? Elige hasta 3.",
         "options": ["Llenar solicitudes y formatos", "Preparar y comparar cotizaciones", "Dar seguimiento a renovaciones", "Redactar mensajes y dar seguimiento a clientes", "Dar seguimiento a cobranza y pagos", "Revisar documentos y requisitos", "Consultar productos, coberturas y condiciones", "Organizar pendientes y recordatorios", "Dar seguimiento a trámites y siniestros", "Prospectar y preparar propuestas de venta", "Otra tarea", "Por ahora no necesito apoyo de IA"],
         "exclusive_option": "Por ahora no necesito apoyo de IA"},
        {"id": "first", "type": "text", "required": False, "max_length": 500,
         "label": "De las tareas que elegiste, ¿cuál deberíamos resolver primero y por qué?"},
        {"id": "time", "type": "single", "required": True,
         "label": "Aproximadamente, ¿cuánto tiempo a la semana dedicas a esas tareas?",
         "options": ["Menos de 1 hora", "De 1 a menos de 3 horas", "De 3 a menos de 5 horas", "De 5 a 10 horas", "Más de 10 horas", "No lo sé / No aplica"]},
        {"id": "open", "type": "text", "required": False, "max_length": 2000,
         "label": "¿Qué otra tarea te gustaría facilitar? Puedes describir un caso concreto y cómo te gustaría que te ayudáramos."},
        {"id": "pilot", "type": "single", "required": True,
         "label": "¿Te gustaría participar en una prueba de las herramientas que desarrollemos?",
         "options": ["Sí, pueden contactarme", "Tal vez, quiero conocer más", "Por ahora no"]},
    ],
}


CONTACT_SURVEY = {
    "title": "Actualiza tu teléfono y mantente conectado con Taiico",
    "description": "Comparte tu número con código de país (México: +52 y 10 dígitos). Actualizar tu teléfono no te obliga a recibir mensajes por WhatsApp. Puedes solicitar cambiar tu preferencia posteriormente.",
    "header_title": "Mantengamos el contacto",
    "header_description": "Información relevante para tu actividad como asesor.",
    "success_title": "Gracias por actualizar tus datos",
    "success_description": "Registramos tu número y tu preferencia de comunicación.",
    "privacy_url": "https://taiico.com/aviso-de-privacidad/",
    "version": "agent-contact-v1",
    "questions": [
        {"id": "phone", "type": "text", "format": "phone", "required": True, "max_length": 30,
         "label": "Número de teléfono con código de país. Ejemplo: +52 55 1234 5678"},
        {"id": "has_whatsapp", "type": "single", "required": True,
         "label": "¿Este número tiene WhatsApp?", "options": ["Sí", "No"]},
        {"id": "whatsapp_consent", "type": "single", "required": True,
         "label": "¿Deseas recibir por WhatsApp información de Taiico sobre capacitaciones, herramientas, novedades y avisos operativos?",
         "options": ["Sí", "No"]},
    ],
}

SURVEYS_BY_TYPE = {"agentes_encuesta_ia": AI_SURVEY, "agentes_actualizacion_datos": CONTACT_SURVEY}


def build_agent_audience(*, promotoria=None):
    agents = load_agents_directory()["agents"]
    if promotoria is not None:
        # Filter before deduplication; missing or mixed affiliations never match.
        agents = [agent for agent in agents
                  if str(agent.get("promotoria") or "").strip().upper() == promotoria.strip().upper()]
    rows, seen = [], set()
    for agent in agents:
        # RFC/agent keys identify people. Never combine different agents merely
        # because they share an email; retain them for review.
        identity = agent.get("rfc") or agent.get("clave_definitiva") or agent.get("clave_arranque") or f"row:{agent['row_number']}"
        identity = str(identity).strip().upper()
        if identity in seen:
            continue
        seen.add(identity)
        email = str(agent.get("correo_personal") or "").strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            email = ""
        rows.append({"key": "agent:" + hashlib.sha256(identity.encode()).hexdigest(),
                     "source_row": agent["row_number"], "nombre_cliente": agent["nombre"],
                     "agente": agent["nombre"], "rfc": agent.get("rfc", ""), "email": email,
                     "recibir_comunicaciones": agent.get("recibir_comunicaciones", True),
                     "promotoria": agent.get("promotoria", ""), "numero_poliza": "",
                     "nombre_producto": "", "fecha_fin_vigencia": "", "deducible": 0,
                     "multiple_policies": False})
    return {"rows": rows, "summary": {"policies": len(rows), "unique_clients": len(rows),
            "clients_with_email": sum(bool(r["email"]) for r in rows),
            "clients_missing_email": sum(not r["email"] for r in rows),
            "clients_with_multiple_policies": 0, "rows_without_rfc": sum(not r["rfc"] for r in rows),
            "source_records": len(agents), "duplicate_records": len(agents)-len(rows)},
            "generated_on": date.today().isoformat(), "segment": {"source": "agentes", "vigencia": "todos", "deducible_minimo": 0, "promotoria": promotoria}}

# Public bearer links contain no agent identity. Test responses are isolated.
import secrets
from datetime import datetime, timedelta
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from database import Campaign, CampaignSurveyResponse, SessionLocal
from services.authorization import require_module_access

router = APIRouter(tags=['campaign-surveys'])
SURVEY_MARKER = '[Enlace a la encuesta: pendiente de habilitar tras la revisión]'


def survey_link(db, campaign, row, *, is_test=False):
    key = ('test:' + secrets.token_hex(12)) if is_test else str(row['key'])
    invite = db.query(CampaignSurveyResponse).filter_by(campaign_id=campaign.id, recipient_key=key).first()
    if not invite:
        invite = CampaignSurveyResponse(id=secrets.token_urlsafe(32), campaign_id=campaign.id,
            recipient_key=key, recipient_name=str(row.get('nombre_cliente') or 'Prueba interna'),
            is_test=is_test, questionnaire=campaign.segment_json['encuesta'],
            expires_at=datetime.utcnow()+timedelta(days=90))
        db.add(invite)
        db.flush()
    return 'https://taiico-crm.com/encuesta/' + invite.id


def invitation_body(body, link):
    return body.replace(SURVEY_MARKER, link) if SURVEY_MARKER in body else body + '\n\nResponde la encuesta: ' + link


def get_invite(db, token):
    if len(token) > 64:
        raise HTTPException(404, 'Enlace no disponible')
    invite=db.get(CampaignSurveyResponse,token)
    if not invite or invite.expires_at < datetime.utcnow():
        raise HTTPException(404,'Este enlace no está disponible o ha caducado.')
    return invite


class SurveySubmission(BaseModel):
    answers: dict[str, str | list[str]] = Field(max_length=10)


def validate_answers(questionnaire, answers):
    questions=questionnaire['questions']
    if set(answers)-{q['id'] for q in questions}:
        raise HTTPException(422,'Hay preguntas desconocidas.')
    cleaned={}
    for q in questions:
        value=answers.get(q['id'], [] if q['type']=='multiple' else '')
        if q['type']=='multiple':
            if not isinstance(value,list) or any(v not in q['options'] for v in value) or len(value)!=len(set(value)) or len(value)>q['max_choices']:
                raise HTTPException(422,'Selecciona hasta tres opciones válidas, sin repetir.')
            if q.get('exclusive_option') in value and len(value)>1:
                raise HTTPException(422,'La opción de no necesitar apoyo debe seleccionarse sola.')
        else:
            if not isinstance(value,str): raise HTTPException(422,'Respuesta inválida.')
            value=value.strip()
            if len(value)>q.get('max_length',500): raise HTTPException(422,'Respuesta demasiado larga.')
            if q.get('format') == 'phone' and value:
                value = re.sub(r'[\s().-]', '', value)
                if not re.fullmatch(r'\+[1-9][0-9]{7,14}', value):
                    raise HTTPException(422, 'Escribe un teléfono válido con + y código de país.')
                if value.startswith('+52') and len(value) != 13:
                    raise HTTPException(422, 'Para México escribe +52 seguido de 10 dígitos.')
            if q['type']=='single' and value and value not in q['options']: raise HTTPException(422,'Selecciona una opción válida.')
        if q.get('required') and not value: raise HTTPException(422,'Responde las preguntas obligatorias.')
        cleaned[q['id']]=value
    if questionnaire.get('version') == 'agent-contact-v1' and cleaned.get('has_whatsapp') == 'No' and cleaned.get('whatsapp_consent') == 'Sí':
        raise HTTPException(422, 'Para recibir mensajes por WhatsApp indica un número que tenga WhatsApp o selecciona No en la autorización.')
    return cleaned


@router.get('/encuestas/{token}')
def public_survey(token: str):
    with SessionLocal() as db:
        invite=get_invite(db,token)
        return {'questionnaire':invite.questionnaire,'is_test':invite.is_test,'submitted':invite.submitted_at is not None}


@router.post('/encuestas/{token}')
def submit_survey(token: str, payload: SurveySubmission):
    with SessionLocal() as db:
        invite=get_invite(db,token)
        answers=validate_answers(invite.questionnaire,payload.answers)
        updated=db.query(CampaignSurveyResponse).filter_by(id=invite.id,submitted_at=None).update(
            {'answers':answers,'submitted_at':datetime.utcnow()},synchronize_session=False)
        if not updated: raise HTTPException(409,'Ya recibimos una respuesta con este enlace.')
        db.commit()
        return {'saved':True,'is_test':invite.is_test}


@router.post('/campanas/{campaign_id}/survey-preview')
def survey_preview(campaign_id: str, profile=Depends(require_module_access('campanas',operation=True))):
    with SessionLocal() as db:
        campaign=db.get(Campaign,campaign_id)
        if not campaign or not (campaign.segment_json or {}).get('encuesta'): raise HTTPException(404,'Encuesta no encontrada')
        link=survey_link(db,campaign,{'nombre_cliente':'Prueba interna'},is_test=True)
        db.commit()
        return {'url':link}


@router.get('/campanas/{campaign_id}/survey-results')
def survey_results(campaign_id: str, profile=Depends(require_module_access('campanas'))):
    with SessionLocal() as db:
        rows=db.query(CampaignSurveyResponse).filter_by(campaign_id=campaign_id,is_test=False).all()
        answered=[r for r in rows if r.submitted_at]
        counts=Counter(option for r in answered for option in r.answers.get('priorities',[]))
        return {'invited':len(rows),'responded':len(answered),'priorities':dict(counts),
            'responses':[{'name':r.recipient_name,'answers':r.answers,'submitted_at':r.submitted_at.isoformat()} for r in answered]}
