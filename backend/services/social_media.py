"""Private editorial workspace. Planned dates are not provider scheduling."""
from __future__ import annotations
import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from PIL import Image, UnidentifiedImageError
from sqlalchemy import Column, String, Integer, Text, JSON, ForeignKey, update
from database import Base, SessionLocal, engine
from services.authorization import current_access_profile
from services.auth import AccessProfile

OWNER = 'alberto.alfaro@taiico.com'
ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / '.runtime' / 'social-media-assets'

def available(profile: AccessProfile) -> bool:
    return profile.can_read('redes_sociales') and 'TAIICO' in profile.promotorias

def require_read(profile: AccessProfile = Depends(current_access_profile)):
    if not available(profile):
        raise HTTPException(403, 'No tienes acceso a Redes sociales de Taiico')
    return profile

def require_operation(profile: AccessProfile = Depends(require_read)):
    if not profile.can_operate('redes_sociales'):
        raise HTTPException(403, 'Necesitas permiso de Operación en Redes sociales')
    return profile

router = APIRouter(prefix='/redes-sociales', tags=['redes-sociales'], dependencies=[Depends(require_read)])
def now(): return datetime.now(timezone.utc).isoformat()

class SocialCampaign(Base):
    __tablename__ = 'social_campaigns'
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    objective = Column(Text, nullable=False)
    created_at = Column(String, nullable=False)

class SocialPost(Base):
    __tablename__ = 'social_posts'
    id = Column(String, primary_key=True)
    campaign_id = Column(String, ForeignKey('social_campaigns.id'), nullable=False, index=True)
    title = Column(String, nullable=False)
    channel = Column(String, nullable=False)
    copy = Column(Text, nullable=False, default='')
    status = Column(String, nullable=False, default='revision')
    planned_at = Column(String, nullable=False, default='')
    landing_url = Column(Text, nullable=False, default='')
    notes = Column(Text, nullable=False, default='')
    asset_id = Column(String, nullable=True)
    revision = Column(Integer, nullable=False, default=1)
    publication_url = Column(Text, nullable=False, default='')
    published_at = Column(String, nullable=True)
    metrics = Column(JSON, nullable=True)
    updated_at = Column(String, nullable=False)

class SocialAsset(Base):
    __tablename__ = 'social_assets'
    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    created_at = Column(String, nullable=False)

class SocialEvent(Base):
    __tablename__ = 'social_events'
    id = Column(String, primary_key=True)
    post_id = Column(String, nullable=False, index=True)
    username = Column(String, nullable=False)
    action = Column(String, nullable=False)
    at = Column(String, nullable=False)
    snapshot = Column(JSON, nullable=False)

class SocialDelivery(Base):
    __tablename__ = 'social_deliveries'
    post_id = Column(String, ForeignKey('social_posts.id'), primary_key=True)
    provider_id = Column(String, nullable=False, unique=True)
    planner_url = Column(Text, nullable=False)
    scheduled_at = Column(String, nullable=False)
    recorded_at = Column(String, nullable=False)
    response = Column(JSON, nullable=False)

def init_schema():
    Base.metadata.create_all(engine, tables=[SocialCampaign.__table__, SocialAsset.__table__, SocialPost.__table__, SocialEvent.__table__, SocialDelivery.__table__])

def serialize(row): return {c.name: getattr(row,c.name) for c in row.__table__.columns}
def serialize_post(db, post):
    data = serialize(post)
    delivery = db.get(SocialDelivery, post.id)
    data['delivery'] = {k:getattr(delivery,k) for k in ('provider_id','planner_url','scheduled_at','recorded_at')} if delivery else None
    return data

def event(db, post, username, action):
    db.add(SocialEvent(id=str(uuid.uuid4()), post_id=post.id, username=username, action=action, at=now(), snapshot=serialize(post)))
def get_post(db, id):
    p=db.get(SocialPost,id)
    if not p: raise HTTPException(404,'Publicación no encontrada')
    return p

def https_url(value):
    if value and (urlparse(value).scheme != 'https' or not urlparse(value).hostname or urlparse(value).username):
        raise ValueError('Usa un enlace HTTPS válido')
    return value

class CampaignInput(BaseModel):
    name: str = Field(min_length=1,max_length=160)
    objective: str = Field(min_length=1,max_length=2000)
    @field_validator('name','objective')
    @classmethod
    def not_blank(cls,v):
        if not v.strip(): raise ValueError('Campo obligatorio')
        return v.strip()

class PostInput(BaseModel):
    title: str = Field(min_length=1,max_length=160)
    channel: Literal['facebook','instagram']
    copy: str = Field(default='',max_length=63206)
    status: Literal['borrador','revision','listo'] = 'revision'
    planned_at: str = ''
    landing_url: str = Field(default='',max_length=2048)
    notes: str = Field(default='',max_length=5000)
    asset_id: str | None = None
    @field_validator('title')
    @classmethod
    def title_valid(cls,v):
        if not v.strip(): raise ValueError('Título obligatorio')
        return v.strip()
    @field_validator('landing_url')
    @classmethod
    def url_valid(cls,v): return https_url(v)
    @field_validator('planned_at')
    @classmethod
    def date_valid(cls,v):
        if v:
            d=datetime.fromisoformat(v.replace('Z','+00:00'))
            if d.tzinfo is None: raise ValueError('Incluye zona horaria')
        return v

class PostEdit(PostInput):
    revision: int = Field(ge=1)

class PublishRecord(BaseModel):
    revision: int = Field(ge=1)
    publication_url: str = Field(max_length=2048)
    published_at: str

class MetricsInput(BaseModel):
    revision: int = Field(ge=1)
    reach: int = Field(ge=0)
    impressions: int = Field(ge=0)
    interactions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    notes: str = Field(default='',max_length=1000)

def validate_content(db,payload):
    if payload.channel=='instagram' and len(payload.copy)>2200: raise HTTPException(422,'Instagram admite hasta 2,200 caracteres en el copy')
    if payload.asset_id and not db.get(SocialAsset,payload.asset_id): raise HTTPException(422,'Arte no encontrado')
    if payload.status=='listo' and (not payload.copy.strip() or not payload.asset_id): raise HTTPException(422,'Completa el copy y el arte antes de marcar como listo')

def change(db,p,revision,values,username,action,editable=False):
    if p.revision!=revision: raise HTTPException(409,'La publicación cambió. Recarga para no sobrescribir otra edición')
    if editable and p.status in ('publicado','programado'): raise HTTPException(409,'Esta publicación ya fue enviada a la red. Cambia primero su programación en Metricool')
    values.update(revision=revision+1,updated_at=now())
    result=db.execute(update(SocialPost).where(SocialPost.id==p.id,SocialPost.revision==revision).values(**values))
    if result.rowcount!=1: raise HTTPException(409,'La publicación cambió. Recarga e inténtalo de nuevo')
    db.refresh(p);event(db,p,username,action);db.commit();return serialize(p)

@router.get('')
def overview(profile=Depends(require_read)):
    with SessionLocal() as db:
        return {'can_operate':profile.can_operate('redes_sociales'), 'campaigns':[serialize(c) for c in db.query(SocialCampaign).order_by(SocialCampaign.created_at.desc())], 'posts':[serialize_post(db,p) for p in db.query(SocialPost).order_by(SocialPost.planned_at,SocialPost.id)], 'integration':{'provider':'Metricool','connected':False,'message':'Listo autoriza el envío por nuestro asistente. Programado confirma que Metricool recibió la publicación. Los estados y métricas no se sincronizan automáticamente; guardar aquí no envía contenido a las redes.'},'monthly_limit':20}

@router.post('/campaigns')
def create_campaign(payload:CampaignInput, profile=Depends(require_operation)):
    with SessionLocal() as db:
        c=SocialCampaign(id=str(uuid.uuid4()),created_at=now(),**payload.model_dump());db.add(c);db.commit();return serialize(c)

@router.post('/campaigns/{id}/posts')
def create_post(id:str,payload:PostInput,profile=Depends(require_operation)):
    with SessionLocal() as db:
        if not db.get(SocialCampaign,id): raise HTTPException(404,'Campaña no encontrada')
        validate_content(db,payload)
        p=SocialPost(id=str(uuid.uuid4()),campaign_id=id,updated_at=now(),revision=1,publication_url='',**payload.model_dump());db.add(p);db.flush();event(db,p,profile.username,'creado');db.commit();return serialize(p)

@router.put('/posts/{id}')
def edit_post(id:str,payload:PostEdit,profile=Depends(require_operation)):
    with SessionLocal() as db:
        p=get_post(db,id);validate_content(db,payload)
        return change(db,p,payload.revision,payload.model_dump(exclude={'revision'}),profile.username,'edición',True)

@router.post('/posts/{id}/publication')
def record_publication(id:str,payload:PublishRecord,profile=Depends(require_operation)):
    with SessionLocal() as db:
        p=get_post(db,id)
        if p.status=='publicado': raise HTTPException(409,'La publicación ya está registrada')
        try:
            https_url(payload.publication_url)
            host=urlparse(payload.publication_url).hostname or ''
            domain='facebook.com' if p.channel=='facebook' else 'instagram.com'
            if host!=domain and not host.endswith('.'+domain): raise ValueError()
            if urlparse(payload.publication_url).path in ('','/'): raise ValueError()
            dt=datetime.fromisoformat(payload.published_at.replace('Z','+00:00'))
            if dt.tzinfo is None or dt>datetime.now(timezone.utc): raise ValueError()
        except ValueError: raise HTTPException(422,'Indica el enlace de la publicación en su red y una fecha de publicación válida, no futura')
        return change(db,p,payload.revision,{'status':'publicado','publication_url':payload.publication_url,'published_at':dt.isoformat()},profile.username,'publicación registrada manualmente')

@router.put('/posts/{id}/metrics')
def metrics(id:str,payload:MetricsInput,profile=Depends(require_operation)):
    with SessionLocal() as db:
        p=get_post(db,id)
        if p.status!='publicado': raise HTTPException(409,'Registra primero la publicación')
        values=payload.model_dump(exclude={'revision'});values.update(source='manual',recorded_at=now())
        return change(db,p,payload.revision,{'metrics':values},profile.username,'métricas manuales')

@router.get('/posts/{id}/history')
def history(id:str):
    with SessionLocal() as db:
        get_post(db,id)
        return [serialize(e) for e in db.query(SocialEvent).filter_by(post_id=id).order_by(SocialEvent.at.desc())]

@router.post('/assets')
async def upload(file:UploadFile=File(...), profile=Depends(require_operation)):
    data=await file.read(10*1024*1024+1)
    if len(data)>10*1024*1024: raise HTTPException(413,'Máximo 10 MB por imagen')
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in ('PNG','JPEG','WEBP') or im.width*im.height>25_000_000: raise ValueError()
            im.load();image=im.convert('RGBA')
    except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError): raise HTTPException(422,'Usa una imagen PNG, JPG o WebP válida de hasta 25 megapíxeles')
    ASSETS.mkdir(parents=True,exist_ok=True);id=str(uuid.uuid4());image.save(ASSETS/f'{id}.png')
    with SessionLocal() as db:
        db.add(SocialAsset(id=id,filename=(file.filename or 'arte')[:200],created_at=now()));db.commit()
    return {'id':id}

@router.get('/assets/{id}')
def asset(id:str):
    with SessionLocal() as db:
        if not db.get(SocialAsset,id): raise HTTPException(404,'Arte no encontrado')
    path=ASSETS/f'{id}.png'
    if not path.is_file(): raise HTTPException(404,'Archivo no disponible')
    return FileResponse(path,media_type='image/png',headers={'Cache-Control':'private, no-store'})

@router.get('/results')
def publication_results():
    from services.social_results import results
    return results()
