from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from parsers.metlife_cobranza import (
    ParsedCobranzaRow,
    build_row_hash,
    clean_cell,
    parse_date,
    parse_money,
    normalize_policy_number,
)


PARSER_VERSION = "1.0.0"

REQUIRED_COLUMNS = [
    "Daños/Vida",
    "Grupo",
    "Oficina",
    "Ramo",
    "Póliza",
    "Contratante",
    "Clave Agente",
    "Tipo de Cambio",
    "# Recibo",
    "Serie de Recibo",
    "Prima Total",
    "Prima Neta",
    "% Comisión pagado",
    "Comisión de derecho",
    "Monto Comisión Neta",
    "Total Comisión pagado",
    "# Liquidación",
    "# Comprobante",
    "Fecha aplicación de la póliza",
]

CONSOLIDATED_REQUIRED_COLUMNS = [
    "FECHA DE CORTE",
    "OFICINA",
    "RAMO",
    "POLIZA",
    "RECIBO",
    "SERIE_RECIBO",
    "FECHAAPLICACION",
    "ASEGURADO",
    "PRIMATOTAL",
    "PRIMANETA",
    "COMNETA",
    "%COMISION",
    "COMDERECHO",
    "TOTAL",
    "Moneda",
]


def normalize_product_branch(value: Any) -> str | None:
    value = clean_cell(value)
    if value is None:
        return None

    text = str(value).strip().upper()
    if text in {"DAÑO", "DANIO", "DAÑOS", "DANOS", "NO VIDA", "NO-VIDA"}:
        return "DANOS"
    if text == "VIDA":
        return "VIDA"
    return text


def detect_sheet_format(columns: list[str]) -> str | None:
    if all(column in columns for column in REQUIRED_COLUMNS):
        return "insurer_statement"
    if all(column in columns for column in CONSOLIDATED_REQUIRED_COLUMNS):
        return "consolidated_statement"
    return None


def detect_workbook_issues(sheet_name: str, columns: list[str]) -> list[dict[str, str]]:
    if detect_sheet_format(columns):
        return []

    if ("POLIZA" in columns or "PÓLIZA" in columns) and "PROSPECTADOR" in columns and "PORCENTAJE" in columns:
        return []

    legacy_missing = [column for column in REQUIRED_COLUMNS if column not in columns]
    consolidated_missing = [column for column in CONSOLIDATED_REQUIRED_COLUMNS if column not in columns]

    return [
        {
            "severity": "critical",
            "issue_type": "missing_required_column",
            "issue_summary": (
                f"SURA {sheet_name} does not match a supported cobranza format. "
                f"Missing legacy columns: {', '.join(legacy_missing)}. "
                f"Missing consolidated columns: {', '.join(consolidated_missing)}."
            ),
        }
    ]


def normalize_insurer_statement_row(row_number: int, source_payload: dict[str, Any]) -> ParsedCobranzaRow:
    policy_number = normalize_policy_number(source_payload.get("Póliza"))
    receipt_number = normalize_policy_number(source_payload.get("# Recibo"))
    payment_date = parse_date(source_payload.get("Fecha aplicación de la póliza"))
    paid_amount = parse_money(source_payload.get("Prima Total"))
    net_premium_amount = parse_money(source_payload.get("Prima Neta"))
    commission_right_amount = parse_money(source_payload.get("Comisión de derecho"))
    net_commission_amount = parse_money(source_payload.get("Monto Comisión Neta"))
    total_commission_paid = parse_money(source_payload.get("Total Comisión pagado"))
    exchange_rate = parse_money(source_payload.get("Tipo de Cambio"))

    normalized_payload = {
        "insurer_id": "sura",
        "product_branch": normalize_product_branch(source_payload.get("Daños/Vida")),
        "policy_number": policy_number,
        "receipt_number": receipt_number,
        "receipt_series": clean_cell(source_payload.get("Serie de Recibo")),
        "client_name": clean_cell(source_payload.get("Contratante")),
        "agent_code": clean_cell(source_payload.get("Clave Agente")),
        "group_code": clean_cell(source_payload.get("Grupo")),
        "office_code": clean_cell(source_payload.get("Oficina")),
        "branch_code": clean_cell(source_payload.get("Ramo")),
        "exchange_rate": exchange_rate,
        "paid_amount": paid_amount,
        "net_premium_amount": net_premium_amount,
        "commission_percentage_paid": parse_money(source_payload.get("% Comisión pagado")),
        "commission_right_amount": commission_right_amount,
        "net_commission_amount": net_commission_amount,
        "total_commission_paid": total_commission_paid,
        "liquidation_number": normalize_policy_number(source_payload.get("# Liquidación")),
        "voucher_number": normalize_policy_number(source_payload.get("# Comprobante")),
        "payment_date": payment_date,
        "source_format": "insurer_statement",
    }

    issues = []
    if not policy_number:
        issues.append({
            "severity": "high",
            "issue_type": "missing_policy_number",
            "issue_summary": f"SURA Cobranza row {row_number} is missing Póliza.",
        })
    if not receipt_number:
        issues.append({
            "severity": "normal",
            "issue_type": "missing_receipt_number",
            "issue_summary": f"SURA Cobranza row {row_number} is missing # Recibo.",
        })
    if source_payload.get("Prima Total") is not None and paid_amount is None:
        issues.append({
            "severity": "normal",
            "issue_type": "amount_parse_failure",
            "issue_summary": f"SURA Cobranza row {row_number} has an unparseable Prima Total value.",
        })
    if source_payload.get("Fecha aplicación de la póliza") is not None and payment_date is None:
        issues.append({
            "severity": "normal",
            "issue_type": "date_parse_failure",
            "issue_summary": f"SURA Cobranza row {row_number} has an unparseable Fecha aplicación de la póliza value.",
        })

    safe_source_payload = {key: clean_cell(value) for key, value in source_payload.items()}

    return ParsedCobranzaRow(
        parser_name="sura_cobranza_workbook",
        parser_version=PARSER_VERSION,
        sheet_name="Cobranza",
        row_number=row_number,
        row_hash=build_row_hash(safe_source_payload),
        source_payload=safe_source_payload,
        normalized_payload=normalized_payload,
        issues=issues,
    )


def normalize_consolidated_statement_row(row_number: int, source_payload: dict[str, Any]) -> ParsedCobranzaRow:
    policy_number = normalize_policy_number(source_payload.get("POLIZA"))
    receipt_number = normalize_policy_number(source_payload.get("RECIBO"))
    payment_date = parse_date(source_payload.get("FECHAAPLICACION"))
    source_cutoff_date = parse_date(source_payload.get("FECHA DE CORTE"))
    paid_amount = parse_money(source_payload.get("PRIMATOTAL"))
    net_premium_amount = parse_money(source_payload.get("PRIMANETA"))
    net_commission_amount = parse_money(source_payload.get("COMNETA"))
    total_commission_paid = parse_money(source_payload.get("TOTAL"))

    normalized_payload = {
        "insurer_id": "sura",
        "product_branch": normalize_product_branch(source_payload.get("Ramo")),
        "policy_number": policy_number,
        "receipt_number": receipt_number,
        "receipt_series": clean_cell(source_payload.get("SERIE_RECIBO")),
        "client_name": clean_cell(source_payload.get("ASEGURADO")),
        "agent_code": clean_cell(source_payload.get("AGENTE")),
        "agency_name": clean_cell(source_payload.get("Agente")),
        "office_code": clean_cell(source_payload.get("OFICINA")),
        "branch_code": clean_cell(source_payload.get("RAMO")),
        "currency": clean_cell(source_payload.get("Moneda")),
        "source_cutoff_date": source_cutoff_date,
        "policy_effective_start": parse_date(source_payload.get("INIVIGENCIA")),
        "paid_amount": paid_amount,
        "net_premium_amount": net_premium_amount,
        "commission_percentage_paid": parse_money(source_payload.get("%COMISION")),
        "commission_right_amount": parse_money(source_payload.get("COMDERECHO")),
        "net_commission_amount": net_commission_amount,
        "total_commission_paid": total_commission_paid,
        "payment_date": payment_date,
        "prospectador_name": clean_cell(source_payload.get("Prospectador")),
        "prospectador_percentage": parse_money(source_payload.get("% de Prospectador")),
        "prospectador_commission_amount": parse_money(source_payload.get("Comision Prospectador")),
        "source_format": "consolidated_statement",
    }

    issues = []
    if not policy_number:
        issues.append({
            "severity": "high",
            "issue_type": "missing_policy_number",
            "issue_summary": f"SURA Cobranza row {row_number} is missing POLIZA.",
        })
    if not receipt_number:
        issues.append({
            "severity": "normal",
            "issue_type": "missing_receipt_number",
            "issue_summary": f"SURA Cobranza row {row_number} is missing RECIBO.",
        })
    if source_payload.get("PRIMATOTAL") is not None and paid_amount is None:
        issues.append({
            "severity": "normal",
            "issue_type": "amount_parse_failure",
            "issue_summary": f"SURA Cobranza row {row_number} has an unparseable PRIMATOTAL value.",
        })
    if source_payload.get("FECHAAPLICACION") is not None and payment_date is None:
        issues.append({
            "severity": "normal",
            "issue_type": "date_parse_failure",
            "issue_summary": f"SURA Cobranza row {row_number} has an unparseable FECHAAPLICACION value.",
        })

    safe_source_payload = {key: clean_cell(value) for key, value in source_payload.items()}

    return ParsedCobranzaRow(
        parser_name="sura_cobranza_workbook",
        parser_version=PARSER_VERSION,
        sheet_name="Cobranza",
        row_number=row_number,
        row_hash=build_row_hash(safe_source_payload),
        source_payload=safe_source_payload,
        normalized_payload=normalized_payload,
        issues=issues,
    )


def parse_sura_cobranza_workbook(path: str | Path, sheets: list[str] | None = None) -> tuple[list[ParsedCobranzaRow], list[dict[str, str]]]:
    workbook_path = Path(path)
    rows: list[ParsedCobranzaRow] = []
    workbook_issues: list[dict[str, str]] = []

    excel = pd.ExcelFile(workbook_path)
    sheets_to_parse = sheets or excel.sheet_names
    for sheet_name in sheets_to_parse:
        if sheet_name not in excel.sheet_names:
            workbook_issues.append({
                "severity": "critical",
                "issue_type": "missing_sheet",
                "issue_summary": f"Workbook is missing required sheet: {sheet_name}",
            })
            continue

        df = pd.read_excel(workbook_path, sheet_name=sheet_name, dtype=object)
        df = df.dropna(how="all")
        columns = [str(column).strip() for column in df.columns]
        df.columns = columns
        workbook_issues.extend(detect_workbook_issues(sheet_name, columns))

        sheet_format = detect_sheet_format(columns)
        if not sheet_format:
            continue

        for index, row in df.iterrows():
            source_payload = {column: row.get(column) for column in columns if not str(column).startswith("Unnamed:")}
            if sheet_format == "consolidated_statement":
                rows.append(normalize_consolidated_statement_row(int(index) + 2, source_payload))
            else:
                rows.append(normalize_insurer_statement_row(int(index) + 2, source_payload))

    return rows, workbook_issues
