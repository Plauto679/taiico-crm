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

REQUIRED_COLUMNS = [
    "CONTRATANTE",
    "RFC",
    "PRODUCTO",
    "NPOLIZA",
    "POLORIG",
    "FINIVIG",
    "FFINVIG",
    "NOMBREL",
    "ESTATUS_DE_RENOVACION",
    "EXPEDIENTE",
    "Email",
]


@dataclass
class ParsedRenewalCandidate:
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
        text = str(int(value))
        if len(text) == 8:
            try:
                return datetime.datetime.strptime(text, "%Y%m%d").date()
            except ValueError:
                pass
        try:
            return (datetime.datetime(1899, 12, 30) + datetime.timedelta(days=int(value))).date()
        except Exception:
            return None

    text = str(value).strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
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

    text = str(value).replace("\xa0", "").replace(" ", "")
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
        text = text.replace(".", "").replace(",", ".")

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


def detect_workbook_issues(columns: list[str]) -> list[dict[str, str]]:
    missing = [column for column in REQUIRED_COLUMNS if column not in columns]
    if not missing:
        return []
    return [
        {
            "severity": "critical",
            "issue_type": "missing_required_column",
            "issue_summary": f"MetLife GMM renewal sheet is missing required columns: {', '.join(missing)}",
        }
    ]


def infer_document_status(expediente: Any) -> str:
    expediente = clean_cell(expediente)
    if not expediente:
        return "missing"
    if isinstance(expediente, str) and expediente.lower().startswith("http"):
        return "linked"
    return "present_unstructured"


def calculate_risk_level(days_until_renewal: int | None) -> str:
    if days_until_renewal is None:
        return "unknown"
    if days_until_renewal < 0:
        return "overdue"
    if days_until_renewal <= 30:
        return "high"
    if days_until_renewal <= 60:
        return "medium"
    if days_until_renewal <= 90:
        return "low"
    return "none"


def normalize_row(row_number: int, source_payload: dict[str, Any], today: datetime.date) -> ParsedRenewalCandidate:
    policy_number = normalize_policy_number(source_payload.get("NPOLIZA"))
    original_policy_number = normalize_policy_number(source_payload.get("POLORIG"))
    effective_start_date = parse_date(source_payload.get("FINIVIG"))
    renewal_deadline = parse_date(source_payload.get("FFINVIG"))
    paid_until_date = parse_date(source_payload.get("PAGADOHASTA"))
    premium_amount = parse_money(source_payload.get("PRIMA.1"))

    days_until_renewal = (renewal_deadline - today).days if renewal_deadline else None
    document_status = infer_document_status(source_payload.get("EXPEDIENTE"))

    normalized_payload = {
        "insurer_id": "metlife",
        "product_branch": "GMM",
        "policy_number": policy_number,
        "original_policy_number": original_policy_number,
        "client_name": clean_cell(source_payload.get("CONTRATANTE")),
        "rfc": clean_cell(source_payload.get("RFC")),
        "product_name": clean_cell(source_payload.get("PRODUCTO")),
        "effective_start_date": effective_start_date,
        "renewal_deadline": renewal_deadline,
        "days_until_renewal": days_until_renewal,
        "risk_level": calculate_risk_level(days_until_renewal),
        "payment_scheme_code": clean_cell(source_payload.get("NESQFPAGO")),
        "payment_frequency_source": clean_cell(source_payload.get("NOMBREL")),
        "policy_status_source": clean_cell(source_payload.get("ESTATUS")),
        "collection_channel": clean_cell(source_payload.get("CONDCOB")),
        "promotoria": clean_cell(source_payload.get("PROMOTORIA")),
        "agent_code": clean_cell(source_payload.get("AGENTE")),
        "agent_name": clean_cell(source_payload.get("NOMBRE")),
        "premium_amount": premium_amount,
        "currency": clean_cell(source_payload.get("MONEDA")),
        "paid_until_date": paid_until_date,
        "deductible": parse_money(source_payload.get("DEDUCIBLE")),
        "coinsurance": parse_money(source_payload.get("COASEGURO")),
        "renewal_status_source": clean_cell(source_payload.get("ESTATUS_DE_RENOVACION")),
        "expediente_link": clean_cell(source_payload.get("EXPEDIENTE")),
        "email_link_or_value": clean_cell(source_payload.get("Email")),
        "document_status": document_status,
        "needs_document_retrieval": document_status == "missing",
    }

    issues = []
    if not policy_number:
        issues.append({
            "severity": "high",
            "issue_type": "missing_policy_number",
            "issue_summary": f"MetLife GMM row {row_number} is missing NPOLIZA.",
        })
    if renewal_deadline is None:
        issues.append({
            "severity": "high",
            "issue_type": "missing_renewal_deadline",
            "issue_summary": f"MetLife GMM row {row_number} is missing or has invalid FFINVIG.",
        })
    if document_status == "missing":
        issues.append({
            "severity": "normal",
            "issue_type": "missing_expediente_link",
            "issue_summary": f"MetLife GMM row {row_number} has no EXPEDIENTE link.",
        })

    safe_source_payload = {key: clean_cell(value) for key, value in source_payload.items()}

    return ParsedRenewalCandidate(
        parser_name="metlife_gmm_renewal_workbook",
        parser_version=PARSER_VERSION,
        sheet_name="GMM",
        row_number=row_number,
        row_hash=build_row_hash(safe_source_payload),
        source_payload=safe_source_payload,
        normalized_payload=normalized_payload,
        issues=issues,
    )


def parse_metlife_gmm_renewal_workbook(path: str | Path, today: datetime.date | None = None) -> tuple[list[ParsedRenewalCandidate], list[dict[str, str]]]:
    workbook_path = Path(path)
    today = today or datetime.date.today()
    rows: list[ParsedRenewalCandidate] = []
    workbook_issues: list[dict[str, str]] = []

    excel = pd.ExcelFile(workbook_path)
    if "GMM" not in excel.sheet_names:
        return [], [
            {
                "severity": "critical",
                "issue_type": "missing_sheet",
                "issue_summary": "Workbook is missing required sheet: GMM",
            }
        ]

    df = pd.read_excel(workbook_path, sheet_name="GMM", dtype=object)
    df = df.dropna(how="all")
    columns = [str(column).strip() for column in df.columns]
    df.columns = columns
    workbook_issues.extend(detect_workbook_issues(columns))

    seen_policy_numbers: set[str] = set()
    for index, row in df.iterrows():
        source_payload = {column: row.get(column) for column in columns if not str(column).startswith("Unnamed:")}
        policy_number = normalize_policy_number(source_payload.get("NPOLIZA"))
        if policy_number and policy_number in seen_policy_numbers:
            continue
        if policy_number:
            seen_policy_numbers.add(policy_number)
        rows.append(normalize_row(int(index) + 2, source_payload, today))

    return rows, workbook_issues
