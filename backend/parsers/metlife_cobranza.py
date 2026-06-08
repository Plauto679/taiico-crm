from __future__ import annotations

import datetime
import hashlib
import json
import math
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd


PARSER_VERSION = "1.0.0"

VIDA_REQUIRED_COLUMNS = [
    "Año y mes",
    "# de Póliza",
    "Producto",
    "Estatus Recibo",
    "Fecha de Pago del Recibo",
    "Estatus Póliza",
    "Prima Pagada",
    "Comisión Bruto",
    "Comisión Neta",
]

GMM_REQUIRED_COLUMNS = [
    "Año y mes",
    "# de Póliza",
    "Producto",
    "Estatus Recibo",
    "Fecha de Pago del Recibo",
    "Estatus Póliza",
    "Prima Pagada",
    "Comisión Bruto",
    "Comisión Neta",
    "IVA Causado",
]


@dataclass
class ParsedCobranzaRow:
    parser_name: str
    parser_version: str
    sheet_name: str
    row_number: int
    row_hash: str
    source_payload: dict[str, Any]
    normalized_payload: dict[str, Any]
    issues: list[dict[str, str]]


def clean_cell(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.isna(value):
        return None
    if isinstance(value, str):
        cleaned = value.replace("\xa0", " ").strip()
        return cleaned if cleaned else None
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return value


def normalize_policy_number(value: Any) -> str | None:
    value = clean_cell(value)
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, int):
        return str(value)

    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    return text


def parse_date(value: Any) -> datetime.date | None:
    value = clean_cell(value)
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, (int, float)):
        try:
            return (datetime.datetime(1899, 12, 30) + datetime.timedelta(days=int(value))).date()
        except Exception:
            return None

    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    return None


def parse_money(value: Any) -> Decimal | None:
    value = clean_cell(value)
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))

    text = str(value)
    text = text.replace("\xa0", "").replace(" ", "")
    text = re.sub(r"[^\d,.\-]", "", text)
    if not text:
        return None

    comma_pos = text.rfind(",")
    dot_pos = text.rfind(".")

    if comma_pos > -1 and dot_pos > -1:
        if comma_pos > dot_pos:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif comma_pos > -1:
        decimals = len(text) - comma_pos - 1
        if decimals in {1, 2}:
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif dot_pos > -1:
        decimals = len(text) - dot_pos - 1
        if decimals not in {1, 2}:
            text = text.replace(".", "")

    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    return value


def build_row_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=json_safe)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def detect_sheet_issues(sheet_name: str, columns: list[str]) -> list[dict[str, str]]:
    required = VIDA_REQUIRED_COLUMNS if sheet_name == "Vida" else GMM_REQUIRED_COLUMNS
    missing = [column for column in required if column not in columns]
    if not missing:
        return []
    return [
        {
            "severity": "critical",
            "issue_type": "missing_required_column",
            "issue_summary": f"{sheet_name} is missing required columns: {', '.join(missing)}",
        }
    ]


def normalize_row(sheet_name: str, row_number: int, source_payload: dict[str, Any]) -> ParsedCobranzaRow:
    branch = "VIDA" if sheet_name == "Vida" else "GMM"
    parser_name = "metlife_cobranza_vida" if sheet_name == "Vida" else "metlife_cobranza_gmm"

    policy_number = normalize_policy_number(source_payload.get("# de Póliza"))
    payment_date = parse_date(source_payload.get("Fecha de Pago del Recibo"))
    paid_amount = parse_money(source_payload.get("Prima Pagada"))
    gross_commission = parse_money(source_payload.get("Comisión Bruto"))
    net_commission = parse_money(source_payload.get("Comisión Neta"))
    tax_amount = parse_money(source_payload.get("IVA Causado")) if sheet_name == "GMM" else None

    normalized_payload = {
        "insurer_id": "metlife",
        "product_branch": branch,
        "source_period_key": clean_cell(source_payload.get("Año y mes")),
        "policy_number": policy_number,
        "agent_code": clean_cell(source_payload.get("Clave del Agente")),
        "product_name": clean_cell(source_payload.get("Producto")),
        "collection_channel": clean_cell(source_payload.get("Conducto de Cobro")),
        "msi": clean_cell(source_payload.get("MSI")),
        "receipt_status": clean_cell(source_payload.get("Estatus Recibo")),
        "payment_date": payment_date,
        "policy_status_source": clean_cell(source_payload.get("Estatus Póliza")),
        "policy_life_year": clean_cell(source_payload.get("Año de Vida Póliza")),
        "insured_age": clean_cell(source_payload.get("Edad Asegurado")),
        "insured_gender": clean_cell(source_payload.get("Género")),
        "insured_state": clean_cell(source_payload.get("Estado")),
        "branch_code": clean_cell(source_payload.get("Ramo")),
        "commission_type": clean_cell(source_payload.get("Tipo de Comisión")),
        "paid_amount": paid_amount,
        "gross_commission_amount": gross_commission,
        "net_commission_amount": net_commission,
        "tax_amount": tax_amount,
    }

    issues = []
    if not policy_number:
        issues.append({
            "severity": "high",
            "issue_type": "missing_policy_number",
            "issue_summary": f"{sheet_name} row {row_number} is missing # de Póliza.",
        })
    if normalized_payload["receipt_status"] == "PAGADO" and payment_date is None:
        issues.append({
            "severity": "normal",
            "issue_type": "paid_receipt_without_payment_date",
            "issue_summary": f"{sheet_name} row {row_number} is PAGADO but has no payment date.",
        })
    if source_payload.get("Prima Pagada") is not None and paid_amount is None:
        issues.append({
            "severity": "normal",
            "issue_type": "amount_parse_failure",
            "issue_summary": f"{sheet_name} row {row_number} has an unparseable Prima Pagada value.",
        })

    safe_source_payload = {key: clean_cell(value) for key, value in source_payload.items()}
    row_hash = build_row_hash(safe_source_payload)

    return ParsedCobranzaRow(
        parser_name=parser_name,
        parser_version=PARSER_VERSION,
        sheet_name=sheet_name,
        row_number=row_number,
        row_hash=row_hash,
        source_payload=safe_source_payload,
        normalized_payload=normalized_payload,
        issues=issues,
    )


def parse_metlife_cobranza_workbook(path: str | Path, sheets: list[str] | None = None) -> tuple[list[ParsedCobranzaRow], list[dict[str, str]]]:
    workbook_path = Path(path)
    sheets_to_parse = sheets or ["Vida", "GMM"]
    rows: list[ParsedCobranzaRow] = []
    workbook_issues: list[dict[str, str]] = []

    excel = pd.ExcelFile(workbook_path)
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
        workbook_issues.extend(detect_sheet_issues(sheet_name, columns))

        for index, row in df.iterrows():
            source_payload = {column: row.get(column) for column in columns if not str(column).startswith("Unnamed:")}
            rows.append(normalize_row(sheet_name, int(index) + 2, source_payload))

    return rows, workbook_issues
