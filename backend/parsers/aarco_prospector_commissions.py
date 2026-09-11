from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

from parsers.metlife_cobranza import (
    ParsedCobranzaRow,
    build_row_hash,
    clean_cell,
    normalize_policy_number,
    parse_date,
    parse_money,
)


PARSER_VERSION = "1.0.0"


def normalize_header(value: object) -> str:
    text = " ".join(str(value or "").replace("\n", " ").split()).upper()
    text = "".join(
        character
        for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^A-Z0-9%$]+", "_", text).strip("_")


def parse_aarco_prospector_workbook(
    path: str | Path,
) -> tuple[list[ParsedCobranzaRow], list[dict[str, str]]]:
    workbook_path = Path(path)
    rows: list[ParsedCobranzaRow] = []
    workbook_issues: list[dict[str, str]] = []
    excel = pd.ExcelFile(workbook_path)

    for sheet_name in excel.sheet_names:
        frame = pd.read_excel(workbook_path, sheet_name=sheet_name, dtype=object)
        frame = frame.dropna(how="all")
        if frame.empty:
            continue
        columns = [str(column).strip() for column in frame.columns]
        frame.columns = columns
        aliases = {normalize_header(column): column for column in columns}
        required = ["CIA", "NUM_POL", "F_COBRO", "COM_APL_MN"]
        missing = [column for column in required if column not in aliases]
        if missing:
            workbook_issues.append({
                "severity": "critical",
                "issue_type": "missing_required_column",
                "issue_summary": (
                    f"AARCO {sheet_name} no contiene las columnas requeridas: "
                    f"{', '.join(missing)}"
                ),
            })
            continue

        for index, source_row in frame.iterrows():
            source_payload = {
                column: clean_cell(source_row.get(column))
                for column in columns
                if not str(column).startswith("Unnamed:")
            }
            policy_number = normalize_policy_number(source_row.get(aliases["NUM_POL"]))
            payment_date = parse_date(source_row.get(aliases["F_COBRO"]))
            commission = parse_money(source_row.get(aliases["COM_APL_MN"]))
            insurer = clean_cell(source_row.get(aliases["CIA"]))
            issues: list[dict[str, str]] = []
            if not policy_number:
                issues.append({
                    "severity": "high",
                    "issue_type": "missing_policy_number",
                    "issue_summary": f"AARCO fila {int(index) + 2} no contiene póliza.",
                })
            if payment_date is None:
                issues.append({
                    "severity": "high",
                    "issue_type": "date_parse_failure",
                    "issue_summary": f"AARCO fila {int(index) + 2} no contiene una fecha válida.",
                })
            if commission is None:
                issues.append({
                    "severity": "high",
                    "issue_type": "amount_parse_failure",
                    "issue_summary": f"AARCO fila {int(index) + 2} no contiene una comisión válida.",
                })

            rows.append(ParsedCobranzaRow(
                parser_name="aarco_prospector_commissions",
                parser_version=PARSER_VERSION,
                sheet_name=sheet_name,
                row_number=int(index) + 2,
                row_hash=build_row_hash(source_payload),
                source_payload=source_payload,
                normalized_payload={
                    "insurer_id": str(insurer or "aarco").strip().casefold(),
                    "product_branch": "DANOS",
                    "policy_number": policy_number,
                    "client_name": clean_cell(source_row.get(aliases.get("CLIENTE", ""))),
                    "payment_date": payment_date,
                    "net_premium_amount": parse_money(source_row.get(aliases.get("PRIMA_NETA_MN", ""))),
                    "source_commission_amount": commission,
                    "currency": "MXN",
                    "source_format": "aarco_consolidated",
                },
                issues=issues,
            ))

    if not rows and not workbook_issues:
        workbook_issues.append({
            "severity": "critical",
            "issue_type": "empty_workbook",
            "issue_summary": "El archivo AARCO no contiene filas utilizables.",
        })
    return rows, workbook_issues
