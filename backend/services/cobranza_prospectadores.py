from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from starlette.concurrency import run_in_threadpool

from database import (
    Policy,
    PolicyProspectorAssignment,
    Prospector,
    ProspectorCommissionAllocation,
    ProspectorCommissionBatch,
    ProspectorCommissionLine,
    ProspectorCommissionPeriod,
    ProspectorOpeningBalance,
    SessionLocal,
)
from parsers.aarco_prospector_commissions import parse_aarco_prospector_workbook
from parsers.metlife_cobranza import parse_metlife_cobranza_workbook
from parsers.sura_cobranza import parse_sura_cobranza_workbook
from services.auth import AccessProfile
from services.authorization import require_module_access


router = APIRouter(prefix="/cobranza-prospectadores", tags=["cobranza-prospectadores"])
CENT = Decimal("0.01")
SUPPORTED_SOURCES = {"metlife", "sura", "aarco"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
PREVIEW_TTL_HOURS = 24


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_allocation(
    source_commission: Decimal,
    commission_rate: Decimal,
    *,
    branch: str,
    utility_coefficient: Decimal = Decimal("0.91"),
    vat_rate: Decimal = Decimal("0.16"),
) -> dict[str, Decimal]:
    life_divisor = Decimal("1.16") if str(branch).strip().upper() == "VIDA" else Decimal("1")
    commission_base = source_commission / life_divisor
    commission_amount = money(commission_base * commission_rate * utility_coefficient)
    vat_amount = money(commission_amount * vat_rate)
    return {
        "source_commission": money(source_commission),
        "life_divisor": life_divisor,
        "commission_base": money(commission_base),
        "commission_amount": commission_amount,
        "vat_amount": vat_amount,
        "total_amount": money(commission_amount + vat_amount),
    }


def import_staging_root() -> Path:
    configured = os.getenv("PROSPECTOR_IMPORT_STAGING_DIR", "").strip()
    root = Path(configured).expanduser() if configured else Path(__file__).resolve().parents[2] / ".runtime" / "prospector-imports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def cleanup_expired_previews() -> None:
    cutoff = datetime.now(timezone.utc).timestamp() - (PREVIEW_TTL_HOURS * 3600)
    for path in import_staging_root().glob("*.json"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            continue


def normalize_policy_key(value: object) -> str:
    text = re.sub(r"[^A-Z0-9]", "", str(value or "").strip().upper())
    return (text.lstrip("0") or "0") if text.isdigit() else text


def normalize_policy_exact(value: object) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value or "").strip().upper())


def _json_value(value: object):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


def _source_key(source: str, branch: str, insurer: str, policy: str, receipt: str, movement_date: str) -> str:
    raw = "|".join((source, branch, insurer, policy, receipt, movement_date))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def consolidate_parsed_rows(source: str, parsed_rows: list) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    for parsed in parsed_rows:
        normalized = parsed.normalized_payload
        policy_number = str(normalized.get("policy_number") or "").strip()
        movement = normalized.get("payment_date")
        movement_text = movement.isoformat() if isinstance(movement, date) else str(movement or "")[:10]
        receipt = str(normalized.get("receipt_number") or "").strip()
        series = str(normalized.get("receipt_series") or "").strip()
        insurer = str(normalized.get("insurer_id") or source).strip().casefold()
        raw_branch = str(normalized.get("product_branch") or "").strip().upper()
        branch = raw_branch if raw_branch in {"VIDA", "GMM", "DANOS"} else ("DANOS" if source != "metlife" else raw_branch)
        if source == "metlife":
            amount = normalized.get("net_commission_amount")
            group_key = (branch, insurer, policy_number, movement_text)
        elif source == "sura":
            amount = normalized.get("net_commission_amount")
            group_key = (branch, insurer, policy_number, receipt, series, movement_text)
        else:
            amount = normalized.get("source_commission_amount")
            group_key = (branch, insurer, policy_number, movement_text)

        entry = grouped.setdefault(group_key, {
            "policy_number": policy_number,
            "receipt_number": "-".join(part for part in (receipt, series) if part),
            "insurer_id": insurer,
            "branch": branch or "DANOS",
            "movement_date": movement_text,
            "source_commission": "0",
            "currency": str(normalized.get("currency") or "MXN").strip().upper(),
            "row_count": 0,
            "row_hashes": [],
            "issues": [],
            "matching_hints": {
                "office_code": str(normalized.get("office_code") or "").strip(),
                "branch_code": str(normalized.get("branch_code") or "").strip(),
            },
        })
        entry["row_count"] += 1
        entry["row_hashes"].append(parsed.row_hash)
        entry["issues"].extend(parsed.issues)
        if amount is None:
            entry["issues"].append({
                "severity": "high",
                "issue_type": "missing_commission",
                "issue_summary": f"No se pudo leer la comisión de la póliza {policy_number or 'sin número'}.",
            })
        else:
            entry["source_commission"] = str(Decimal(entry["source_commission"]) + Decimal(str(amount)))

    result = []
    for entry in grouped.values():
        entry["source_commission"] = str(Decimal(entry["source_commission"]).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
        entry["source_key"] = _source_key(
            source, entry["branch"], entry["insurer_id"], entry["policy_number"],
            entry["receipt_number"], entry["movement_date"],
        )
        result.append(entry)
    return sorted(result, key=lambda item: (item["movement_date"], item["policy_number"], item["receipt_number"]))


def parse_import_file(source: str, path: Path) -> tuple[list[dict], list[dict], int]:
    if source == "metlife":
        parsed, workbook_issues = parse_metlife_cobranza_workbook(path)
    elif source == "sura":
        parsed, workbook_issues = parse_sura_cobranza_workbook(path)
    elif source == "aarco":
        parsed, workbook_issues = parse_aarco_prospector_workbook(path)
    else:
        raise ValueError("Fuente no soportada")
    return consolidate_parsed_rows(source, parsed), workbook_issues, len(parsed)


def _policy_aliases(policy: Policy) -> set[str]:
    number = str(policy.policy_number or "").strip()
    aliases = {normalize_policy_key(number)}
    parts = [part for part in re.split(r"[-/ ]+", number) if part]
    if len(parts) > 1:
        aliases.add(normalize_policy_key(parts[-1]))
    return {alias for alias in aliases if alias}


def _incoming_policy_aliases(line: dict) -> list[str]:
    policy = str(line.get("policy_number") or "").strip()
    hints = line.get("matching_hints") or {}
    office = str(hints.get("office_code") or "").strip()
    branch = str(hints.get("branch_code") or "").strip()
    candidates = [policy]
    if office and branch and policy:
        candidates.insert(0, f"{office}-{branch}-{policy}")
    if branch and policy:
        candidates.insert(1, f"{branch}-{policy}")
    return list(dict.fromkeys(normalize_policy_key(candidate) for candidate in candidates if candidate))


def _matching_assignments(
    db, policy_id: str, movement_date: date,
) -> tuple[list[PolicyProspectorAssignment], bool]:
    query = db.query(PolicyProspectorAssignment).filter(
        PolicyProspectorAssignment.policy_id == policy_id,
        PolicyProspectorAssignment.effective_from <= movement_date,
    )
    current = query.filter(or_(
        PolicyProspectorAssignment.effective_to.is_(None),
        PolicyProspectorAssignment.effective_to > movement_date,
    ), PolicyProspectorAssignment.is_active.is_(True)).all()
    if current:
        return current, False
    historical = query.order_by(PolicyProspectorAssignment.effective_from.desc()).all()
    if not historical:
        return [], False
    latest_start = historical[0].effective_from
    return [row for row in historical if row.effective_from == latest_start], True


def analyze_import_lines(db, lines: list[dict], period: ProspectorCommissionPeriod) -> list[dict]:
    policies = db.query(Policy).all()
    alias_map: dict[str, list[Policy]] = defaultdict(list)
    exact_map: dict[str, list[Policy]] = defaultdict(list)
    for policy in policies:
        exact_map[normalize_policy_exact(policy.policy_number)].append(policy)
        for alias in _policy_aliases(policy):
            alias_map[alias].append(policy)

    analyzed = []
    for source_line in lines:
        line = dict(source_line)
        reasons = [issue.get("issue_summary", "Error de formato") for issue in line.get("issues", []) if issue.get("severity") in {"critical", "high"}]
        movement_date = None
        try:
            movement_date = date.fromisoformat(str(line.get("movement_date") or ""))
        except ValueError:
            reasons.append("No se pudo determinar la fecha del movimiento")
        amount = Decimal(str(line.get("source_commission") or "0"))
        if str(line.get("currency") or "MXN").upper() != period.currency:
            reasons.append("La moneda requiere registrar un tipo de cambio")

        exact_candidates = exact_map.get(normalize_policy_exact(line.get("policy_number")), [])
        matches: list[Policy] = exact_candidates if len(exact_candidates) == 1 else []
        if not matches:
            for alias in _incoming_policy_aliases(line):
                candidates = alias_map.get(alias, [])
                if len(candidates) == 1:
                    matches = candidates
                    break
                if len(candidates) > 1:
                    matches = candidates
        if not matches:
            reasons.append("No se encontró la póliza en Cartera de Prospectadores")
        elif len(matches) > 1:
            reasons.append("La póliza coincide con más de un registro de cartera")

        allocations = []
        policy = matches[0] if len(matches) == 1 else None
        if policy and movement_date:
            assignments, expired_assignment = _matching_assignments(db, policy.id, movement_date)
            if not assignments:
                reasons.append("La póliza no tiene un prospectador asignado")
            effective_rates = [
                Decimal("0") if expired_assignment and amount >= 0 else Decimal(str(row.commission_rate))
                for row in assignments
            ]
            total_rate = sum(effective_rates, Decimal("0"))
            if total_rate > 1:
                reasons.append("Los porcentajes asignados exceden 100%")
            if not reasons:
                for assignment, effective_rate in zip(assignments, effective_rates):
                    prospectador = db.get(Prospector, assignment.prospector_id)
                    calculation = calculate_allocation(
                        amount, effective_rate,
                        branch=str(line.get("branch") or ""),
                        utility_coefficient=Decimal(str(period.utility_coefficient)),
                        vat_rate=Decimal(str(period.vat_rate)),
                    )
                    allocations.append({
                        "prospector_id": assignment.prospector_id,
                        "prospector_name": prospectador.name if prospectador else "Prospectador",
                        "assignment_id": assignment.id,
                        "commission_rate": str(effective_rate),
                        "expired_zero": expired_assignment and amount >= 0,
                        "calculation": _json_value(calculation),
                    })

        line["policy_id"] = policy.id if policy else None
        line["status"] = "listo" if not reasons else "pendiente_asignacion"
        line["exception_reason"] = " | ".join(dict.fromkeys(reasons)) or None
        line["allocations"] = allocations
        analyzed.append(line)
    return analyzed


def _preview_summary(lines: list[dict], raw_rows: int, workbook_issues: list[dict]) -> dict:
    ready = [line for line in lines if line["status"] == "listo"]
    exceptions = [line for line in lines if line["status"] != "listo"]
    return {
        "raw_rows": raw_rows,
        "consolidated_rows": len(lines),
        "ready_rows": len(ready),
        "exception_rows": len(exceptions),
        "source_commission": float(sum((Decimal(line["source_commission"]) for line in lines), Decimal("0"))),
        "prospector_total": float(sum((Decimal(allocation["calculation"]["total_amount"]) for line in ready for allocation in line["allocations"]), Decimal("0"))),
        "workbook_issues": workbook_issues,
    }


async def _save_upload(upload: UploadFile, destination: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with destination.open("wb") as output:
        while chunk := await upload.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail="El archivo excede el límite de 50 MB")
            digest.update(chunk)
            output.write(chunk)
    return size, digest.hexdigest()


def _load_preview(token: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{32}", token):
        raise HTTPException(status_code=404, detail="Vista previa no encontrada")
    path = import_staging_root() / f"{token}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Vista previa no encontrada")
    payload = json.loads(path.read_text(encoding="utf-8"))
    created = datetime.fromisoformat(payload["created_at"])
    if datetime.now(timezone.utc) - created > timedelta(hours=PREVIEW_TTL_HOURS):
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=410, detail="La vista previa caducó; vuelve a cargar el archivo")
    return payload


class PeriodPayload(BaseModel):
    month: date
    currency: str = Field(default="MXN", min_length=3, max_length=3)


class OpeningBalancePayload(BaseModel):
    prospector_id: str
    amount: Decimal
    notes: str | None = Field(default=None, max_length=1000)


class CalculationPreview(BaseModel):
    source_commission: Decimal
    commission_percentage: Decimal = Field(ge=0, le=100)
    branch: str = ""


def _serialize_period(row: ProspectorCommissionPeriod, balances: Decimal = Decimal("0"), batches: int = 0, exceptions: int = 0) -> dict:
    return {
        "id": row.id,
        "month": row.month.isoformat(),
        "status": row.status,
        "currency": row.currency,
        "utility_coefficient": float(row.utility_coefficient),
        "vat_rate": float(row.vat_rate),
        "opening_balance": float(balances or 0),
        "batch_count": int(batches or 0),
        "exception_count": int(exceptions or 0),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("")
def commission_workspace():
    db = SessionLocal()
    try:
        periods = db.query(ProspectorCommissionPeriod).order_by(ProspectorCommissionPeriod.month.desc()).all()
        serialized = []
        for period in periods:
            balances = db.query(func.coalesce(func.sum(ProspectorOpeningBalance.amount), 0)).filter(
                ProspectorOpeningBalance.period_id == period.id
            ).scalar()
            batch_count = db.query(ProspectorCommissionBatch).filter(ProspectorCommissionBatch.period_id == period.id).count()
            exceptions = (
                db.query(ProspectorCommissionLine)
                .join(ProspectorCommissionBatch, ProspectorCommissionBatch.id == ProspectorCommissionLine.batch_id)
                .filter(
                    ProspectorCommissionBatch.period_id == period.id,
                    ProspectorCommissionLine.status == "pendiente_asignacion",
                ).count()
            )
            serialized.append(_serialize_period(period, balances, batch_count, exceptions))
        return {
            "periods": serialized,
            "summary": {
                "periods": len(periods),
                "prospectors": db.query(Prospector).filter(Prospector.is_active.is_(True)).count(),
                "pending_exceptions": db.query(ProspectorCommissionLine).filter(
                    ProspectorCommissionLine.status == "pendiente_asignacion"
                ).count(),
                "fixed_coefficient": 0.91,
            },
        }
    finally:
        db.close()


@router.get("/periods/{period_id}")
def period_detail(period_id: str):
    db = SessionLocal()
    try:
        period = db.get(ProspectorCommissionPeriod, period_id)
        if not period:
            raise HTTPException(status_code=404, detail="Periodo no encontrado")
        batches = db.query(ProspectorCommissionBatch).filter(
            ProspectorCommissionBatch.period_id == period.id
        ).order_by(ProspectorCommissionBatch.created_at.desc()).all()
        batch_ids = [row.id for row in batches]
        exceptions = []
        exception_count = 0
        if batch_ids:
            exception_count = db.query(ProspectorCommissionLine).filter(
                ProspectorCommissionLine.batch_id.in_(batch_ids),
                ProspectorCommissionLine.status != "listo",
            ).count()
            rows = db.query(ProspectorCommissionLine).filter(
                ProspectorCommissionLine.batch_id.in_(batch_ids),
                ProspectorCommissionLine.status != "listo",
            ).order_by(ProspectorCommissionLine.created_at.desc()).limit(500).all()
            exceptions = [{
                "id": row.id,
                "batch_id": row.batch_id,
                "policy_number": row.policy_number,
                "receipt_number": row.receipt_number or "",
                "insurer_id": row.insurer_id,
                "branch": row.branch or "",
                "movement_date": row.movement_date.isoformat() if row.movement_date else None,
                "source_commission": float(row.source_commission),
                "currency": row.currency,
                "reason": row.exception_reason or "Pendiente de revisión",
            } for row in rows]
        return {
            "period": _serialize_period(
                period,
                db.query(func.coalesce(func.sum(ProspectorOpeningBalance.amount), 0)).filter(
                    ProspectorOpeningBalance.period_id == period.id
                ).scalar(),
                len(batches),
                exception_count,
            ),
            "batches": [{
                "id": row.id,
                "source": row.source,
                "filename": row.filename,
                "status": row.status,
                "raw_rows": row.raw_row_count,
                "consolidated_rows": row.consolidated_row_count,
                "exceptions": row.exception_count,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            } for row in batches],
            "exceptions": exceptions,
        }
    finally:
        db.close()


@router.post("/imports/preview")
async def preview_import(
    period_id: str = Form(...),
    source: str = Form(...),
    file: UploadFile = File(...),
    profile: AccessProfile = Depends(require_module_access("cobranza_prospectadores", operation=True)),
):
    del profile
    cleanup_expired_previews()
    normalized_source = source.strip().casefold()
    if normalized_source not in SUPPORTED_SOURCES:
        raise HTTPException(status_code=400, detail="La fuente debe ser MetLife, SURA o AARCO")
    filename = Path(file.filename or "estado.xlsx").name
    if Path(filename).suffix.casefold() not in {".xlsx", ".xls"}:
        raise HTTPException(status_code=400, detail="Selecciona un archivo Excel .xlsx o .xls")

    db = SessionLocal()
    temp_path: Path | None = None
    try:
        period = db.get(ProspectorCommissionPeriod, period_id)
        if not period:
            raise HTTPException(status_code=404, detail="Periodo no encontrado")
        if period.status != "borrador":
            raise HTTPException(status_code=409, detail="Solo se pueden cargar archivos en un periodo en borrador")
        with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False, dir=import_staging_root()) as temporary:
            temp_path = Path(temporary.name)
        _, file_hash = await _save_upload(file, temp_path)
        duplicate = db.query(ProspectorCommissionBatch).filter(
            ProspectorCommissionBatch.period_id == period.id,
            ProspectorCommissionBatch.source == normalized_source,
            ProspectorCommissionBatch.file_hash == file_hash,
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Este mismo archivo ya fue aplicado al periodo")

        try:
            lines, workbook_issues, raw_rows = await run_in_threadpool(
                parse_import_file, normalized_source, temp_path
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"No se pudo leer el archivo {filename}: {exc}",
            ) from exc
        if any(issue.get("severity") == "critical" for issue in workbook_issues):
            raise HTTPException(status_code=422, detail={"message": "El formato del archivo no es compatible", "issues": workbook_issues})
        analyzed = analyze_import_lines(db, lines, period)
        summary = _preview_summary(analyzed, raw_rows, workbook_issues)
        token = uuid.uuid4().hex
        staged = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "period_id": period.id,
            "source": normalized_source,
            "filename": filename,
            "file_hash": file_hash,
            "raw_rows": raw_rows,
            "workbook_issues": workbook_issues,
            "lines": _json_value(lines),
        }
        (import_staging_root() / f"{token}.json").write_text(
            json.dumps(staged, ensure_ascii=False), encoding="utf-8"
        )
        return {
            "token": token,
            "source": normalized_source,
            "filename": filename,
            "summary": summary,
            "sample": analyzed[:30],
        }
    finally:
        db.close()
        if temp_path:
            temp_path.unlink(missing_ok=True)


@router.post("/imports/{token}/apply", status_code=201)
def apply_import(
    token: str,
    profile: AccessProfile = Depends(require_module_access("cobranza_prospectadores", operation=True)),
):
    staged = _load_preview(token)
    db = SessionLocal()
    try:
        period = db.get(ProspectorCommissionPeriod, staged["period_id"])
        if not period:
            raise HTTPException(status_code=404, detail="Periodo no encontrado")
        if period.status != "borrador":
            raise HTTPException(status_code=409, detail="El periodo ya no admite cargas")
        if db.query(ProspectorCommissionBatch).filter(
            ProspectorCommissionBatch.period_id == period.id,
            ProspectorCommissionBatch.source == staged["source"],
            ProspectorCommissionBatch.file_hash == staged["file_hash"],
        ).first():
            raise HTTPException(status_code=409, detail="Este mismo archivo ya fue aplicado al periodo")

        analyzed = analyze_import_lines(db, staged["lines"], period)
        exception_count = sum(1 for line in analyzed if line["status"] != "listo")
        batch = ProspectorCommissionBatch(
            period_id=period.id,
            source=staged["source"],
            filename=staged["filename"],
            file_hash=staged["file_hash"],
            currency=period.currency,
            status="con_excepciones" if exception_count else "procesado",
            raw_row_count=staged["raw_rows"],
            consolidated_row_count=len(analyzed),
            exception_count=exception_count,
            created_by=profile.username,
        )
        db.add(batch)
        db.flush()
        allocation_count = 0
        for item in analyzed:
            movement_date = None
            try:
                movement_date = date.fromisoformat(str(item.get("movement_date") or ""))
            except ValueError:
                pass
            line = ProspectorCommissionLine(
                batch_id=batch.id,
                source_key=item["source_key"],
                policy_id=item.get("policy_id"),
                policy_number=item.get("policy_number") or "SIN-POLIZA",
                receipt_number=item.get("receipt_number") or None,
                insurer_id=item.get("insurer_id") or staged["source"],
                branch=item.get("branch") or None,
                movement_date=movement_date,
                source_commission=Decimal(str(item.get("source_commission") or "0")),
                currency=item.get("currency") or period.currency,
                status=item["status"],
                exception_reason=item.get("exception_reason"),
                raw_payload={
                    "row_count": item.get("row_count", 0),
                    "row_hashes": item.get("row_hashes", []),
                    "issues": item.get("issues", []),
                    "matching_hints": item.get("matching_hints", {}),
                },
            )
            db.add(line)
            db.flush()
            for allocation in item.get("allocations", []):
                calculation = allocation["calculation"]
                db.add(ProspectorCommissionAllocation(
                    line_id=line.id,
                    prospector_id=allocation["prospector_id"],
                    assignment_id=allocation["assignment_id"],
                    commission_rate=Decimal(allocation["commission_rate"]),
                    utility_coefficient=Decimal(str(period.utility_coefficient)),
                    vat_rate=Decimal(str(period.vat_rate)),
                    life_divisor=Decimal(calculation["life_divisor"]),
                    commission_amount=Decimal(calculation["commission_amount"]),
                    vat_amount=Decimal(calculation["vat_amount"]),
                    total_amount=Decimal(calculation["total_amount"]),
                    calculation_json=calculation,
                ))
                allocation_count += 1
        db.commit()
        (import_staging_root() / f"{token}.json").unlink(missing_ok=True)
        return {
            "batch_id": batch.id,
            "status": batch.status,
            "consolidated_rows": batch.consolidated_row_count,
            "exception_count": batch.exception_count,
            "allocation_count": allocation_count,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/periods", status_code=201)
def create_period(payload: PeriodPayload, profile: AccessProfile = Depends(require_module_access("cobranza_prospectadores", operation=True))):
    if payload.month.day != 1:
        raise HTTPException(status_code=400, detail="El periodo debe usar el primer día del mes")
    currency = payload.currency.strip().upper()
    if currency != "MXN":
        raise HTTPException(status_code=409, detail="La moneda requiere registrar un tipo de cambio antes de continuar")
    db = SessionLocal()
    try:
        if db.query(ProspectorCommissionPeriod).filter(ProspectorCommissionPeriod.month == payload.month).first():
            raise HTTPException(status_code=409, detail="El periodo ya existe")
        row = ProspectorCommissionPeriod(
            month=payload.month, status="borrador", currency=currency,
            utility_coefficient=Decimal("0.91"), vat_rate=Decimal("0.16"),
            created_by=profile.username,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"period": _serialize_period(row)}
    finally:
        db.close()


@router.put("/periods/{period_id}/opening-balance")
def upsert_opening_balance(period_id: str, payload: OpeningBalancePayload, profile: AccessProfile = Depends(require_module_access("cobranza_prospectadores", operation=True))):
    db = SessionLocal()
    try:
        period = db.get(ProspectorCommissionPeriod, period_id)
        prospector = db.get(Prospector, payload.prospector_id)
        if not period or not prospector:
            raise HTTPException(status_code=404, detail="Periodo o prospectador no encontrado")
        if period.status != "borrador":
            raise HTTPException(status_code=409, detail="El saldo inicial solo puede modificarse en un periodo en borrador")
        row = db.query(ProspectorOpeningBalance).filter(
            ProspectorOpeningBalance.period_id == period.id,
            ProspectorOpeningBalance.prospector_id == prospector.id,
        ).first()
        if row:
            row.amount = money(payload.amount)
            row.notes = payload.notes
        else:
            row = ProspectorOpeningBalance(
                period_id=period.id, prospector_id=prospector.id,
                amount=money(payload.amount), notes=payload.notes, created_by=profile.username,
            )
            db.add(row)
        db.commit()
        return {"opening_balance": {"id": row.id, "amount": float(row.amount)}}
    finally:
        db.close()


@router.post("/calculation-preview")
def preview_calculation(payload: CalculationPreview):
    result = calculate_allocation(
        payload.source_commission,
        payload.commission_percentage / Decimal("100"),
        branch=payload.branch,
    )
    return {key: float(value) for key, value in result.items()}
