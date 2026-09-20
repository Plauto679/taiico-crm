from __future__ import annotations

import io
import re
import smtplib
from datetime import datetime, date
from decimal import Decimal
from email.message import EmailMessage
from pathlib import Path
from typing import Literal
from uuid import uuid4
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from database import (SessionLocal, AgentStatement, Prospector, ProspectorCommissionPeriod,
    ProspectorCommissionBatch, ProspectorCommissionLine, ProspectorCommissionAllocation, ProspectorOpeningBalance)
from services.auth import AccessProfile
from services.authorization import require_module_access
from services.mail_configuration import smtp_settings_for, smtp_ssl_context
from services.cobranza_prospectadores import money

router = APIRouter(prefix='/estados-prospectadores', tags=['estados-prospectadores'])
operate = require_module_access('estados_agentes', operation=True)
LABELS = {'pendiente': 'Pendiente de envío', 'enviado': 'Enviado', 'pagado': 'Pagado'}


def locked_session():
    db = SessionLocal()
    # Serialize mutations before reads on SQLite too (FOR UPDATE alone is ignored there).
    if db.bind.dialect.name == 'sqlite':
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')
    else:
        # Shared lock for statement mutations: protects carry calculations across periods.
        db.execute(select(ProspectorCommissionPeriod.id).order_by(ProspectorCommissionPeriod.id).with_for_update()).all()
    return db


def event(row, actor, action, **details):
    row.history = [*(row.history or []), {'at': datetime.utcnow().isoformat(), 'actor': actor, 'action': action, **details}]


VAT_RATE = Decimal('0.16')
STATEMENT_CC = 'veronica.alfaro@taiico.com'


def split_adjustment(item):
    # Legacy entries were final amounts. Preserve their payable value.
    if 'vat' in item:
        net = Decimal(str(item['amount']))
        vat = Decimal(str(item['vat']))
    else:
        gross = Decimal(str(item['amount']))
        net = money(gross / (1 + VAT_RATE))
        vat = gross - net
    return net, vat


def own_breakdown(row):
    net = sum((Decimal(x['commission']) for x in row.lines), Decimal('0'))
    vat = sum((Decimal(x['vat']) for x in row.lines), Decimal('0'))
    for item in row.adjustments:
        n, v = split_adjustment(item)
        net += n; vat += v
    return money(net), money(vat)


def own_amount(row):
    return money(sum(own_breakdown(row)))


def carry_total(item):
    return Decimal(item['amount']) + Decimal(item.get('vat', '0'))


def summary_matrix(data):
    commission = [sum((Decimal(x[k]) for x in data['lines']), Decimal('0')) for k in ('commission','vat')]
    adjustments = [sum((split_adjustment(x)[i] for x in data['adjustments']), Decimal('0')) for i in (0,1)]
    carry = [sum((split_adjustment(x)[i] for x in data['carry']), Decimal('0')) for i in (0,1)]
    rows = [('Comisiones del mes', *commission), ('Ajustes del mes', *adjustments), ('Saldo anterior', *carry)]
    rows.append(('Total del estado', sum(x[1] for x in rows), sum(x[2] for x in rows)))
    return [(label, money(net), money(vat), money(net+vat)) for label,net,vat in rows]


def refresh_balances(db, actor):
    db.flush()
    rows = db.query(AgentStatement).order_by(AgentStatement.month, AgentStatement.id).all()
    for row in rows:
        if row.status == 'pagado':
            continue
        # Carry only each unpaid month's own amount, never a previous accumulated total.
        carry = [{'id': old.id, 'month': old.month.isoformat(), 'amount': str(own_breakdown(old)[0]), 'vat': str(own_breakdown(old)[1])}
                 for old in rows if old.prospector_id == row.prospector_id and old.currency == row.currency
                 and old.month < row.month and old.status != 'pagado' and old.own_amount != 0]
        own = own_amount(row)
        total = money(own + sum((carry_total(x) for x in carry), Decimal('0')))
        if carry != row.carry or own != row.own_amount or total != row.total_amount:
            if row.delivery_state == 'sending':
                raise HTTPException(409, 'Hay un envío en curso para este prospectador; espera a que termine.')
            row.carry, row.own_amount, row.total_amount = carry, own, total
            row.status = 'pendiente'
            row.revision += 1
            event(row, actor, 'saldo_actualizado', total=str(total))


def statement_recipient(row, prospector):
    # An explicit statement recipient takes precedence over the current directory.
    return (row.recipient or '').strip() or (prospector.email or '').strip()


def serialize(row, prospector, detail=False):
    result = {'id': row.id, 'period_id': row.period_id, 'prospector_id': row.prospector_id,
        'name': prospector.name, 'month': row.month.isoformat(), 'currency': row.currency,
        'prospector_active': bool(prospector.is_active),
        'status': row.status, 'recipient': statement_recipient(row, prospector),
        'commission': str(money(sum((Decimal(x['total']) for x in row.lines), Decimal('0')))),
        'adjustment_total': str(money(sum((sum(split_adjustment(x)) for x in row.adjustments), Decimal('0')))),
        'carry_total': str(money(sum((carry_total(x) for x in row.carry), Decimal('0')))),
        'own_amount': str(row.own_amount), 'total': str(row.total_amount), 'revision': row.revision,
        'delivery_state': row.delivery_state, 'delivery_error': row.delivery_error,
        'sent_at': row.sent_at.isoformat() if row.sent_at else None,
        'paid_at': row.paid_at.isoformat() if row.paid_at else None}
    if detail:
        normalized_carry = []
        with SessionLocal() as source_db:
            for item in row.carry:
                if 'vat' in item:
                    normalized_carry.append(item)
                    continue
                source = source_db.get(AgentStatement, item['id'])
                net, vat = own_breakdown(source) if source else split_adjustment(item)
                # Preserve the historical carried total if its source changed.
                if money(net + vat) != money(Decimal(item['amount'])):
                    net, vat = split_adjustment(item)
                normalized_carry.append({**item, 'amount': str(net), 'vat': str(vat)})
        result.update(lines=[x for x in row.lines if (x.get("manual") or Decimal(x["rate"]) != 0)], adjustments=[{**x, 'amount': str(split_adjustment(x)[0]), 'vat': str(split_adjustment(x)[1])} for x in row.adjustments], carry=normalized_carry, notes=row.notes, history=row.history)
    return result


def get_row(db, statement_id):
    row = db.get(AgentStatement, statement_id)
    if not row:
        raise HTTPException(404, 'Estado de cuenta no encontrado')
    return row


def check_revision(row, revision):
    if row.revision != revision:
        raise HTTPException(409, 'El estado cambió. Vuelve a abrirlo antes de continuar.')
    if row.delivery_state == 'sending':
        raise HTTPException(409, 'Este estado tiene un envío en curso. No lo modifiques ni reenvíes.')


class GenerateInput(BaseModel):
    period_id: str
    prospector_id: str | None = None


class Adjustment(BaseModel):
    concept: str = Field(min_length=1, max_length=250)
    amount: Decimal = Field(max_digits=14, decimal_places=2)

    @field_validator('concept')
    @classmethod
    def nonblank(cls, v):
        if not v.strip():
            raise ValueError('Especifica el concepto')
        return v.strip()


class ManualCommission(BaseModel):
    id: str | None = Field(default=None, max_length=36)
    policy: str = Field(min_length=1, max_length=100)
    date: date
    insurer: str = Field(min_length=1, max_length=100)
    branch: str = Field(min_length=1, max_length=100)
    percentage: Decimal | None = Field(default=None, gt=0, le=100, decimal_places=6)
    commission: Decimal = Field(max_digits=14, decimal_places=2)

    @field_validator('policy', 'insurer', 'branch')
    @classmethod
    def required_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Completa los datos de la póliza')
        return value


class EditInput(BaseModel):
    revision: int
    recipient: str = Field(default='', max_length=320)
    notes: str = Field(default='', max_length=4000)
    adjustments: list[Adjustment] = Field(default_factory=list, max_length=100)
    manual_commissions: list[ManualCommission] | None = Field(default=None, max_length=100)

    @field_validator('recipient')
    @classmethod
    def email(cls, v):
        v = v.strip()
        if v and not re.fullmatch(r'[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+', v):
            raise ValueError('Escribe un correo válido, sin listas de destinatarios')
        return v


class StatusInput(BaseModel):
    revision: int
    status: Literal['pendiente', 'pagado']


class SendInput(BaseModel):
    revision: int
    resend: bool = False


def statement_has_activity(row):
    return (any(Decimal(x['total']) != 0 for x in row.lines) or bool(row.adjustments)
            or bool(row.carry) or bool(row.notes)
            or any(x.get('manual') for x in row.history))


@router.get('')
def workspace():
    db = SessionLocal()
    try:
        periods = db.query(ProspectorCommissionPeriod).order_by(ProspectorCommissionPeriod.month.desc()).all()
        rows = db.query(AgentStatement, Prospector).join(Prospector, Prospector.id == AgentStatement.prospector_id).all()
        return {'periods': [{'id': p.id, 'month': p.month.isoformat()} for p in periods],
                'statements': [serialize(r, p) for r, p in rows if r.status != 'pendiente' or statement_has_activity(r)],
                'prospectors': [{'id': p.id, 'name': p.name} for p in db.query(Prospector).filter_by(is_active=True).order_by(Prospector.name).all()]}
    finally:
        db.close()


@router.post('/generate')
def generate(payload: GenerateInput, profile: AccessProfile = Depends(operate)):
    db = locked_session()
    try:
        period = db.get(ProspectorCommissionPeriod, payload.period_id)
        if not period:
            raise HTTPException(404, 'Periodo no encontrado')
        batches = db.query(ProspectorCommissionBatch).filter_by(period_id=period.id).all()
        if {b.source for b in batches} != {'metlife','sura','aarco'}:
            raise HTTPException(409, 'Carga los estados de MetLife, SURA y AARCO antes de generar el periodo.')
        batch_ids = [b.id for b in batches]
        if db.query(ProspectorCommissionLine).filter(ProspectorCommissionLine.batch_id.in_(batch_ids), ProspectorCommissionLine.status != 'listo').count():
            raise HTTPException(409, 'Resuelve las excepciones del periodo antes de generar los estados.')
        allocations = db.query(ProspectorCommissionAllocation, ProspectorCommissionLine).join(
            ProspectorCommissionLine, ProspectorCommissionLine.id == ProspectorCommissionAllocation.line_id
        ).filter(ProspectorCommissionLine.batch_id.in_(batch_ids)).order_by(ProspectorCommissionLine.movement_date, ProspectorCommissionLine.policy_number).all()
        if payload.prospector_id:
            allocations = [(a, line) for a, line in allocations if a.prospector_id == payload.prospector_id]
        from services.cobranza_prospectadores import analyze_import_lines
        source_lines = {line.id: line for _, line in allocations if line.policy_id}
        inputs = [{**(line.raw_payload or {}), 'policy_number': line.policy_number,
                   'insurer_id': line.insurer_id, 'branch': line.branch, 'currency': line.currency,
                   'movement_date': str(line.movement_date), 'source_commission': str(line.source_commission)}
                  for line in source_lines.values()]
        refreshed = dict(zip(source_lines, analyze_import_lines(db, inputs, period)))
        grouped = {}
        for a, line in allocations:
            item = refreshed.get(line.id)
            matching = [x for x in item['allocations'] if x['prospector_id'] == a.prospector_id] if item else []
            existing = db.query(AgentStatement).filter_by(period_id=period.id, prospector_id=a.prospector_id).first()
            if item and (not existing or existing.status == 'pendiente'):
                if item['status'] != 'listo' or len(matching) != 1:
                    raise HTTPException(409, 'Cambió la asignación de una póliza; revisa la cobranza antes de generar.')
                fresh = matching[0]
                a.commission_rate = Decimal(fresh['commission_rate'])
                for key in ('commission_amount','vat_amount','total_amount'):
                    setattr(a, key, Decimal(fresh['calculation'][key]))
                a.calculation_json = fresh['calculation']

            if Decimal(a.commission_rate) == 0:
                continue
            grouped.setdefault(a.prospector_id, []).append({'allocation_id': a.id, 'policy': line.policy_number,
                'insurer': line.insurer_id, 'branch': line.branch or '', 'date': str(line.movement_date or ''),
                'rate': str(a.commission_rate), 'source_commission': str(line.source_commission),
                'commission': str(a.commission_amount), 'vat': str(a.vat_amount), 'total': str(a.total_amount)})
        openings = {x.prospector_id: x for x in db.query(ProspectorOpeningBalance).filter_by(period_id=period.id).all()}
        ids = set(grouped) | set(openings)
        ids.update(x.prospector_id for x in db.query(AgentStatement).filter_by(period_id=period.id).all())
        ids.update(x.prospector_id for x in db.query(AgentStatement).filter(AgentStatement.month < period.month,
            AgentStatement.status != 'pagado', AgentStatement.currency == period.currency).all() if x.own_amount != 0)
        if payload.prospector_id:
            if not db.get(Prospector, payload.prospector_id):
                raise HTTPException(404, 'Prospectador no encontrado')
            ids = {payload.prospector_id}
        created = updated = 0
        for prospector_id in sorted(ids):
            row = db.query(AgentStatement).filter_by(period_id=period.id, prospector_id=prospector_id).first()
            if row and row.status != 'pendiente':
                continue
            if row and row.delivery_state == 'sending':
                raise HTTPException(409, 'Hay envíos en curso. Espera antes de regenerar.')
            if not row and not payload.prospector_id and not any(Decimal(x['total']) != 0 for x in grouped.get(prospector_id, [])) and prospector_id not in openings:
                if not db.query(AgentStatement).filter(AgentStatement.prospector_id == prospector_id,
                    AgentStatement.month < period.month, AgentStatement.status != 'pagado',
                    AgentStatement.own_amount != 0).first():
                    continue
            if not row:
                person = db.get(Prospector, prospector_id)
                previous = db.query(AgentStatement).filter_by(prospector_id=prospector_id).order_by(AgentStatement.month.desc()).first()
                initial = openings.get(prospector_id)
                # Opening balances are initial historical balances, imported only once for each prospectador.
                first = not db.query(AgentStatement).filter_by(prospector_id=prospector_id).first()
                adjustments = [{'concept': initial.notes or 'Saldo inicial', 'amount': str(initial.amount), 'vat': str(money(Decimal(initial.amount) * VAT_RATE))}] if initial and first else []
                row = AgentStatement(period_id=period.id, prospector_id=prospector_id, month=period.month,
                    currency=period.currency, recipient=person.email or (previous.recipient if previous else ''), lines=grouped.get(prospector_id, []),
                    adjustments=adjustments, carry=[], own_amount=0, total_amount=0, status='pendiente',
                    revision=1, notes='', history=[], delivery_state='', created_by=profile.username)
                db.add(row); db.flush()
                event(row, profile.username, 'generado', manual=bool(payload.prospector_id))
                created += 1
            elif row.lines != grouped.get(prospector_id, []) + [x for x in row.lines if x.get('manual')]:
                row.lines = grouped.get(prospector_id, []) + [x for x in row.lines if x.get('manual')]
                row.revision += 1
                event(row, profile.username, 'comisiones_actualizadas')
                updated += 1
        refresh_balances(db, profile.username)
        db.commit()
        return {'created': created, 'updated': updated}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


@router.get('/{statement_id}')
def detail(statement_id: str):
    db = SessionLocal()
    try:
        row = get_row(db, statement_id)
        return serialize(row, db.get(Prospector, row.prospector_id), True)
    finally:
        db.close()


@router.put('/{statement_id}')
def edit(statement_id: str, payload: EditInput, profile: AccessProfile = Depends(operate)):
    db = locked_session()
    try:
        row = get_row(db, statement_id); check_revision(row, payload.revision)
        if row.status == 'pagado':
            raise HTTPException(409, 'Reabre el estado como Pendiente de envío antes de editarlo.')
        event(row, profile.username, 'editado', previous_adjustments=row.adjustments, previous_notes=row.notes,
              previous_recipient=row.recipient, previous_lines=row.lines)
        row.recipient, row.notes = payload.recipient, payload.notes
        row.adjustments = [{'concept': x.concept, 'amount': str(x.amount), 'vat': str(money(x.amount * VAT_RATE))} for x in payload.adjustments]
        if payload.manual_commissions is not None:
            existing_ids = {x.get('id') for x in row.lines if x.get('manual')}
            used_ids = set()
            manual = []
            for item in payload.manual_commissions:
                if item.id and (item.id not in existing_ids or item.id in used_ids):
                    raise HTTPException(409, 'La comisión manual no corresponde a este estado o está duplicada.')
                if item.date.year != row.month.year or item.date.month != row.month.month:
                    raise HTTPException(422, 'La fecha de la comisión debe pertenecer al periodo del estado.')
                id = item.id or str(uuid4())
                used_ids.add(id)
                vat = money(item.commission * VAT_RATE)
                manual.append({'id':id, 'manual':True, 'policy':item.policy, 'date':item.date.isoformat(),
                    'insurer':item.insurer, 'branch':item.branch,
                    'rate':str(item.percentage / 100) if item.percentage is not None else None,
                    'commission':str(item.commission), 'vat':str(vat), 'total':str(money(item.commission+vat))})
            row.lines = [x for x in row.lines if not x.get('manual')] + manual
        row.status = 'pendiente'; row.revision += 1
        refresh_balances(db, profile.username)
        db.commit()
        return serialize(row, db.get(Prospector, row.prospector_id), True)
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


@router.post('/{statement_id}/status')
def set_status(statement_id: str, payload: StatusInput, profile: AccessProfile = Depends(operate)):
    db = locked_session()
    try:
        row = get_row(db, statement_id); check_revision(row, payload.revision)
        if payload.status == 'pagado':
            settled = [get_row(db, x['id']) for x in row.carry] + [row]
            for item in settled:
                if item.delivery_state == 'sending':
                    raise HTTPException(409, 'Hay un envío en curso para un saldo incluido.')
                if item.status != 'pagado':
                    item.status = 'pagado'; item.paid_at = datetime.utcnow(); item.revision += 1
                    event(item, profile.username, 'pagado', settled_by=row.id, total=str(item.total_amount))
        else:
            row.status = 'pendiente'; row.paid_at = None; row.revision += 1
            event(row, profile.username, 'reabierto', note='Los saldos anteriores ya liquidados conservan su pago.')
        refresh_balances(db, profile.username)
        db.commit()
        return {'status': row.status}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


STATEMENT_LOGO = Path(__file__).resolve().parent.parent / 'assets' / 'taiico-statement-logo.png'


def display_insurer(value):
    name = str(value).strip().title()
    return 'MetLife' if name.lower() == 'metlife' else name


def display_percentage(rate):
    # Presentation only: keep the original precision for commission calculations.
    return int(Decimal(str(rate)) * 100)


def pdf_bytes(data):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    navy = colors.HexColor('#283E63')
    blue = colors.HexColor('#34587C')
    accent = colors.HexColor('#5996D1')
    ink = colors.HexColor('#1D2F3E')
    styles = getSampleStyleSheet()
    styles['Normal'].textColor = ink
    styles['Heading2'].textColor = navy
    styles.add(ParagraphStyle(name='SmallCell', fontSize=7.5, leading=10, textColor=ink, alignment=1))
    styles.add(ParagraphStyle(name='NumberCell', parent=styles['SmallCell'], alignment=1))
    styles.add(ParagraphStyle(name='TableHead', parent=styles['SmallCell'], fontName='Helvetica-Bold', textColor=colors.white))
    styles.add(ParagraphStyle(name='StatementTitle', fontName='Helvetica-Bold', fontSize=23, leading=28, textColor=navy))
    p = lambda value, style='SmallCell': Paragraph(escape(str(value)), styles[style])
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=32, leftMargin=32, topMargin=28, bottomMargin=38,
                            title=f"Estado de cuenta {data['month'][:7]}", author='TAIICO')
    width = doc.width
    header = Table([[Image(str(STATEMENT_LOGO), width=74, height=74),
                     p('Estado de cuenta', 'StatementTitle')]], colWidths=[96, width-96])
    header.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),0),
                               ('LINEBELOW',(0,0),(-1,-1),2,accent),('BOTTOMPADDING',(0,0),(-1,-1),14)]))
    content = [header, Spacer(1,12), Paragraph(escape(data['name']), styles['Heading2']),
        Paragraph(f"Periodo: {data['month'][:7]} · {data['currency']}", styles['Normal']), Spacer(1,18)]
    totals = [[p(x,'TableHead') for x in ('Concepto','Importe sin IVA','IVA','Total con IVA')]]
    matrix = summary_matrix(data)
    for i, (label,net,vat,total) in enumerate(matrix):
        style = 'TableHead' if i == 3 else 'SmallCell'
        totals.append([p(label,style), *[p(f"${value:,.2f}",style) for value in (net,vat,total)]])
    table=Table(totals,colWidths=[width*.34,width*.22,width*.20,width*.24])
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),blue),('BACKGROUND',(0,-1),(-1,-1),navy),
        ('LINEBELOW',(0,1),(-1,-2),.3,accent),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('BOTTOMPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),9)]))
    content += [table,Spacer(1,18),Paragraph('Detalle de comisiones',styles['Heading2'])]
    rows = [[p(x,'TableHead') for x in ('Póliza','Fecha','Aseguradora','Ramo','Porcentaje','Comisión','IVA','Total')]]
    for x in data['lines']:
        if x.get('rate') is not None and Decimal(x['rate']) == 0:
            continue
        rows.append([p(x['policy']),p(x['date']),p(display_insurer(x['insurer'])),p(x['branch']),
                     p(f"{display_percentage(x['rate'])}%" if x.get("rate") is not None else "-", 'NumberCell'),
                     *[p(f"${Decimal(x[k]):,.2f}", 'NumberCell') for k in ('commission','vat','total')]])
    if len(rows)>1:
        table=Table(rows,colWidths=[83,65,65,39,54,76,65,width-447],repeatRows=1)
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),navy),('VALIGN',(0,0),(-1,-1),'TOP'),
            ('LINEBELOW',(0,1),(-1,-1),.25,accent),('TOPPADDING',(0,0),(-1,-1),5),
            ('BOTTOMPADDING',(0,0),(-1,-1),5),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5)]))
        content.append(table)
    else:
        content.append(Paragraph('Sin comisiones nuevas en este periodo.',styles['Normal']))
    for title, items in [('Ajustes manuales',data['adjustments']),('Saldos anteriores pendientes',data['carry'])]:
        if items:
            content += [Spacer(1,12),Paragraph(title,styles['Heading2'])]
            for x in items:
                text=x.get('concept') or x['month'][:7]
                content.append(Paragraph(escape(f"{text}: ${split_adjustment(x)[0]:,.2f} sin IVA + ${split_adjustment(x)[1]:,.2f} de IVA"),styles['Normal']))
    if data['notes']:
        content += [Spacer(1,12),Paragraph('Notas',styles['Heading2']),Paragraph(escape(data['notes']).replace('\n','<br/>'),styles['Normal'])]
    def footer(canvas, document):
        canvas.setStrokeColor(accent);canvas.line(32,30,A4[0]-32,30)
        canvas.setFont('Helvetica',8);canvas.setFillColor(blue)
        canvas.drawString(32,18,f"TAIICO · {data['month'][:7]} · Versión {data['revision']}")
        canvas.drawRightString(A4[0]-32,18,f'Página {document.page}')
    doc.build(content,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()


def excel_bytes(data):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.drawing.image import Image
    wb=Workbook();ws=wb.active;ws.title='Estado de cuenta'
    def safe(v):
        return "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v
    ws.append(['TAIICO - Estado de cuenta',safe(data['name']),data['month'][:7],data['currency']])
    ws.append(['Concepto','Importe sin IVA','IVA','Total con IVA'])
    for label,net,vat,total in summary_matrix(data):
        ws.append([label,float(net),float(vat),float(total)])
        for col in range(2,5):ws.cell(ws.max_row,col).number_format='#,##0.00'
    ws.append([])
    ws.append(['Póliza','Fecha','Aseguradora','Ramo','Porcentaje','Comisión','IVA','Total'])
    for x in data['lines']:
        if x.get('rate') is not None and Decimal(x['rate']) == 0:
            continue
        ws.append([safe(x['policy']),x['date'],safe(display_insurer(x['insurer'])),safe(x['branch']),display_percentage(x['rate'])/100 if x.get('rate') is not None else None,float(x['commission']),float(x['vat']),float(x['total'])])
        ws.cell(ws.max_row,5).number_format='0%'
        for col in range(6,9): ws.cell(ws.max_row,col).number_format='#,##0.00'
    ws.append([]);ws.append(['Ajustes manuales','Importe sin IVA','IVA','Total con IVA'])
    for x in data['adjustments']: ws.append([safe(x['concept']),*[float(v) for v in (*split_adjustment(x),sum(split_adjustment(x)))]])
    ws.append([]);ws.append(['Saldos anteriores','Importe sin IVA','IVA','Total con IVA'])
    for x in data['carry']:ws.append([x['month'][:7],*[float(v) for v in (*split_adjustment(x),sum(split_adjustment(x)))]])
    ws.append([]);ws.append(['Notas',safe(data['notes'])])
    ws.insert_rows(1)
    logo=Image(str(STATEMENT_LOGO));logo.width=72;logo.height=72;ws.add_image(logo,'A1')
    ws.row_dimensions[1].height=60
    ws.merge_cells('B1:H1');ws['B1']='Estado de cuenta | TAIICO'
    ws['B1'].font=Font(name='Helvetica',size=20,bold=True,color='283E63')
    ws['B1'].alignment=Alignment(vertical='center')
    for row in (2,3,7,9):
        for cell in ws[row]: cell.font=Font(bold=True,color='FFFFFF');cell.fill=PatternFill('solid',fgColor='283E63')
    for row in ws:
        for cell in row: cell.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
    for col in 'ABCDEFGH': ws.column_dimensions[col].width=22
    ws.column_dimensions['A'].width=36;ws.freeze_panes='A10'
    output=io.BytesIO();wb.save(output);return output.getvalue()


@router.get('/{statement_id}/download/{format}')
def download(statement_id: str, format: Literal['pdf','xlsx']):
    data=detail(statement_id)
    content=pdf_bytes(data) if format=='pdf' else excel_bytes(data)
    mime='application/pdf' if format=='pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return Response(content,media_type=mime,headers={'Content-Disposition':f'attachment; filename="estado-{data["month"][:7]}-{statement_id[:8]}.{format}"'})


@router.post('/{statement_id}/send')
def send(statement_id: str, payload: SendInput, profile: AccessProfile = Depends(operate)):
    settings=smtp_settings_for(profile.username)
    if not settings:
        raise HTTPException(409,'Configura tu correo en Configuración de Mail antes de enviar.')
    db=locked_session()
    try:
        row=get_row(db,statement_id)
        person = db.get(Prospector, row.prospector_id)
        if not person or not person.is_active:
            raise HTTPException(409, 'El prospectador está inactivo. No se permite enviar ni reenviar su estado de cuenta.')
        check_revision(row,payload.revision)
        if not statement_has_activity(row): raise HTTPException(409,'El estado no tiene comisiones, ajustes ni saldo pendiente para enviar.')
        if row.status=='pagado': raise HTTPException(409,'El estado ya está pagado; descárgalo si necesitas una copia.')
        if row.delivery_state=='uncertain': raise HTTPException(409,'Primero confirma si el envío anterior llegó, usando Resolver envío.')
        if row.status=='enviado' and not payload.resend: raise HTTPException(409,'Ya fue enviado. Confirma un reenvío explícito.')
        if row.status == 'pendiente':
            from services.cobranza_prospectadores import analyze_import_lines
            for saved in row.lines:
                if saved.get('manual'):
                    continue
                allocation = db.get(ProspectorCommissionAllocation, saved['allocation_id'])
                line = db.get(ProspectorCommissionLine, allocation.line_id) if allocation else None
                if line and line.policy_id:
                    current = analyze_import_lines(db, [{**(line.raw_payload or {}),
                        'policy_number':line.policy_number, 'insurer_id':line.insurer_id,
                        'branch':line.branch, 'currency':line.currency,
                        'movement_date':str(line.movement_date), 'source_commission':str(line.source_commission)}],
                        db.get(ProspectorCommissionPeriod,row.period_id))[0]
                    matches = [x for x in current['allocations'] if x['prospector_id']==row.prospector_id]
                    if len(matches)!=1 or Decimal(matches[0]['commission_rate'])!=Decimal(saved['rate']) or Decimal(matches[0]['calculation']['total_amount'])!=Decimal(saved['total']):
                        raise HTTPException(409,'Cambió la asignación o el porcentaje en Cartera. Genera / actualiza los estados antes de enviar.')
        person = db.get(Prospector, row.prospector_id)
        row.recipient = statement_recipient(row, person)
        EditInput(revision=row.revision,recipient=row.recipient)  # validate resolved email too
        if not row.recipient: raise HTTPException(409,'Agrega el correo del prospectador antes de enviar.')
        data=serialize(row,db.get(Prospector,row.prospector_id),True)
        # Render before claiming: failures here have no ambiguous delivery outcome.
        pdf=pdf_bytes(data);xlsx=excel_bytes(data)
        row.delivery_state='sending';row.delivery_error=None
        event(row,profile.username,'envio_iniciado',recipient=row.recipient,cc=STATEMENT_CC,revision=row.revision,
              snapshot={key:value for key,value in data.items() if key != 'history'})
        db.commit()
    except Exception:
        db.rollback();raise
    finally:
        db.close()
    message=EmailMessage();message['From']=settings['sender'];message['To']=data['recipient']
    message['Cc']=STATEMENT_CC
    message['Subject']=f"TAIICO | Estado de cuenta {data['month'][:7]}"
    _, net, vat, total = summary_matrix(data)[-1]
    message.set_content(
        f"Hola {data['name']},\n\n"
        f"Adjuntamos tu estado de cuenta de {data['month'][:7]}.\n"
        f"Importe Sin IVA: ${net:,.2f}\n"
        f"IVA: ${vat:,.2f}\n"
        f"Total: ${total:,.2f}.\n"
        f"Recuerda enviar la factura correspondiente a {STATEMENT_CC}\n\n"
        "Saludos,\nTAIICO"
    )
    for content,subtype,ext in ((pdf,'pdf','pdf'),(xlsx,'vnd.openxmlformats-officedocument.spreadsheetml.sheet','xlsx')):
        message.add_attachment(content,maintype='application',subtype=subtype,filename=f"Estado-{data['month'][:7]}.{ext}")
    error=None
    try:
        with smtplib.SMTP(settings['host'],settings['port'],timeout=20) as server:
            if settings['use_starttls']:server.starttls(context=smtp_ssl_context())
            server.login(settings['user'],settings['password'])
            server.send_message(message)
    except Exception:
        # Do not blindly retry: SMTP can accept a message before a connection fails.
        error='No se pudo confirmar la entrega al servidor de correo. Revisa Enviados antes de reintentar.'
    db=locked_session()
    try:
        row=get_row(db,statement_id)
        row.delivery_state='uncertain' if error else 'sent';row.delivery_error=error
        if not error:row.status='enviado';row.sent_at=datetime.utcnow()
        row.revision+=1
        event(row,profile.username,'envio_no_confirmado' if error else 'enviado',recipient=data['recipient'],revision=data['revision'])
        db.commit()
    finally:db.close()
    if error:raise HTTPException(502,error)
    return {'sent':True}


class DeliveryResolution(BaseModel):
    revision: int
    delivered: bool


@router.post('/{statement_id}/resolve-delivery')
def resolve_delivery(statement_id: str, payload: DeliveryResolution, profile: AccessProfile = Depends(operate)):
    db = locked_session()
    try:
        row = get_row(db, statement_id)
        if row.revision != payload.revision or row.delivery_state not in ('sending', 'uncertain'):
            raise HTTPException(409, 'El estado cambió o no tiene un envío por resolver.')
        # Do not release a potentially live SMTP request; wait for the timeout or worker interruption.
        if row.delivery_state == 'sending' and row.updated_at and (datetime.utcnow()-row.updated_at).total_seconds() < 180:
            raise HTTPException(409, 'Espera tres minutos para comprobar el resultado del envío en curso.')
        row.delivery_state = 'sent' if payload.delivered else ''
        row.delivery_error = None
        row.status = 'enviado' if payload.delivered else 'pendiente'
        if payload.delivered: row.sent_at = datetime.utcnow()
        row.revision += 1
        event(row, profile.username, 'envio_verificado_manualmente', delivered=payload.delivered)
        db.commit()
        return {'resolved': True}
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
