"""AARCO portfolio reconciliation. Original workbooks and internal columns survive loads."""
from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from decimal import Decimal

from openpyxl import load_workbook
from config import AARCO_PATHS
from database import Client, Insurer, Policy, Product, Renewal, SessionLocal

SOURCE = 'renovaciones.aarco_axa'
ALIASES = {'LINK EXPEDIENTE': 'EXPEDIENTE ORIGEN', 'EMAIL': 'Email', 'TELEFONO': 'TELEFONO'}
REQUIRED = {'AGENTE', 'ASEGURADORA', 'POLIZA', 'CONTRATANTE', 'INICIO VIGENCIA', 'PRIMA NETA ANUAL'}
INTERNAL = {'EXPEDIENTE', 'EXPEDIENTE ORIGEN', 'Email', 'TELEFONO', 'PROSPECTADOR', 'ESTATUS_DE_RENOVACION'}


def text(value):
    return ' '.join(str(value or '').split())


def heading(value):
    value = ''.join(c for c in unicodedata.normalize('NFKD', text(value).upper()) if not unicodedata.combining(c))
    return ALIASES.get(value, value)


def policy_key(value):
    if isinstance(value, (float, int)):
        return str(int(value)) if float(value).is_integer() else str(value)
    return text(value)


def money(value):
    raw = text(value).replace('$','').replace(' ','')
    if not raw: return Decimal('0')
    if ',' in raw and '.' in raw:
        raw = raw.replace('.','').replace(',','.') if raw.rfind(',') > raw.rfind('.') else raw.replace(',','')
    elif ',' in raw:
        raw = raw.replace(',','.') if len(raw.rsplit(',',1)[1]) == 2 else raw.replace(',','')
    return Decimal(raw)


def as_date(value):
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try: return datetime.strptime(text(value), fmt).date()
        except ValueError: pass
    raise ValueError(f'Fecha de vigencia inválida: {value}')


def annual_end(start):
    return start.replace(year=start.year + 1, day=min(start.day, calendar.monthrange(start.year + 1, start.month)[1]))


def read_rows(path):
    workbook = load_workbook(path, data_only=True)
    try:
        sheet = workbook.active
        headers = [heading(c.value) for c in sheet[1]]
        missing = REQUIRED - set(headers)
        if missing: raise ValueError('Faltan columnas AARCO: ' + ', '.join(sorted(missing)))
        populated = [h for h in headers if h]
        if len(populated) != len(set(populated)): raise ValueError('Hay encabezados duplicados en el archivo AARCO')
        rows = {}
        for cells in sheet.iter_rows(min_row=2):
            row = {h: c.value for h, c in zip(headers, cells) if h}
            key = policy_key(row.get('POLIZA'))
            if not key: continue
            row['POLIZA'] = key
            for h, c in zip(headers, cells):
                if h in ('EXPEDIENTE ORIGEN', 'EXPEDIENTE') and c.hyperlink:
                    row[h] = c.hyperlink.target
            key = (key, as_date(row['INICIO VIGENCIA']).isoformat())
            if key in rows and rows[key] != row: raise ValueError(f'Póliza {key}: filas distintas; se requiere conciliación')
            rows[key] = row
        if not rows: raise ValueError('El archivo AARCO no contiene pólizas')
        return headers, rows
    finally: workbook.close()


def prepare(upload: Path, destination: Path):
    headers, incoming = read_rows(upload)
    current_headers, current = read_rows(AARCO_PATHS['RENOVACIONES'])
    merged = {k: dict(v) for k, v in current.items()}
    for key, row in incoming.items():
        old = current.get(key, {})
        start = as_date(row['INICIO VIGENCIA'])
        end = as_date(row['FIN VIGENCIA']) if row.get('FIN VIGENCIA') else annual_end(start)
        if not row.get('FIN VIGENCIA') and old.get('FIN VIGENCIA') and as_date(old['INICIO VIGENCIA']) == start:
            end = as_date(old['FIN VIGENCIA'])
        if end <= start: raise ValueError(f'Vigencia inválida para la póliza {row["POLIZA"]}')
        money(row.get('PRIMA NETA ANUAL'))
        result = dict(old)
        if not old:
            related = [v for v in current.values() if v['POLIZA'] == row['POLIZA'] and text(v.get('CONTRATANTE')).upper() == text(row['CONTRATANTE']).upper() and text(v.get('ASEGURADORA')).upper() == text(row.get('ASEGURADORA')).upper()]
            if related:
                previous = max(related, key=lambda v: as_date(v['INICIO VIGENCIA']))
                for h in INTERNAL - {'ESTATUS_DE_RENOVACION'}:
                    if previous.get(h) and not row.get(h): result[h] = previous[h]
        for h, value in row.items():
            if h in INTERNAL and old.get(h): continue
            if value is not None: result[h] = value
        result.update({'POLIZA': row['POLIZA'], 'INICIO VIGENCIA': start, 'FIN VIGENCIA': end})
        result.setdefault('PROMOTORIA', 'AARCO')
        merged[key] = result
    out_headers = list(dict.fromkeys(current_headers + headers + ['FIN VIGENCIA', 'EXPEDIENTE ORIGEN', 'TELEFONO', 'ESTATUS']))
    workbook = load_workbook(AARCO_PATHS['RENOVACIONES'])
    try:
        sheet = workbook.active
        sheet.delete_rows(1, sheet.max_row)
        sheet.append(out_headers)
        for row in merged.values(): sheet.append([row.get(h) for h in out_headers])
        for table in sheet.tables.values(): table.ref = f'A1:{sheet.cell(1,len(out_headers)).column_letter}{sheet.max_row}'
        workbook.save(destination)
    finally: workbook.close()
    common = incoming.keys() & current.keys()
    incoming_policies = {r['POLIZA'] for r in incoming.values()}
    current_policies = {r['POLIZA'] for r in current.values()}
    return dict(allowed_agent_keys=len({text(r.get('AGENTE')) for r in incoming.values()}), source_rows=len(incoming),
                rows_after_agent_filter=len(incoming), unique_incoming_policies=len(incoming_policies),
                existing_policies_updated=len(incoming_policies & current_policies), new_policies_added=len(incoming_policies-current_policies),
                current_policies_preserved_as_exceptions=len(current_policies-incoming_policies),
                final_policy_count=len({r['POLIZA'] for r in merged.values()}), final_row_count=len(merged),
                statuses_changed=sum(text(incoming[k].get('ESTATUS')) != text(current[k].get('ESTATUS')) for k in common),
                rows_with_preserved_internal_data=sum(any(current[k].get(h) for h in INTERNAL) for k in common))


def sync_index():
    _, rows = read_rows(AARCO_PATHS['RENOVACIONES'])
    db = SessionLocal()
    count = 0
    conflicts = []
    try:
        if not db.get(Insurer, 'aarco'): db.add(Insurer(id='aarco', name='AARCO'))
        for _, row in sorted(rows.items(), key=lambda item: as_date(item[1]['INICIO VIGENCIA'])):
            key = row['POLIZA']
            policy = db.query(Policy).filter_by(policy_number=key).first()
            if policy and policy.insurer_id != 'aarco':
                conflicts.append(key)
                continue
            start, end = as_date(row['INICIO VIGENCIA']), as_date(row['FIN VIGENCIA'])
            if policy is None:
                # Never merge clients by name alone: source has no RFC.
                client = Client(full_name=text(row['CONTRATANTE']), responsible_user_id='usr_pamela',
                                email=text(row.get('Email')) or None, phone=text(row.get('TELEFONO')) or None,
                                metadata_json={'created_from': SOURCE, 'requires_human_review': True, 'aarco_policy': key})
                db.add(client); db.flush()
                policy = Policy(policy_number=key, client_id=client.id, insurer_id='aarco', responsible_user_id='usr_pamela')
            branch = text(row.get('RAMO')) or 'POR CONFIRMAR'
            product_name = text(row.get('PRODUCTO')) or branch
            product = db.query(Product).filter_by(insurer_id='aarco',name=product_name,branch=branch).first()
            if product is None:
                product = Product(insurer_id='aarco',name=product_name,branch=branch);db.add(product);db.flush()
            policy.product_id = product.id
            policy.effective_start_date, policy.effective_end_date = start, end
            policy.premium_amount = money(row.get('PRIMA NETA ANUAL'))
            policy.payment_frequency = text(row.get('FRECUENCIA PAGO')) or 'unknown'
            if text(row.get('ESTATUS')).upper() == 'CANCELADA': policy.status = 'cancelled'
            elif not policy.status: policy.status = 'in_force'
            policy.metadata_json = {**(policy.metadata_json or {}), 'aarco_source': {h: v.isoformat() if isinstance(v,(date,datetime)) else v for h,v in row.items()}}
            if not policy.document_link and text(row.get('EXPEDIENTE')).startswith('https://'): policy.document_link = row['EXPEDIENTE']
            db.add(policy)
            db.flush()
            renewal = db.query(Renewal).filter_by(original_policy_id=policy.id,renewal_deadline=end).first()
            if renewal is None:
                renewal = Renewal(original_policy_id=policy.id,client_id=policy.client_id,renewal_deadline=end)
                db.add(renewal)
            renewal.requested_modifications = {**(renewal.requested_modifications or {}), 'aarco_source': policy.metadata_json['aarco_source']}
            if not renewal.insurer_response and row.get('ESTATUS_DE_RENOVACION'): renewal.insurer_response = text(row['ESTATUS_DE_RENOVACION'])
            if policy.status == 'cancelled': renewal.status = 'cancelled'
            count += 1
        db.commit()
        return {'status':'completed_with_warnings' if conflicts else 'completed','rows_updated':count,'rows_failed':0,'policy_number_conflicts':conflicts}
    except Exception:
        db.rollback();raise
    finally: db.close()


def renewal_rows(start, end):
    _, rows = read_rows(AARCO_PATHS['RENOVACIONES'])
    result = []
    db = SessionLocal()
    try:
        indexed = {(p.policy_number, r.renewal_deadline): (r.insurer_response, p.document_link, p.client.email if p.client else None)
                   for r,p in db.query(Renewal,Policy).join(Policy,Renewal.original_policy_id==Policy.id).filter(Policy.insurer_id=='aarco').all()}
    finally: db.close()
    for row in rows.values():
        deadline = as_date(row['FIN VIGENCIA'])
        if not start <= deadline <= end: continue
        item = {h: v.isoformat() if isinstance(v,(date,datetime)) else v for h,v in row.items()}
        item['INICIO VIGENCIA'] = as_date(row['INICIO VIGENCIA']).isoformat()
        item['FIN VIGENCIA'] = deadline.isoformat()
        # Keep Windows links as provenance; browsers must only open verified web links.
        if not text(item.get('EXPEDIENTE')).startswith('https://'): item['EXPEDIENTE'] = None
        item['PRIMA NETA ANUAL'] = float(money(row.get('PRIMA NETA ANUAL')))
        overlay = indexed.get((row['POLIZA'], deadline))
        if overlay:
            for h,v in zip(('ESTATUS_DE_RENOVACION','EXPEDIENTE','Email'),overlay):
                if v: item[h] = v
        result.append(item)
    return result
