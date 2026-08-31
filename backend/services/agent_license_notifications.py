from __future__ import annotations

import calendar
from datetime import date, datetime
from html import escape
from zoneinfo import ZoneInfo

from services.agentes import load_agents_directory
from services.mail_configuration import smtp_settings_for
from services.pendientes import normalize_report_recipients
from services.renovaciones import send_email_smtp


DEFAULT_TIMEZONE = "America/Mexico_City"


def add_calendar_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _parse_iso_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        return None


def build_agent_license_expiration_report(
    directory: dict,
    *,
    generated_on: date | None = None,
    months_ahead: int = 3,
) -> dict:
    report_date = generated_on or datetime.now(ZoneInfo(DEFAULT_TIMEZONE)).date()
    window_end = add_calendar_months(report_date, months_ahead)
    agents: list[dict] = []
    for agent in directory.get("agents", []):
        expiration = _parse_iso_date(agent.get("fin_vigencia_cedula"))
        if expiration is None or not report_date <= expiration <= window_end:
            continue
        agents.append(
            {
                "nombre": str(agent.get("nombre") or "").strip(),
                "rfc": str(agent.get("rfc") or "").strip(),
                "clave_arranque": str(agent.get("clave_arranque") or "").strip(),
                "clave_definitiva": str(agent.get("clave_definitiva") or "").strip(),
                "promotoria": str(agent.get("promotoria") or "").strip(),
                "correo_personal": str(agent.get("correo_personal") or "").strip(),
                "telefono_particular": str(agent.get("telefono_particular") or "").strip(),
                "estatus_met": str(agent.get("estatus_met") or "").strip(),
                "fin_vigencia_cedula": expiration.isoformat(),
                "dias_restantes": (expiration - report_date).days,
            }
        )
    agents.sort(
        key=lambda item: (
            item["fin_vigencia_cedula"],
            item["nombre"].casefold(),
            item["rfc"],
        )
    )
    return {
        "generated_on": report_date.isoformat(),
        "window_end": window_end.isoformat(),
        "months_ahead": months_ahead,
        "count": len(agents),
        "agents": agents,
    }


def _display_date(value: str) -> str:
    parsed = _parse_iso_date(value)
    return parsed.strftime("%d/%m/%Y") if parsed else "—"


def agent_license_email_subject(report: dict) -> str:
    return f"Cédulas de agentes próximas a vencer - {_display_date(report['generated_on'])}"


def agent_license_email_text(report: dict) -> str:
    lines = [
        "Cédulas de agentes próximas a vencer",
        (
            f"Periodo revisado: {_display_date(report['generated_on'])} al "
            f"{_display_date(report['window_end'])}"
        ),
        f"Agentes identificados: {report['count']}",
        "",
    ]
    if not report["agents"]:
        lines.append("No hay cédulas con vencimiento durante los próximos 3 meses.")
    for agent in report["agents"]:
        lines.append(
            f"- {_display_date(agent['fin_vigencia_cedula'])} | "
            f"{agent['nombre'] or '—'} | RFC {agent['rfc'] or '—'} | "
            f"Clave {agent['clave_definitiva'] or agent['clave_arranque'] or '—'} | "
            f"Promotoría {agent['promotoria'] or '—'} | "
            f"Correo {agent['correo_personal'] or '—'} | "
            f"Teléfono {agent['telefono_particular'] or '—'}"
        )
    lines.extend(
        [
            "",
            "Favor de dar seguimiento con anticipación para evitar que la cédula expire.",
        ]
    )
    return "\n".join(lines)


def agent_license_email_html(report: dict) -> str:
    cell_style = "padding:8px;border:1px solid #b8c7d3;text-align:left"
    rows = "".join(
        "<tr>"
        f"<td style=\"{cell_style}\">{escape(_display_date(agent['fin_vigencia_cedula']))}</td>"
        f"<td style=\"{cell_style}\">{escape(agent['nombre'] or '—')}</td>"
        f"<td style=\"{cell_style}\">{escape(agent['rfc'] or '—')}</td>"
        f"<td style=\"{cell_style}\">{escape(agent['clave_arranque'] or '—')}</td>"
        f"<td style=\"{cell_style}\">{escape(agent['clave_definitiva'] or '—')}</td>"
        f"<td style=\"{cell_style}\">{escape(agent['promotoria'] or '—')}</td>"
        f"<td style=\"{cell_style}\">{escape(agent['correo_personal'] or '—')}</td>"
        f"<td style=\"{cell_style}\">{escape(agent['telefono_particular'] or '—')}</td>"
        f"<td style=\"{cell_style}\">{escape(agent['estatus_met'] or '—')}</td>"
        "</tr>"
        for agent in report["agents"]
    )
    if not rows:
        rows = (
            '<tr><td colspan="9" style="padding:8px;border:1px solid #b8c7d3">'
            "No hay cédulas con vencimiento durante los próximos 3 meses.</td></tr>"
        )
    headings = "".join(
        f'<th style="{cell_style};background:#e8f1f8">{heading}</th>'
        for heading in (
            "Vencimiento",
            "Agente",
            "RFC",
            "Clave arranque",
            "Clave definitiva",
            "Promotoría",
            "Correo",
            "Teléfono",
            "Estatus",
        )
    )
    return (
        '<!doctype html><html><body style="font-family:Arial,sans-serif;color:#172033">'
        '<h1 style="color:#0b4a73">Cédulas de agentes próximas a vencer</h1>'
        f"<p>Periodo revisado: <strong>{escape(_display_date(report['generated_on']))}</strong> al "
        f"<strong>{escape(_display_date(report['window_end']))}</strong></p>"
        f"<p>Agentes identificados: <strong>{report['count']}</strong></p>"
        '<table style="border-collapse:collapse;width:100%;font-size:13px">'
        f"<thead><tr>{headings}</tr></thead><tbody>{rows}</tbody></table>"
        '<p style="margin-top:20px">Favor de dar seguimiento con anticipación para '
        "evitar que la cédula expire.</p></body></html>"
    )


def deliver_agent_license_expiration_report(
    recipients: list[str],
    *,
    sender_username: str,
    generated_on: date | None = None,
    months_ahead: int = 3,
) -> dict:
    normalized_recipients = normalize_report_recipients(recipients)
    report = build_agent_license_expiration_report(
        load_agents_directory(),
        generated_on=generated_on,
        months_ahead=months_ahead,
    )
    send_email_smtp(
        subject=agent_license_email_subject(report),
        body=agent_license_email_text(report),
        html_body=agent_license_email_html(report),
        recipients=normalized_recipients,
        cc_recipients=[],
        settings=smtp_settings_for(sender_username),
    )
    return {
        "sent": True,
        "recipients": normalized_recipients,
        "sender_username": sender_username,
        **report,
    }
