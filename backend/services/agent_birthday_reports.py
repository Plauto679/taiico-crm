from __future__ import annotations

import datetime
from html import escape

from services.authorization import normalize_promotoria
from services.mail_configuration import smtp_settings_for
from services.renovaciones import send_email_smtp


DEFAULT_WINDOW_DAYS = 15
MONTH_NAMES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def _spanish_date(value: str) -> str:
    date_value = datetime.date.fromisoformat(value)
    return f"{date_value.day} de {MONTH_NAMES[date_value.month - 1]}"


def _timing_label(days: int) -> str:
    if days == 0:
        return "Hoy"
    if days == 1:
        return "Mañana"
    return f"En {days} días"


def upcoming_agent_birthdays(
    directory: dict,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    promotoria: str | None = None,
) -> list[dict]:
    requested_promotoria = normalize_promotoria(promotoria or "")
    agents: list[dict] = []
    for source in directory.get("agents", []):
        days = source.get("days_until_birthday")
        if not isinstance(days, int) or not 0 <= days <= window_days:
            continue
        promotorias = [
            normalize_promotoria(value)
            for value in source.get("promotorias", [])
            if normalize_promotoria(value)
        ]
        if requested_promotoria and requested_promotoria not in promotorias:
            continue
        agents.append({**source, "promotorias": sorted(set(promotorias))})
    agents.sort(
        key=lambda agent: (
            agent["days_until_birthday"],
            str(agent.get("agent_name") or "").casefold(),
            str(agent.get("rfc") or ""),
        )
    )
    return agents


def agent_birthday_report_subject(*, promotoria: str | None = None) -> str:
    scope = f" · {promotoria}" if promotoria else ""
    return f"Cumpleaños de agentes{scope} · próximos 15 días"


def agent_birthday_report_text(
    agents: list[dict],
    *,
    generated_on: str,
    promotoria: str | None = None,
) -> str:
    scope = f" de la promotoría {promotoria}" if promotoria else ""
    lines = [
        "Cumpleaños de agentes TAIICO",
        f"Fecha: {generated_on}",
        "",
        f"Agentes{scope} que cumplen años entre hoy y los próximos 15 días:",
        "",
    ]
    if not agents:
        lines.append("No hay cumpleaños en este periodo.")
    for agent in agents:
        lines.append(
            f"- {_timing_label(agent['days_until_birthday'])}, "
            f"{_spanish_date(agent['next_birthday'])}: "
            f"{agent.get('agent_name') or 'Sin nombre'} · "
            f"Promotoría: {', '.join(agent.get('promotorias', [])) or '—'} · "
            f"Clave: {', '.join(agent.get('definitive_keys', [])) or '—'}"
        )
    lines.extend(["", "Saludos,", "TAIICO"])
    return "\n".join(lines)


def agent_birthday_report_html(
    agents: list[dict],
    *,
    generated_on: str,
    promotoria: str | None = None,
) -> str:
    rows = []
    for agent in agents:
        promotorias = ", ".join(agent.get("promotorias", [])) or "—"
        keys = ", ".join(agent.get("definitive_keys", [])) or "—"
        rows.append(
            "<tr>"
            f'<td style="padding:12px;border-bottom:1px solid #e2e8f0"><strong>{escape(str(agent.get("agent_name") or "Sin nombre"))}</strong></td>'
            f'<td style="padding:12px;border-bottom:1px solid #e2e8f0">{escape(_spanish_date(agent["next_birthday"]))}</td>'
            f'<td style="padding:12px;border-bottom:1px solid #e2e8f0;font-weight:700;color:#0f4c75">{escape(_timing_label(agent["days_until_birthday"]))}</td>'
            f'<td style="padding:12px;border-bottom:1px solid #e2e8f0">{escape(promotorias)}</td>'
            f'<td style="padding:12px;border-bottom:1px solid #e2e8f0">{escape(keys)}</td>'
            f'<td style="padding:12px;border-bottom:1px solid #e2e8f0">{escape(str(agent.get("email") or "—"))}</td>'
            "</tr>"
        )
    scope = f" · {escape(promotoria)}" if promotoria else ""
    content = (
        '<table style="border-collapse:collapse;width:100%;margin-top:22px">'
        '<thead><tr style="background:#e8f3f8;text-align:left">'
        '<th style="padding:12px">Agente</th><th style="padding:12px">Cumpleaños</th>'
        '<th style="padding:12px">Cuándo</th><th style="padding:12px">Promotoría</th>'
        '<th style="padding:12px">Clave definitiva</th><th style="padding:12px">Correo</th>'
        f"</tr></thead><tbody>{''.join(rows)}</tbody></table>"
        if rows
        else '<div style="margin-top:22px;background:#f8fafc;border:1px solid #e2e8f0;padding:18px;border-radius:10px">No hay cumpleaños en este periodo.</div>'
    )
    return (
        '<!doctype html><html><body style="margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#1e293b">'
        '<div style="max-width:960px;margin:24px auto;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 6px 24px rgba(15,23,42,.08)">'
        '<div style="background:#0f4c75;padding:28px 32px;color:#ffffff">'
        f'<div style="font-size:13px;letter-spacing:1.5px;text-transform:uppercase;opacity:.85">TAIICO · Cumpleaños de agentes{scope}</div>'
        f'<h1 style="margin:8px 0 0;font-size:26px">Próximos 15 días · {len(agents)} cumpleaños</h1>'
        "</div>"
        '<div style="padding:28px 32px">'
        f'<p style="margin-top:0;color:#64748b">Reporte generado el {escape(generated_on)}.</p>'
        f"{content}"
        '<p style="margin:28px 0 0;color:#64748b">Saludos,<br><strong>TAIICO</strong></p>'
        "</div></div></body></html>"
    )


def deliver_agent_birthday_report(
    directory: dict,
    recipients: list[str],
    *,
    sender_username: str,
    promotoria: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> dict:
    agents = upcoming_agent_birthdays(
        directory,
        window_days=window_days,
        promotoria=promotoria,
    )
    generated_on = str(directory.get("generated_on") or datetime.date.today().isoformat())
    send_email_smtp(
        subject=agent_birthday_report_subject(promotoria=promotoria),
        body=agent_birthday_report_text(
            agents,
            generated_on=generated_on,
            promotoria=promotoria,
        ),
        html_body=agent_birthday_report_html(
            agents,
            generated_on=generated_on,
            promotoria=promotoria,
        ),
        recipients=recipients,
        cc_recipients=[],
        settings=smtp_settings_for(sender_username),
    )
    return {
        "generated_on": generated_on,
        "count": len(agents),
        "recipients": recipients,
        "promotoria": promotoria,
    }
