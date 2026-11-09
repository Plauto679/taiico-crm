"""One-way, durable handoff to the canonical Pendientes workbook. No emails."""
from __future__ import annotations

import io
import os
from pathlib import Path
from uuid import UUID, uuid4

import pandas as pd
from fastapi import HTTPException

from services import pendientes, mesa_claims


def _backup(workbook, source, case_id):
    root = Path(os.getenv('MESA_PENDING_BACKUP_DIR', str(Path(__file__).resolve().parents[2] / '.runtime/mesa-pending-backups')))
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = root / f'{source.key}-{case_id}-{uuid4()}.xlsx'
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
        stream.write(workbook)
        stream.flush()
        os.fsync(stream.fileno())


def registration(item):
    linked = [entry for entry in item.history if entry['action'] == 'pending_registered']
    failed = [entry for entry in item.history if entry['action'] == 'pending_registration_failed']
    if linked:
        first = linked[0]
        last = linked[-1]
        edited = any(entry['revision'] > first['revision'] and entry['action'] in
                     {'edited', 'document_uploaded', 'extraction_confirmed', 'form_generated'} for entry in item.history)
        if failed and failed[-1]['revision'] > last['revision']:
            return {'status': 'failed', **last['pending'], 'changed_after_registration': edited, 'notice': failed[-1]['comment']}
        return {'status': 'registered', **last['pending'], 'changed_after_registration': edited,
                'notice': 'El registro operativo conserva su seguimiento. Revisa en Pendientes los cambios posteriores al primer registro.' if edited else 'Registro operativo creado y carpeta del movimiento vinculada.'}
    if failed:
        return {'status': 'failed', 'notice': failed[-1]['comment']}
    return {'status': 'not_registered', 'notice': 'Al validar en Mesa se registrará en Pendientes.'}


def _find(parsed, case_id):
    matches = [row for row in parsed['rows'] if row.get('mesa_case_id') == case_id]
    if len(matches) > 1:
        raise HTTPException(409, 'Hay varios registros con el mismo identificador de Mesa. Requieren conciliación.')
    return matches[0] if matches else None


def _add_headers(workbook, source):
    headers = list(pd.read_excel(io.BytesIO(pendientes._workbook_for_tabular_read(workbook, source.sheet_name)),
                                sheet_name=source.sheet_name, nrows=0).columns)
    for header in pendientes.MESA_HEADERS:
        matches = [h for h in headers if pendientes._normalized_header(str(h)) == pendientes._normalized_header(header)]
        if matches and matches != [header]:
            raise HTTPException(409, 'Las columnas de enlace de Mesa requieren revisión.')
        if not matches:
            workbook = pendientes._update_xlsx_cells(workbook, source.sheet_name, {(1, len(headers)+1): header})
            headers.append(header)
    return workbook


def register(item, profile, *, service=None):
    """Recover an uncertain upload by its persistent UUID, never by row position."""
    if item.status != 'validated' or not profile.is_admin or not profile.can_operate('pendientes'):
        raise HTTPException(409, 'Se requiere un expediente validado por mesa y acceso administrativo de operación.')
    UUID(item.id)
    if not item.folder_id:
        raise HTTPException(409, 'El expediente no tiene carpeta del movimiento. Revisa sus documentos antes de registrar.')
    is_claim = mesa_claims.is_claim(item.data)
    source = pendientes.SOURCES['siniestros' if is_claim else 'emision-servicios']
    service = service or pendientes.build_pending_drive_service()
    parent = pendientes._client_folder_for_row(service, {'summary': {'RFC': item.data['rfc'], 'Contratante': item.data['client_name']}}, create=False)
    folder = service.files().get(fileId=item.folder_id, fields='id,parents,trashed,appProperties', supportsAllDrives=True).execute()
    if not parent or folder.get('trashed') or parent['id'] not in folder.get('parents', []) or folder.get('appProperties', {}).get('taiico_mesa_id') != item.id:
        raise HTTPException(409, 'La carpeta no corresponde al RFC y movimiento de Mesa. Revisa el vínculo.')
    promotoria = pendientes._assigned_promotoria(item.promotoria, profile)
    agent = pendientes._assigned_agent_rfc(item.agent_rfc, promotoria, profile, service=service)
    reviewer = next((entry['actor'] for entry in reversed(item.history) if entry['action'] == 'validate'), profile.username)
    file_id = pendientes._source_file_id(source)
    # All CRM writes to these workbooks share this lock. A durable UUID also survives restarts.
    with pendientes._write_lock:
        original = pendientes._download_workbook(file_id, service)
        parsed = pendientes.parse_pending_workbook(original, source)
        row = _find(parsed, item.id)
        if row:
            pendientes._ensure_row_access(row, profile, operation=True)
            if row.get('mesa_folder_id') != item.folder_id or pendientes._rfc_from_row(row) != item.data['rfc']:
                raise HTTPException(409, 'El registro existente no coincide con la identidad o carpeta de Mesa.')
        else:
            if any(entry['action'] == 'pending_registered' for entry in item.history):
                raise HTTPException(409, 'El registro vinculado ya no se encuentra en la base. Revisa Pendientes; no se duplicará automáticamente.')
            values = {'Contratante': item.data['client_name'], 'RFC': item.data['rfc'],
                      'Asegurado': ' '.join(item.data.get(key, '') for key in
                          (('patient_given_names', 'patient_paternal_surname', 'patient_maternal_surname') if is_claim else
                           ('given_names', 'paternal_surname', 'maternal_surname'))).strip(),
                      'Póliza': item.data.get('policy_number', ''), 'Promotoria': promotoria, 'RFC Agente': agent,
                      'Responsable': pendientes._assigned_responsible(reviewer),
                      'ID Mesa': item.id, 'Carpeta Mesa': item.folder_id, 'Revisión Mesa': str(item.revision),
                      **pendientes._automatic_creation_values(source)}
            if is_claim:
                if item.data.get('claim_stage') not in {'initial', 'complement'} or not item.data.get('policy_number'):
                    raise HTTPException(422, 'Confirma tipo de reembolso y póliza antes del registro operativo.')
                values.update({'Tipo de Trámite': 'Reembolso', 'Trámite': 'Inicial' if item.data['claim_stage'] == 'initial' else 'Complemento', 'Estatus': 'En Proceso'})
            else:
                values.update({'Casificacion': 'GMM', 'Tipo de Trámite': 'Emisión', 'Producto': item.data.get('product', ''),
                               'Solicitud de': 'EMISION PERSONA FISICA', 'Estatus actual': 'Pendiente Taiico'})
            updated = _add_headers(original, source)
            updated, source_row = pendientes.append_pending_record(updated, source, values)
            comment = f'Mesa {item.id}: expediente validado por {reviewer}, registrado por {profile.username}, revisión {item.revision}. Registro operativo, sin envío a MetLife.'
            if is_claim:
                comment += f" Siniestro: {item.data.get('claim_number') or 'inicial'}."
                if item.data.get('previous_dcn'):
                    comment += f" DCN previo: {item.data['previous_dcn']}."
            updated, _ = pendientes.add_pending_follow_up(updated, source, source_row, comment)
            # Detect a human edit between read and write. The canonical Drive file is not a SQL transaction.
            if pendientes._download_workbook(file_id, service) != original:
                raise HTTPException(409, 'La base cambió durante el registro. Reintenta para usar su versión más reciente.')
            _backup(original, source, item.id)
            try:
                pendientes._upload_workbook(file_id, updated, service)
            finally:
                pendientes._clear_source_cache(source.key)
            verified = pendientes.parse_pending_workbook(pendientes._download_workbook(file_id, service), source)
            row = _find(verified, item.id)
            if not row or row.get('mesa_folder_id') != item.folder_id:
                raise HTTPException(502, 'No se pudo confirmar el registro en Drive. Reintenta; el identificador evita duplicados.')
        return {'source': source.key, 'source_row': row['source_row'], 'case_id': item.id,
                'source_revision': row.get('mesa_revision', ''),
                'url': f'/pendientes?source={source.key}&mesa={item.id}'}
