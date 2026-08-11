from __future__ import annotations

import datetime
import re
from collections import defaultdict
from html import escape


DEFAULT_WINDOW_DAYS = 7
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


def _display_name(value: str) -> str:
    return " ".join(part for part in re.split(r"[/\\]+|\s+", value.strip()) if part)


def _spanish_date(value: str) -> str:
    date_value = datetime.date.fromisoformat(value)
    return f"{date_value.day} de {MONTH_NAMES[date_value.month - 1]}"


def _timing_label(days: int) -> str:
    if days == 0:
        return "Hoy"
    if days == 1:
        return "Mañana"
    return f"En {days} días"


def build_agent_birthday_notifications(
    directory: dict,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    agent_details: dict[str, dict] = {}
    for client in directory.get("clients", []):
        days = client.get("days_until_birthday")
        if not isinstance(days, int) or not 0 <= days <= window_days:
            continue
        key = (client.get("agent_rfc") or client.get("agent_label") or "").strip()
        if not key:
            continue
        grouped[key].append(client)
        agent_details[key] = {
            "agent_rfc": (client.get("agent_rfc") or "").strip(),
            "agent_name": (client.get("agent_name") or "").strip(),
            "agent_label": (client.get("agent_label") or "").strip(),
            "agent_email": (client.get("agent_email") or "").strip().casefold(),
        }

    notifications = []
    missing_email = []
    for key, clients in grouped.items():
        details = agent_details[key]
        clients.sort(
            key=lambda item: (
                item["days_until_birthday"],
                item.get("client_name", "").casefold(),
            )
        )
        notification = {**details, "clients": clients}
        if details["agent_email"] and "@" in details["agent_email"]:
            notifications.append(notification)
        else:
            missing_email.append(notification)

    sort_key = lambda item: (
        item.get("agent_name", "").casefold(),
        item.get("agent_rfc", ""),
    )
    notifications.sort(key=sort_key)
    missing_email.sort(key=sort_key)
    return {
        "generated_on": directory.get("generated_on"),
        "window_days": window_days,
        "notifications": notifications,
        "missing_email": missing_email,
        "birthday_count": sum(len(item["clients"]) for item in notifications),
    }


def birthday_email_subject(notification: dict, *, test: bool = False) -> str:
    count = len(notification["clients"])
    prefix = "[PRUEBA] " if test else ""
    noun = "cumpleaños" if count == 1 else "cumpleaños"
    return f"{prefix}{count} {noun} de tus clientes esta semana"


def birthday_email_text(notification: dict) -> str:
    agent_name = _display_name(notification.get("agent_name") or "Agente")
    lines = [
        f"Hola, {agent_name}:",
        "",
        "Estos son los cumpleaños de tus clientes con póliza vigente entre hoy y los próximos 7 días:",
        "",
    ]
    for client in notification["clients"]:
        lines.append(
            f"- {_timing_label(client['days_until_birthday'])}, "
            f"{_spanish_date(client['next_birthday'])}: "
            f"{_display_name(client['client_name'])}"
        )
    lines.extend(
        [
            "",
            "Te recomendamos preparar tu felicitación con anticipación.",
            "",
            "Saludos,",
            "TAIICO",
        ]
    )
    return "\n".join(lines)


def birthday_email_html(notification: dict) -> str:
    agent_name = escape(_display_name(notification.get("agent_name") or "Agente"))
    rows = []
    for client in notification["clients"]:
        rows.append(
            "<tr>"
            f"<td style=\"padding:12px;border-bottom:1px solid #e2e8f0;font-weight:700;color:#0f4c75\">{escape(_timing_label(client['days_until_birthday']))}</td>"
            f"<td style=\"padding:12px;border-bottom:1px solid #e2e8f0\">{escape(_spanish_date(client['next_birthday']))}</td>"
            f"<td style=\"padding:12px;border-bottom:1px solid #e2e8f0\"><strong>{escape(_display_name(client['client_name']))}</strong></td>"
            "</tr>"
        )
    count = len(notification["clients"])
    return (
        "<!doctype html><html><body style=\"margin:0;background:#f1f5f9;font-family:Arial,sans-serif;color:#1e293b\">"
        "<div style=\"max-width:720px;margin:24px auto;background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 6px 24px rgba(15,23,42,.08)\">"
        "<div style=\"background:#0f4c75;padding:28px 32px;color:#ffffff\">"
        "<div style=\"font-size:13px;letter-spacing:1.5px;text-transform:uppercase;opacity:.85\">TAIICO · Cumpleaños</div>"
        f"<h1 style=\"margin:8px 0 0;font-size:26px\">{count} oportunidad{'es' if count != 1 else ''} para estar cerca</h1>"
        "</div>"
        "<div style=\"padding:28px 32px\">"
        f"<p style=\"font-size:17px;margin-top:0\">Hola, <strong>{agent_name}</strong>:</p>"
        "<p>Estos son los cumpleaños de tus clientes con póliza vigente entre hoy y los próximos 7 días.</p>"
        "<table style=\"border-collapse:collapse;width:100%;margin:22px 0\">"
        "<thead><tr style=\"background:#e8f3f8;text-align:left\"><th style=\"padding:12px\">Cuándo</th><th style=\"padding:12px\">Fecha</th><th style=\"padding:12px\">Cliente</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
        "<div style=\"background:#fff7ed;border-left:4px solid #f59e0b;padding:14px 16px;border-radius:6px\">Te recomendamos preparar tu felicitación con anticipación.</div>"
        "<p style=\"margin:28px 0 0;color:#64748b\">Saludos,<br><strong>TAIICO</strong></p>"
        "</div></div></body></html>"
    )
