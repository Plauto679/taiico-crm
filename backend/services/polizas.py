"""Central policy registry. Existing Policy/Client IDs and commission assignments are preserved."""
from __future__ import annotations
import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, or_, false, text
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from database import SessionLocal, Policy, Client, Product, Renewal, PolicyProspectorAssignment, Prospector, AgentAction, Document
from services.auth import AccessProfile
from services.authorization import require_module_access
from services.client_promotorias import scope_client_query
from services.agent_scope import profile_policy_numbers, profile_allows_insurer
from services.client_folders import normalize_rfc, valid_client_rfc

router = APIRouter(prefix='/polizas', tags=['polizas'])
read_access = require_module_access('polizas')
write_access = require_module_access('polizas', operation=True)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def policy_key(value):
    # Used only to flag possible duplicates, never to silently merge records.
    return re.sub(r'[^A-Z0-9]', '', str(value).upper()).lstrip('0') or '0'


def scoped(db, profile):
    query = db.query(Policy)
    if profile.is_central_admin:
        return query
    if profile.is_agent:
        numbers = profile_policy_numbers(profile) or ()
        query = query.filter(Policy.policy_number.in_(numbers)) if numbers else query.filter(false())
        insurers = [p[0] for p in db.query(Policy.insurer_id).distinct() if profile_allows_insurer(profile, p[0])]
        return query.filter(Policy.insurer_id.in_(insurers))
    clients = scope_client_query(db.query(Client), profile).with_entities(Client.id)
    return query.filter(Policy.client_id.in_(clients))


def get_policy(db, profile, policy_id):
    policy = scoped(db, profile).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(404, 'Póliza no encontrada o fuera de tu alcance')
    return policy


def snapshot(p):
    return dict(policy_number=p.policy_number, client_id=p.client_id, insurer_id=p.insurer_id, product_id=p.product_id,
                effective_start_date=p.effective_start_date.isoformat(), effective_end_date=p.effective_end_date.isoformat(),
                premium_amount=str(p.premium_amount), payment_frequency=p.payment_frequency, status=p.status,
                document_link=p.document_link or '', registry=(p.metadata_json or {}).get('registry', {}))


def event(db, profile, policy, before, source):
    db.add(AgentAction(agent_name='policy_registry', action_type='policy_registry_change', status='completed',
        description=source, input_payload={'policy_id': policy.id, 'actor': profile.username, 'before': before},
        output_payload={'after': snapshot(policy)}))


def serialize(p, duplicate_rfcs=None, possible_numbers=None, *, full=True):
    c=p.client
    issues=[]
    rfc=normalize_rfc(c.rfc) if c else ''
    if not c or not valid_client_rfc(rfc): issues.append('Cliente sin RFC válido: identidad por revisar')
    if c and normalize_rfc((c.metadata_json or {}).get('source_rfc')) not in {'',rfc}: issues.append('El RFC de una fuente difiere del cliente vinculado')
    if duplicate_rfcs and rfc in duplicate_rfcs: issues.append('RFC compartido por varios registros: homologar en Clientes')
    if not p.document_link: issues.append('Expediente de póliza sin vincular')
    if possible_numbers and (p.insurer_id,policy_key(p.policy_number)) in possible_numbers: issues.append('Posible variante duplicada del número de póliza')
    registry=(p.metadata_json or {}).get('registry',{})
    if registry.get('source_conflicts'): issues.append('Una carga de base propone cambios sobre datos validados')
    return {'id':p.id, **snapshot(p), 'client_name':c.full_name if c else '', 'rfc':rfc,
        'client_folder':c.drive_folder_url if c else None, 'insurer':p.insurer.name if p.insurer else p.insurer_id,
        'branch':p.product.branch if p.product else '', 'product':p.product.name if p.product else '',
        'issues':issues, 'fingerprint':digest(snapshot(p)) if full else '', 'agent':registry.get('agent','') or (p.metadata_json or {}).get('agent_name',''),
        'created_at':str(p.created_at), 'updated_at':str(p.updated_at), 'origin':(p.metadata_json or {}).get('created_from','Registro existente')}


class PolicyInput(BaseModel):
    policy_number: str = Field(min_length=1,max_length=100)
    rfc: str = Field(min_length=12,max_length=20)
    product_id: str = Field(min_length=1,max_length=36)
    effective_start_date: date
    effective_end_date: date
    premium_amount: Decimal = Field(ge=0,max_digits=12,decimal_places=2)
    payment_frequency: Literal['monthly','quarterly','semi_annual','annual','single','unknown']='annual'
    status: Literal['in_force','lapsed','cancelled','renewed']='in_force'
    document_link: str = Field(default='',max_length=500)
    agent: str = Field(default='',max_length=255)
    insured_names: list[str] = Field(default_factory=list,max_length=100)
    emission_row: int | None = Field(default=None,ge=2)
    emission_fingerprint: str | None = None

    @field_validator('policy_number')
    @classmethod
    def trim_number(cls,value):
        if not value.strip(): raise ValueError('Captura el número de póliza')
        return value.strip()

    @field_validator('rfc')
    @classmethod
    def check_rfc(cls,value):
        value=normalize_rfc(value)
        if not valid_client_rfc(value) or value in {'XAXX010101000','XEXX010101000'}: raise ValueError('Usa el RFC propio del cliente, no uno genérico')
        return value

    @field_validator('document_link')
    @classmethod
    def check_link(cls,value):
        if value and (urlparse(value).scheme != 'https' or not urlparse(value).netloc): raise ValueError('El expediente debe ser un enlace HTTPS')
        return value.strip()

    @field_validator('insured_names')
    @classmethod
    def check_names(cls,value):
        if any(len(name)>255 for name in value): raise ValueError('Nombre de asegurado demasiado largo')
        return list(dict.fromkeys(name.strip() for name in value if name.strip()))

    @model_validator(mode='after')
    def dates(self):
        if self.effective_end_date <= self.effective_start_date: raise ValueError('El fin de vigencia debe ser posterior al inicio')
        return self


class PolicyEdit(BaseModel):
    fingerprint: str
    data: PolicyInput


def resolve_client(db, profile, rfc):
    # Require an existing canonical client. Never create or merge clients by name.
    index=db.info.get('policy_registry_clients_by_rfc')
    if index is None:
        index={}
        for item in db.query(Client).filter(Client.rfc.isnot(None)):
            index.setdefault(normalize_rfc(item.rfc),[]).append(item)
        db.info['policy_registry_clients_by_rfc']=index
    matches=index.get(rfc,[])
    if len(matches)!=1: raise HTTPException(409, 'RFC sin cliente único. Registra u homologa al cliente en Clientes antes de continuar.')
    client=matches[0]
    if not scope_client_query(db.query(Client),profile).filter(Client.id==client.id).first(): raise HTTPException(403,'Cliente fuera de tu alcance')
    if client.status=='inactive': raise HTTPException(409,'El cliente está inactivo; revisa su identidad en Clientes')
    return client


def validate_input(db,profile,data):
    client=resolve_client(db,profile,data.rfc)
    product=db.get(Product,data.product_id)
    if not product or not profile_allows_insurer(profile,product.insurer_id): raise HTTPException(422,'Producto o aseguradora no disponible')
    return client,product


def validate_emission(data, profile):
    if not data.emission_row: return None
    from services.pendientes import SOURCES, load_pending_source, _filter_source_for_profile
    source=_filter_source_for_profile(load_pending_source(SOURCES['emision-servicios']),profile)
    row=next((r for r in source['rows'] if r['source_row']==data.emission_row),None)
    if not row or digest(row)!=data.emission_fingerprint: raise HTTPException(409,'La emisión cambió. Vuelve a seleccionarla.')
    summary=row['summary']
    if str(summary.get('Estatus actual','')).strip().casefold()!='concluido': raise HTTPException(409,'La emisión debe estar concluida')
    if 'emisi' not in str(summary.get('Solicitud de','')).casefold() and 'emisi' not in str(summary.get('Casificacion','')).casefold(): raise HTTPException(409,'El registro no corresponde a una emisión')
    source_rfc=normalize_rfc(summary.get('RFC',''))
    if source_rfc and source_rfc!=data.rfc: raise HTTPException(409,'El RFC no coincide con el de la emisión')
    source_number=str(summary.get('Póliza') or summary.get('Poliza') or '').strip()
    if source_number and source_number!=data.policy_number: raise HTTPException(409,'El número no coincide con la emisión')
    return {'source':'emision-servicios','source_row':data.emission_row,'fingerprint':digest(row),'summary':summary}


def create_policy(db,profile,data,source='Alta manual',emission=None):
    client,product=validate_input(db,profile,data)
    if db.query(Policy).filter(Policy.policy_number==data.policy_number).first(): raise HTTPException(409,'Ese número ya existe; utiliza la conciliación para revisar la coincidencia')
    variants=db.query(Policy.policy_number).filter(Policy.insurer_id==product.insurer_id).all()
    if any(policy_key(n[0])==policy_key(data.policy_number) for n in variants): raise HTTPException(409,'Existe una variante del número; revisa la posible duplicidad antes de darla de alta')
    policy=Policy(policy_number=data.policy_number,client_id=client.id,insurer_id=product.insurer_id,product_id=product.id,
        effective_start_date=data.effective_start_date,effective_end_date=data.effective_end_date,premium_amount=data.premium_amount,
        payment_frequency=data.payment_frequency,status=data.status,document_link=data.document_link or None,
        responsible_user_id=client.responsible_user_id,
        metadata_json={'created_from':source,'registry':{'agent':data.agent,'insured_names':data.insured_names,'emission':emission,'validated':True}})
    db.add(policy);db.flush();event(db,profile,policy,None,source)
    return policy


def update_policy(db,profile,policy,data,source):
    client,product=validate_input(db,profile,data)
    if (client.id,product.id,data.policy_number)!=(policy.client_id,policy.product_id,policy.policy_number):
        raise HTTPException(409,'La identidad de la póliza no se cambia por conciliación. Revisa cliente, producto y número.')
    before=snapshot(policy)
    for key in ('effective_start_date','effective_end_date','premium_amount','payment_frequency','status'):
        setattr(policy,key,getattr(data,key))
    policy.document_link=data.document_link or None
    metadata=dict(policy.metadata_json or {})
    metadata['registry']={**metadata.get('registry',{}),'agent':data.agent,'insured_names':data.insured_names,'validated':True,'source_conflicts':[]}
    policy.metadata_json=metadata
    db.flush();event(db,profile,policy,before,source)


def write_lock(db):
    # Serialize previews/apply/create within SQLite, including concurrent RFC lookups.
    if db.bind.dialect.name=='sqlite': db.execute(text('BEGIN IMMEDIATE'))


@router.get('/options')
def options(profile:AccessProfile=Depends(read_access)):
    with SessionLocal() as db:
        return {'can_operate':profile.can_operate('polizas'),'products':[{'id':p.id,'name':p.name,'branch':p.branch,'insurer_id':p.insurer_id} for p in db.query(Product).order_by(Product.name) if profile_allows_insurer(profile,p.insurer_id)]}


@router.get('/client')
def client_by_rfc(rfc:str,profile:AccessProfile=Depends(read_access)):
    with SessionLocal() as db:
        c=resolve_client(db,profile,normalize_rfc(rfc))
        return {'id':c.id,'name':c.full_name,'rfc':c.rfc,'folder':c.drive_folder_url}


@router.get('')
def inventory(q:str=Query('',max_length=200), review:bool=False, insurer:str=Query('',max_length=50), page:int=Query(1,ge=1), profile:AccessProfile=Depends(read_access), branch:str=Query('',max_length=100)):
    with SessionLocal() as db:
        base=scoped(db,profile)
        if insurer: base=base.filter(Policy.insurer_id==insurer)
        if branch.strip(): base=base.filter(Policy.product.has(Product.branch==branch.strip()))
        if q.strip():
            term=f'%{q.strip()}%'
            base=base.join(Client).filter(or_(Policy.policy_number.ilike(term),Client.full_name.ilike(term),Client.rfc.ilike(term)))
        # Review is computed from the same scoped inventory, so no unscoped identities leak.
        rows=base.options(joinedload(Policy.client),joinedload(Policy.product),joinedload(Policy.insurer)).order_by(Policy.updated_at.desc(),Policy.id).all()
        rfc_clients={}
        for client_id,client_rfc in scope_client_query(db.query(Client),profile).with_entities(Client.id,Client.rfc):
            rfc=normalize_rfc(client_rfc)
            if rfc:rfc_clients.setdefault(rfc,set()).add(client_id)
        duplicate_rfcs={r for r,ids in rfc_clients.items() if len(ids)>1}
        keys=Counter((p.insurer_id,policy_key(p.policy_number)) for p in rows)
        variants={key for key,count in keys.items() if count>1}
        serialized=[serialize(p,duplicate_rfcs,variants,full=False) for p in rows]
        review_count=sum(bool(p['issues']) for p in serialized)
        filtered=[p for p in serialized if p['issues']] if review else serialized
        return {'rows':filtered[(page-1)*50:page*50],'total':len(filtered),'inventory_total':len(rows),'review_count':review_count,'page':page,'pages':max(1,(len(filtered)+49)//50)}


@router.get('/emissions')
def emissions(profile:AccessProfile=Depends(write_access)):
    from services.pendientes import SOURCES, load_pending_source, _filter_source_for_profile
    source=_filter_source_for_profile(load_pending_source(SOURCES['emision-servicios']),profile)
    rows=[]
    for row in source['rows']:
        s=row['summary']
        request=str(s.get('Solicitud de') or '').casefold()
        if str(s.get('Estatus actual','')).strip().casefold()=='concluido' and ('emisi' in request or 'emisi' in str(s.get('Casificacion','')).casefold()):
            rows.append({'row':row['source_row'],'fingerprint':digest(row),'name':s.get('Contratante') or s.get('Asegurado') or '', 'rfc':s.get('RFC') or '', 'policy_number':str(s.get('Póliza') or s.get('Poliza') or ''),'request':s.get('Solicitud de') or ''})
    return rows


@router.post('')
def create(data:PolicyInput, profile:AccessProfile=Depends(write_access)):
    emission=validate_emission(data,profile)
    with SessionLocal() as db:
        write_lock(db)
        try:
            p=create_policy(db,profile,data,'Emisión concluida' if emission else 'Alta manual',emission)
            db.commit();return {'id':p.id}
        except IntegrityError as exc:
            db.rollback();raise HTTPException(409,'Conflicto de identidad; vuelve a consultar la póliza') from exc


@router.get('/imports')
def imports(profile:AccessProfile=Depends(write_access)):
    with SessionLocal() as db:
        rows=db.query(AgentAction).filter(AgentAction.action_type=='policy_registry_import').order_by(AgentAction.created_at.desc()).limit(100).all()
        return [{'id':a.id,'name':a.description,'date':str(a.created_at),'status':a.status, 'rows':a.output_payload.get('rows',[])} for a in rows if a.input_payload.get('actor')==profile.username]


class ImportRequest(BaseModel):
    name:str=Field(min_length=1,max_length=200)
    rows:list[dict]=Field(min_length=1,max_length=500)


class ApplyRequest(BaseModel):
    indices:list[int]=Field(min_length=1,max_length=500)


def preview_row(db,profile,raw):
    try:data=PolicyInput.model_validate(raw)
    except Exception as exc:
        return {'kind':'blocked','message':'Campos inválidos o incompletos: '+str(exc)[:500],'policy_number':str(raw.get('policy_number',''))}
    try:
        client,product=validate_input(db,profile,data)
        matches=db.query(Policy).filter(Policy.policy_number==data.policy_number).all()
        if matches:
            p=get_policy(db,profile,matches[0].id)
            if (p.insurer_id,p.product_id,p.client_id)!=(product.insurer_id,product.id,client.id):
                raise HTTPException(409,'Conflicto de aseguradora, ramo o RFC. Se conserva el registro actual.')
            fields=('effective_start_date','effective_end_date','premium_amount','payment_frequency','status','document_link')
            changes=[]
            for field in fields:
                old=getattr(p,field);new=getattr(data,field)
                if field=='document_link' and not new:continue
                if (old or '')!=(new or ''):changes.append({'field':field,'before':str(old or ''),'after':str(new or '')})
            registry=(p.metadata_json or {}).get('registry',{})
            for field in ('agent','insured_names'):
                new=getattr(data,field)
                if new and registry.get(field)!=new:changes.append({'field':field,'before':str(registry.get(field,'')),'after':str(new)})
            return {'kind':'changes' if changes else 'matched','policy_id':p.id,'policy_number':p.policy_number,'client_name':client.full_name,'changes':changes,'fingerprint':digest(snapshot(p))}
        variants=db.query(Policy.policy_number).filter(Policy.insurer_id==product.insurer_id).all()
        if any(policy_key(n[0])==policy_key(data.policy_number) for n in variants):raise HTTPException(409,'Posible duplicado con otra escritura del número. Revisión necesaria.')
        return {'kind':'new','policy_number':data.policy_number,'client_name':client.full_name,'client_id':client.id}
    except HTTPException as exc:return {'kind':'blocked','policy_number':data.policy_number,'message':str(exc.detail)}


@router.post('/imports/preview')
def import_preview(payload:ImportRequest,profile:AccessProfile=Depends(write_access)):
    with SessionLocal() as db:
        rows=[preview_row(db,profile,r) for r in payload.rows]
        keys=Counter(str(r.get('policy_number','')).strip() for r in payload.rows)
        for i,row in enumerate(rows):
            if keys[str(payload.rows[i].get('policy_number','')).strip()]>1: rows[i]={'kind':'blocked','policy_number':row['policy_number'],'message':'Número repetido dentro del archivo; corrige antes de aplicar'}
        action=AgentAction(agent_name='policy_registry',action_type='policy_registry_import',status='preview',description=payload.name,
            input_payload={'actor':profile.username,'rows':payload.rows},output_payload={'rows':rows,'applied':[]})
        db.add(action);db.commit();return {'id':action.id,'rows':rows,'status':action.status}


@router.post('/imports/{import_id}/apply')
def import_apply(import_id:str,payload:ApplyRequest,profile:AccessProfile=Depends(write_access)):
    with SessionLocal() as db:
        write_lock(db)
        action=db.get(AgentAction,import_id)
        if not action or action.action_type!='policy_registry_import' or action.input_payload.get('actor')!=profile.username:raise HTTPException(404,'Carga no encontrada')
        original=action.output_payload;applied=set(original.get('applied',[]));indices=set(payload.indices)
        if indices & applied:raise HTTPException(409,'Hay filas que ya fueron aplicadas')
        for i in sorted(indices):
            if i<0 or i>=len(original['rows']):raise HTTPException(422,'Fila inválida')
            raw=action.input_payload['rows'][i];expected=original['rows'][i]
            if expected.get('dismissed') or expected['kind'] not in {'new','changes'}:raise HTTPException(409,'La fila requiere revisión o no tiene cambios')
            actual=preview_row(db,profile,raw)
            if actual!={k:v for k,v in expected.items() if k!='applied'}:raise HTTPException(409,'Los datos cambiaron desde la vista previa; genera una nueva conciliación')
            data=PolicyInput.model_validate(raw)
            if expected['kind']=='new':create_policy(db,profile,data,'Carga conciliada: '+action.description)
            else:
                p=get_policy(db,profile,expected['policy_id']);registry=(p.metadata_json or {}).get('registry',{})
                # Empty source cells do not erase validated enrichment.
                data=data.model_copy(update={'document_link':data.document_link or p.document_link or '', 'agent':data.agent or registry.get('agent',''),'insured_names':data.insured_names or registry.get('insured_names',[])})
                update_policy(db,profile,p,data,'Conciliación: '+action.description)
            applied.add(i)
        action.output_payload={**original,'applied':sorted(applied),'rows':[dict(row,applied=i in applied) for i,row in enumerate(original['rows'])]}
        action.status='completed' if all(r.get('dismissed') or r['kind']=='matched' or i in applied for i,r in enumerate(original['rows'])) else 'review'
        db.commit();return {'applied':len(indices)}


@router.post('/imports/{import_id}/dismiss')
def dismiss_import_rows(import_id:str,payload:ApplyRequest,profile:AccessProfile=Depends(write_access)):
    with SessionLocal() as db:
        write_lock(db)
        action=db.get(AgentAction,import_id)
        if not action or action.action_type!='policy_registry_import' or action.input_payload.get('actor')!=profile.username:
            raise HTTPException(404,'Carga no encontrada')
        output=dict(action.output_payload);rows=[dict(row) for row in output['rows']]
        for i in set(payload.indices):
            if i<0 or i>=len(rows) or rows[i].get('applied'): raise HTTPException(409,'Fila inválida o ya aplicada')
            rows[i]['dismissed']=True
        output['rows']=rows;action.output_payload=output
        action.status='completed' if all(r.get('applied') or r.get('dismissed') or r['kind']=='matched' for r in rows) else 'review'
        db.commit()
        return {'dismissed':len(set(payload.indices))}


@router.get('/{policy_id}')
def detail(policy_id:str,profile:AccessProfile=Depends(read_access)):
    with SessionLocal() as db:
        p=get_policy(db,profile,policy_id)
        result=serialize(p)
        if not result['agent'] and p.insurer_id=='metlife':
            from services.renovaciones import metlife_gmm_agents, metlife_vida_agents
            try:
                agents=metlife_gmm_agents() if p.product.branch=='GMM' else metlife_vida_agents()
                agent=agents.get((p.policy_number,str(p.effective_end_date)),agents.get((p.policy_number,''),{}))
                result['agent']=' · '.join(str(agent.get(key) or '') for key in ('NOMBRE','AGENTE')).strip(' ·')
            except (FileNotFoundError, OSError):
                pass
        result['assignments']=[{'name':s.name,'rate':float(a.commission_rate)*100,'from':str(a.effective_from),'to':str(a.effective_to) if a.effective_to else None,'active':a.is_active,'source':a.source} for a,s in db.query(PolicyProspectorAssignment,Prospector).join(Prospector,Prospector.id==PolicyProspectorAssignment.prospector_id).filter(PolicyProspectorAssignment.policy_id==p.id).all()]
        result['renewals']=[{'date':str(r.renewal_deadline),'status':r.insurer_response or r.status,'next_policy_id':r.renewal_policy_id} for r in p.renewals]
        result['documents']=[{'name':d.name,'category':d.category,'url':d.drive_link} for d in p.documents]
        result['history']=[{'date':str(a.created_at),'source':a.description,'actor':a.input_payload.get('actor'), 'before':a.input_payload.get('before'),'after':a.output_payload.get('after')} for a in db.query(AgentAction).filter(AgentAction.action_type=='policy_registry_change',AgentAction.input_payload['policy_id'].as_string()==p.id).order_by(AgentAction.created_at.desc()).limit(100)]
        return result


@router.patch('/{policy_id}')
def edit(policy_id:str,payload:PolicyEdit,profile:AccessProfile=Depends(write_access)):
    with SessionLocal() as db:
        write_lock(db);p=get_policy(db,profile,policy_id)
        if digest(snapshot(p))!=payload.fingerprint:raise HTTPException(409,'La póliza cambió; vuelve a abrir su ficha')
        update_policy(db,profile,p,payload.data,'Edición validada en Pólizas');db.commit()
        return {'id':p.id}
