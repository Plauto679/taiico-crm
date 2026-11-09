import io
import zipfile
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from openpyxl import Workbook
from services import mesa_pending as bridge, pendientes as pending
from services.auth import AccessProfile

HEADERS = {
    'emision-servicios': ['Fólio Titan','Folio MetLife','Contratante','Asegurado','RFC','Póliza','Producto','Agente','Casificacion','Tipo de Trámite','Solicitud de','Estatus actual','Fecha Inicio','Días Transcurridos','Fecha ingreso en la aseguradora','Dias en la aseguradora','Comentarios','Responsable','Promotoria','RFC Agente','Recordatorio Futuro','Monto','01-nov-26'],
    'siniestros': ['Folio Titán','Folio DCN','Contratante','Asegurado','RFC','Tipo de Trámite','Trámite','Estatus','Fecha de registro de siniestro','Dias desde registro del siniestro','Fecha de envío a la aseguradora','DIAS CUMPLIDOS EN LA ASEGURADORA','Póliza','Comentarios','Notas Especiales','Promotoria','RFC Agente','Responsable','Recordatorio Futuro','01-nov-26'],
}


def workbook(source):
    wb=Workbook(); ws=wb.active;ws.title=source.sheet_name;ws.append(HEADERS[source.key])
    ws.append(['Anterior' if h=='Contratante' else 'AAAA901001AB1' if h=='RFC' else 'TAIICO' if h=='Promotoria' else '' for h in HEADERS[source.key]])
    wb.create_sheet('Conservar')['A1']='=1+2'
    out=io.BytesIO();wb.save(out);return out.getvalue()


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.setenv('MESA_PENDING_BACKUP_DIR', str(tmp_path / 'backups'))
    source=pending.SOURCES['emision-servicios']
    item=SimpleNamespace(id=str(uuid4()),status='validated',revision=5,history=[],folder_id='mesa-folder',
        promotoria='TAIICO',agent_rfc='AGENTE1',data={'workflow':'emision_gmm','client_name':'Cliente Ficticio','rfc':'BBBB900101AB1','given_names':'CLIENTE','paternal_surname':'FICTICIO','product':'MédicaLife Familiar'})
    profile=AccessProfile(username='reviewer@test.example',role='admin',promotorias=('TAIICO',),rfc='',aseguradoras=('METLIFE',),module_permissions={'pendientes':'operacion'})
    memory={'content':workbook(source),'uploads':0,'timeout':False}
    class Drive:
        def files(self):return self
        def get(self,**kw):return self
        def execute(self):return {'id':item.folder_id,'parents':['rfc-parent'],'appProperties':{'taiico_mesa_id':item.id}}
    drive=Drive()
    monkeypatch.setattr(pending,'_download_workbook',lambda *a:memory['content'])
    def upload(file_id,content,service):
        memory['content']=content;memory['uploads']+=1
        if memory['timeout']:raise TimeoutError('connection lost after Drive accepted write')
    monkeypatch.setattr(pending,'_upload_workbook',upload)
    monkeypatch.setattr(pending,'_clear_source_cache',lambda *a:None)
    monkeypatch.setattr(pending,'_client_folder_for_row',lambda *a,**kw:{'id':'rfc-parent'})
    monkeypatch.setattr(pending,'_assigned_agent_rfc',lambda *a,**kw:'AGENTE1')
    monkeypatch.setattr(pending,'_assigned_responsible',lambda value:value)
    monkeypatch.setattr(pending,'_notify_assigned_responsible',lambda *a,**kw:pytest.fail('Handoff must not send mail'))
    return item,profile,drive,memory


def test_emission_registers_once_preserves_workbook_and_existing_status(setup):
    item,profile,drive,memory=setup;source=pending.SOURCES['emision-servicios']
    with zipfile.ZipFile(io.BytesIO(memory['content'])) as z: preserved=z.read('xl/worksheets/sheet2.xml')
    link=bridge.register(item,profile,service=drive)
    parsed=pending.parse_pending_workbook(memory['content'],source);row=parsed['rows'][-1]
    assert row['mesa_case_id']==item.id and row['mesa_folder_id']=='mesa-folder'
    assert row['summary']['Estatus actual']=='Pendiente Taiico'
    assert row['summary']['Responsable']==profile.username
    assert row['summary']['Fecha ingreso en la aseguradora']==''
    assert 'ID Mesa' not in row['summary'] and 'ID Mesa' not in parsed['core_headers']
    assert all(h['date'] not in pending.MESA_HEADERS for h in row['history'])
    assert item.id in row['history'][-1]['update']
    from services.xlsx_integrity import normalize_sheet_row_spans
    with zipfile.ZipFile(io.BytesIO(memory['content'])) as z:assert z.read('xl/worksheets/sheet2.xml')==normalize_sheet_row_spans(preserved.decode()).encode()
    memory['content']=pending.update_pending_record(memory['content'],source,row['source_row'],{'Estatus actual':'Concluido'})
    pending._creation_requests.clear()
    assert bridge.register(item,profile,service=drive)==link
    assert memory['uploads']==1
    assert pending.parse_pending_workbook(memory['content'],source)['rows'][-1]['summary']['Estatus actual']=='Concluido'
    with pytest.raises(ValueError):pending.update_pending_record(memory['content'],source,row['source_row'],{'ID Mesa':'tampered'})


@pytest.mark.parametrize('stage,expected',[('initial','Inicial'),('complement','Complemento')])
def test_reimbursement_routes_to_siniestros_without_claiming_insurer_submission(setup,stage,expected):
    item,profile,drive,memory=setup;source=pending.SOURCES['siniestros'];memory['content']=workbook(source)
    item.data.update(workflow='reembolso_gmm',claim_stage=stage,policy_number='12345',claim_number='SIN123',patient_given_names='PACIENTE',patient_paternal_surname='FICTICIO')
    result=bridge.register(item,profile,service=drive);row=pending.parse_pending_workbook(memory['content'],source)['rows'][-1]
    assert result['source']=='siniestros'
    assert row['summary']['Trámite']==expected and row['summary']['Tipo de Trámite']=='Reembolso'
    assert row['summary']['Estatus']=='En Proceso' and row['summary']['Fecha de envío a la aseguradora']==''
    assert row['summary']['Asegurado']=='PACIENTE FICTICIO'


def test_timeout_after_upload_recovers_by_id_after_row_shift(setup):
    item,profile,drive,memory=setup;source=pending.SOURCES['emision-servicios'];memory['timeout']=True
    with pytest.raises(TimeoutError):bridge.register(item,profile,service=drive)
    assert memory['uploads']==1
    memory['timeout']=False
    memory['content']=pending.delete_pending_record(memory['content'],source,2)
    link=bridge.register(item,profile,service=drive)
    assert link['source_row']==2 and memory['uploads']==1
    assert len(pending.parse_pending_workbook(memory['content'],source)['rows'])==1


def test_deleted_registered_row_and_duplicate_markers_fail_closed(setup):
    item,profile,drive,memory=setup;source=pending.SOURCES['emision-servicios']
    link=bridge.register(item,profile,service=drive)
    item.history=[{'action':'pending_registered','revision':5,'pending':link}]
    saved=memory['content']
    memory['content']=pending.delete_pending_record(saved,source,link['source_row'])
    for attempt in range(2):
        with pytest.raises(HTTPException) as error:bridge.register(item,profile,service=drive)
        assert error.value.status_code==409
        item.history.append({'action':'pending_registration_failed','revision':6+attempt,'comment':'missing'})
    assert memory['uploads']==1 and bridge.registration(item)['status']=='failed'
    memory['content'],_=pending.append_pending_record(saved,source,{'Contratante':'Duplicado','ID Mesa':item.id})
    with pytest.raises(HTTPException) as error:bridge.register(item,profile,service=drive)
    assert error.value.status_code==409 and memory['uploads']==1


def test_external_workbook_change_aborts_write(setup,monkeypatch):
    item,profile,drive,memory=setup;source=pending.SOURCES['emision-servicios'];calls=[]
    old=memory['content'];changed,_=pending.append_pending_record(old,source,{'Contratante':'Cambio externo'})
    def download(*a):
        calls.append(1);return old if len(calls)==1 else changed
    monkeypatch.setattr(pending,'_download_workbook',download)
    with pytest.raises(HTTPException) as error:bridge.register(item,profile,service=drive)
    assert error.value.status_code==409 and memory['uploads']==0


def test_folder_binding_uses_id_and_parent_not_legacy_name(setup,monkeypatch):
    item,profile,drive,memory=setup
    row={'summary':{'RFC':item.data['rfc'],'Contratante':item.data['client_name']},'mesa_case_id':item.id,'mesa_folder_id':item.folder_id}
    monkeypatch.setattr(pending,'_documents_root_id',lambda:'root')
    def folders(service,parent):
        return [{'id':'rfc-parent','name':item.data['rfc']+' - Nombre'}] if parent=='root' else [
            {'id':'mesa-folder','name':'Reembolso GMM - Mesa - '+item.id,'appProperties':{'taiico_mesa_id':item.id}}]
    monkeypatch.setattr(pending,'_list_child_folders',folders)
    pending._decorate_rows_with_folders({'rows':[row]},drive)
    assert row['folder_id']==item.folder_id
    assert pending._create_folder_for_row(drive,row)['folder_id']==item.folder_id
    row['mesa_folder_id']='different-folder'
    with pytest.raises(HTTPException) as error:pending._create_folder_for_row(drive,row)
    assert error.value.status_code==409


def test_retry_keeps_validating_administrator_as_initial_responsible(setup):
    item,profile,drive,memory=setup
    item.history=[{'action':'validate','actor':'original@test.example','revision':4}]
    bridge.register(item,profile,service=drive)
    row=pending.parse_pending_workbook(memory['content'],pending.SOURCES['emision-servicios'])['rows'][-1]
    assert row['summary']['Responsable']=='original@test.example'


def test_private_download_checks_scope_parent_and_hides_drive_errors(setup,monkeypatch):
    item,profile,drive,memory=setup
    row={'summary':{'RFC':item.data['rfc'],'Promotoria':'TAIICO'},'folder_id':'mesa-folder'}
    calls=[]
    class DownloadDrive:
        def files(self): return self
        def get(self,**kwargs): calls.append('metadata');return self
        def get_media(self,**kwargs): calls.append('media');return self
        def execute(self):
            if calls[-1]=='media':return b'private fixture'
            return {'parents':[memory.get('parent','mesa-folder')],'name':'Solicitud.pdf','size':'15'}
    monkeypatch.setattr(pending,'build_pending_drive_service',lambda:DownloadDrive())
    monkeypatch.setattr(pending,'_get_pending_row',lambda *a:(None,row))
    response=pending.download_pending_document('siniestros',2,'doc',profile)
    assert response.body==b'private fixture' and response.headers['cache-control']=='no-store'
    memory['parent']='another-folder';calls.clear()
    with pytest.raises(HTTPException) as err:pending.download_pending_document('siniestros',2,'doc',profile)
    assert err.value.status_code==404 and calls==['metadata']
    row['summary']['Promotoria']='UNAUTHORIZED';calls.clear()
    with pytest.raises(HTTPException):pending.download_pending_document('siniestros',2,'doc',profile)
    assert calls==[]
    row['summary']['Promotoria']='TAIICO'
    monkeypatch.setattr(DownloadDrive,'execute',lambda self:(_ for _ in ()).throw(RuntimeError('sensitive upstream details')))
    with pytest.raises(HTTPException) as err:pending.download_pending_document('siniestros',2,'doc',profile)
    assert err.value.status_code==502 and 'sensitive' not in err.value.detail


def test_requirements_use_published_snapshot_and_document_kinds(setup,monkeypatch):
    item,profile,drive,memory=setup
    item.history=[{'action':'pending_registered','requirements':['Solicitud firmada']}]
    item.documents=[{'drive_id':'doc','kind':'Solicitud firmada'}]
    class Session:
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def get(self,*a):return item
    monkeypatch.setattr(pending,'SessionLocal',Session)
    row={'mesa_case_id':item.id,'mesa_folder_id':item.folder_id,'summary':{'RFC':item.data['rfc']}}
    assert pending._requirements_for_row(row,'siniestros')==['Solicitud firmada']
    assert pending._mesa_document_context(row)['kinds']=={'doc':'Solicitud firmada'}
    row['mesa_folder_id']='foreign-folder'
    assert pending._mesa_document_context(row) is None
