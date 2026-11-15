"""Read-only weekly renewal monitoring for the direct-to-client portfolio."""
from __future__ import annotations

import calendar
import csv
import io
import unicodedata
from datetime import date, timedelta
from html import escape

from database import Policy, Renewal, SessionLocal
from services.renewal_agent_api import TAIICO_AGENT_CODES
from services.renovaciones import metlife_gmm_agents, send_email_smtp
from services.mail_configuration import smtp_settings_for


def normalized(value: object) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').strip().casefold()) if not unicodedata.combining(c))


def window_start(today: date) -> date:
    month_index = today.year * 12 + today.month - 1 - 3
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    return date(year, month, min(today.day, calendar.monthrange(year, month)[1]))


def traffic_light(days: int) -> str | None:
    if days > 45:
        return None
    return 'rojo' if days <= 10 else 'amarillo' if days <= 30 else 'verde'


SEMAPHORE = {'rojo': '🔴', 'amarillo': '🟡', 'verde': '🟢'}


def is_closed(row: dict) -> bool:
    # A sent renewal is no longer pending delivery, even before renewal is confirmed.
    if normalized(row.get('status')) in {'sent', 'delivered'} or normalized(row.get('renewal_status')).startswith(('enviado', 'enviada')):
        return True
    return normalized(row.get('status')) in {'renewed', 'cancelled', 'canceled'} or normalized(row.get('renewal_status')) in {
        'renovada', 'renovado', 'renovado automatico', 'renovada automaticamente',
        'renovada manual', 'cancelada', 'cancelado', 'cancelada / falta de pago',
    }


def build_report(rows: list[dict], generated_on: date) -> dict:
    # Identity includes the renewal period: a past renewal never closes the next one.
    grouped: dict[tuple, list[dict]] = {}
    for row in rows:
        code = str(row.get('agent_code') or '').strip().removesuffix('.0')
        if code not in TAIICO_AGENT_CODES:
            continue
        deadline = date.fromisoformat(str(row['deadline']))
        if deadline < window_start(generated_on) or traffic_light((deadline - generated_on).days) is None:
            continue
        grouped.setdefault((row['policy_number'], deadline.isoformat()), []).append(row)
    policies = []
    for matches in grouped.values():
        if any(is_closed(row) for row in matches):
            continue
        row = dict(matches[-1])
        row['days'] = (date.fromisoformat(row['deadline']) - generated_on).days
        row['traffic_light'] = traffic_light(row['days'])
        policies.append(row)
    policies.sort(key=lambda row: (row['days'], row['policy_number']))
    return {
        'generated_on': generated_on.isoformat(),
        'window_start': window_start(generated_on).isoformat(),
        'window_end': (generated_on + timedelta(days=45)).isoformat(),
        'scope': 'MetLife GMM · cartera con envío directo al cliente',
        'agent_codes': sorted(TAIICO_AGENT_CODES),
        'counts': {color: sum(row['traffic_light'] == color for row in policies) for color in ('rojo','amarillo','verde')},
        'overdue_count': sum(row['days'] < 0 for row in policies),
        'count': len(policies), 'policies': policies,
    }


def load_report(generated_on: date) -> dict:
    agents = metlife_gmm_agents()
    with SessionLocal() as db:
        renewals = db.query(Renewal).join(Policy, Renewal.original_policy_id == Policy.id).filter(
            Policy.insurer_id == 'metlife', Policy.product_id == 'prod_met_gmm',
            Renewal.renewal_deadline >= window_start(generated_on),
            Renewal.renewal_deadline <= generated_on + timedelta(days=45),
        ).order_by(Renewal.updated_at.asc()).all()
        rows = []
        for renewal in renewals:
            policy = renewal.original_policy
            number = str(policy.policy_number).strip()
            deadline = renewal.renewal_deadline.isoformat()
            agent = agents.get((number, deadline), agents.get((number, ''), {}))
            rows.append({
                'policy_number': number, 'deadline': deadline,
                'client': policy.client.full_name if policy.client else '',
                'agent_code': agent.get('AGENTE', ''), 'agent_name': agent.get('NOMBRE', ''),
                'status': renewal.status, 'renewal_status': renewal.insurer_response or '',
            })
    return build_report(rows, generated_on)


def report_text(report: dict) -> str:
    lines = ['Informe de Renovaciones cartera Taiico', f"Corte: {report['generated_on']} · {report['scope']}",
             'Rojo: vencidas y 0–10 días | Amarillo: 11–30 días | Verde: 31–45 días para el fin de vigencia.',
             'Solo pólizas pendientes de envío; vencidas de los últimos tres meses y próximas a vencer en 45 días. Se excluyen enviadas, renovadas y canceladas.',
             ' | '.join(f'{SEMAPHORE[color]} {color.title()}: {count}' for color, count in report['counts'].items())]
    for row in report['policies'][:50]:
        lines.append(f"{SEMAPHORE[row['traffic_light']]} {row['traffic_light'].upper()} | {row['days']} días | {row['deadline']} | {row['policy_number']} | {row['client']} | {row['agent_name']} ({row['agent_code']}) | {row['renewal_status'] or 'Sin estatus registrado'}")
    if not report['policies']:
        lines.append('No hay renovaciones pendientes de envío en el periodo revisado para esta cartera.')
    lines.append('Consulta el archivo CSV adjunto para el detalle completo de todas las pólizas.')
    return '\n'.join(lines)


def semaphore_summary_html(report: dict) -> str:
    # Same compact three-column count table as the Pendientes email.
    styles = {
        'verde': ('#166534', '#dcfce7', 'Verde (31–45 días)'),
        'amarillo': ('#854d0e', '#fef9c3', 'Amarillo (11–30 días)'),
        'rojo': ('#991b1b', '#fee2e2', 'Rojo (vencidas y 0–10 días)'),
    }
    headings, cells = [], []
    for color, (foreground, background, label) in styles.items():
        headings.append(f'<th scope="col" style="padding:10px;border:1px solid #cbd5e1;text-align:center">{label}</th>')
        cells.append(
            f'<td style="padding:10px;border:1px solid #cbd5e1;color:{foreground};'
            f'background:{background};font-weight:700;text-align:center">{report["counts"][color]}</td>'
        )
    return (
        '<h2>Semáforo de renovaciones pendientes de envío</h2>'
        '<table aria-label="Semáforo condensado" style="width:100%;border-collapse:collapse">'
        '<thead><tr>' + ''.join(headings) + '</tr></thead><tbody><tr>'
        + ''.join(cells) + '</tr></tbody></table>'
    )


def report_html(report: dict) -> str:
    colors = {'rojo': ('#fee2e2','#991b1b'), 'amarillo': ('#fef3c7','#92400e'), 'verde': ('#dcfce7','#166534')}
    cell = 'padding:10px;border-bottom:1px solid #dbe3eb;text-align:left'
    sections = []
    for color, (background, ink) in colors.items():
        policies = [row for row in report['policies'] if row['traffic_light'] == color]
        bounds = {'rojo':'Vencidas y 0–10 días','amarillo':'11–30 días','verde':'31–45 días'}[color]
        sections.append(f'<h2 style="padding:12px;background:{background};color:{ink}">{SEMAPHORE[color]} {color.title()} · {bounds} · {len(policies)} pólizas</h2>')
        if not policies:
            sections.append('<p>Sin pólizas en este rango.</p>')
            continue
        if len(policies) > 50:
            sections.append('<p>Vista resumida de 50 pólizas próximas a vencer o vencidas más recientes. El CSV adjunto contiene el detalle completo, dentro del periodo revisado.</p>')
            policies = sorted(policies[-50:], key=lambda row: (row['days'], row['policy_number']))
        headings = ''.join(f'<th style="{cell}">{heading}</th>' for heading in ('Semáforo','Póliza','Contratante','Agente','Fin de vigencia','Días restantes','Estatus registrado'))
        table_rows = []
        for row in policies:
            values = [f"{SEMAPHORE[color]} {color.title()}", row['policy_number'], row['client'], f"{row['agent_name']} ({row['agent_code']})", row['deadline'], row['days'], row['renewal_status'] or 'Sin estatus registrado']
            table_rows.append('<tr>'+''.join(f'<td style="{cell}">{escape(str(value))}</td>' for value in values)+'</tr>')
        sections.append(f'<table style="border-collapse:collapse;width:100%;font-size:13px"><thead><tr>{headings}</tr></thead><tbody>'+''.join(table_rows)+'</tbody></table>')
    return ('<!doctype html><html><body style="font-family:Arial,sans-serif;color:#172033;margin:24px">'
            '<h1 style="background:#093b5b;color:white;padding:20px;border-bottom:5px solid #00afd4">TAIICO · Informe de Renovaciones cartera Taiico</h1>'
            f"<p>Corte: <strong>{escape(report['generated_on'])}</strong> · Periodo: {escape(report['window_start'])} al {escape(report['window_end'])} · Hora de CDMX.</p>"
            f"<p>{escape(report['scope'])}. <strong>{report['count']} pólizas pendientes de envío; {report['overdue_count']} vencidas.</strong></p>"
            '<p>Días restantes para el fin de vigencia. Solo pendientes de envío. Se excluyen las pólizas ya enviadas, renovadas o canceladas. Las vencidas se limitan a los últimos tres meses.</p>'
            + semaphore_summary_html(report) + ''.join(sections) + '<p><a href="https://taiico-crm.com/renovaciones">Consultar Renovaciones en el CRM</a></p></body></html>')


def report_csv(report: dict) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Semáforo','Póliza','Contratante','Agente','Clave agente','Fin de vigencia','Días restantes','Estatus registrado'])
    for row in report['policies']:
        values = [row['traffic_light'], row['policy_number'], row['client'], row['agent_name'], row['agent_code'], row['deadline'], row['days'], row['renewal_status'] or 'Sin estatus registrado']
        writer.writerow([("'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value) if isinstance(value, str) else value for value in values])
    return output.getvalue().encode('utf-8-sig')


def deliver_report(report: dict, config: dict) -> None:
    send_email_smtp(
        subject=f"Informe de Renovaciones cartera Taiico · {report['generated_on']}",
        body=report_text(report), html_body=report_html(report),
        recipients=config['recipients'], cc_recipients=config.get('cc_recipients', []),
        settings=smtp_settings_for(config['sender']),
        attachments=[{'name': f"renovaciones-taiico-{report['generated_on']}.csv", 'content': report_csv(report), 'mime_type': 'text/csv'}],
    )
