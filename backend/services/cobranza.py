from fastapi import APIRouter, HTTPException, Query
from database import SessionLocal, Payment, Policy, Client, PaymentEvidenceRecord
from typing import Optional
from datetime import datetime
from services.cartera import prospector_commission_is_expired

router = APIRouter(prefix="/cobranza", tags=["cobranza"])

def format_date(d):
    if d is None:
        return None
    return d.strftime("%Y-%m-%d")

def format_decimal(value):
    if value is None:
        return None
    return float(value)

def serialize_payment_evidence(evidence: PaymentEvidenceRecord):
    return {
        "id": evidence.id,
        "policy_number": evidence.policy_number,
        "client_name": evidence.client_name,
        "insurer_id": evidence.insurer_id,
        "product_branch": evidence.product_branch,
        "evidence_type": evidence.evidence_type,
        "evidence_date": format_date(evidence.evidence_date),
        "paid_amount": format_decimal(evidence.paid_amount),
        "gross_commission_amount": format_decimal(evidence.gross_commission_amount),
        "net_commission_amount": format_decimal(evidence.net_commission_amount),
        "tax_amount": format_decimal(evidence.tax_amount),
        "receipt_number": evidence.receipt_number,
        "insurer_reference": evidence.insurer_reference,
        "receipt_status": evidence.receipt_status,
        "policy_status_source": evidence.policy_status_source,
        "collection_channel": evidence.collection_channel,
        "commission_type": evidence.commission_type,
        "payment_application_status": evidence.payment_application_status,
        "reconciliation_status": evidence.reconciliation_status,
        "reconciliation_confidence": format_decimal(evidence.reconciliation_confidence),
        "metadata": evidence.metadata_json,
        "ingestion_record_id": evidence.ingestion_record_id,
    }


def apply_payment_evidence_filters(
    query,
    start_date: Optional[str],
    end_date: Optional[str],
    product_branch: Optional[str],
    policy_number: Optional[str],
    reconciliation_status: Optional[str] = None,
):
    if start_date:
        query = query.filter(PaymentEvidenceRecord.evidence_date >= datetime.strptime(start_date, "%Y-%m-%d").date())
    if end_date:
        query = query.filter(PaymentEvidenceRecord.evidence_date <= datetime.strptime(end_date, "%Y-%m-%d").date())
    if product_branch:
        query = query.filter(PaymentEvidenceRecord.product_branch == product_branch.upper())
    if policy_number:
        query = query.filter(PaymentEvidenceRecord.policy_number == str(policy_number).strip())
    if reconciliation_status:
        query = query.filter(PaymentEvidenceRecord.reconciliation_status == reconciliation_status)
    return query


def get_payment_evidence_for_insurer(
    insurer_id: str,
    start_date: Optional[str],
    end_date: Optional[str],
    product_branch: Optional[str],
    policy_number: Optional[str],
    reconciliation_status: Optional[str],
    limit: int,
):
    db = SessionLocal()
    try:
        query = db.query(PaymentEvidenceRecord).filter(PaymentEvidenceRecord.insurer_id == insurer_id)
        query = apply_payment_evidence_filters(
            query,
            start_date=start_date,
            end_date=end_date,
            product_branch=product_branch,
            policy_number=policy_number,
            reconciliation_status=reconciliation_status,
        )

        evidence_rows = query.order_by(PaymentEvidenceRecord.evidence_date.desc()).limit(limit).all()
        return [serialize_payment_evidence(evidence) for evidence in evidence_rows]
    finally:
        db.close()


def get_payment_evidence_summary_for_insurer(
    insurer_id: str,
    start_date: Optional[str],
    end_date: Optional[str],
    product_branch: Optional[str],
):
    db = SessionLocal()
    try:
        query = db.query(PaymentEvidenceRecord).filter(PaymentEvidenceRecord.insurer_id == insurer_id)
        query = apply_payment_evidence_filters(
            query,
            start_date=start_date,
            end_date=end_date,
            product_branch=product_branch,
            policy_number=None,
        )

        summary = {}
        for evidence in query.all():
            key = (
                evidence.product_branch or "UNKNOWN",
                evidence.policy_number or "UNKNOWN",
                format_date(evidence.evidence_date) or "NO_DATE",
                evidence.receipt_status or "UNKNOWN",
            )
            if key not in summary:
                summary[key] = {
                    "product_branch": key[0],
                    "policy_number": key[1],
                    "evidence_date": key[2],
                    "receipt_status": key[3],
                    "evidence_row_count": 0,
                    "paid_amount": 0.0,
                    "gross_commission_amount": 0.0,
                    "net_commission_amount": 0.0,
                    "tax_amount": 0.0,
                    "latest_policy_status_source": evidence.policy_status_source,
                    "reconciliation_statuses": set(),
                }

            item = summary[key]
            item["evidence_row_count"] += 1
            item["paid_amount"] += float(evidence.paid_amount or 0)
            item["gross_commission_amount"] += float(evidence.gross_commission_amount or 0)
            item["net_commission_amount"] += float(evidence.net_commission_amount or 0)
            item["tax_amount"] += float(evidence.tax_amount or 0)
            item["latest_policy_status_source"] = evidence.policy_status_source or item["latest_policy_status_source"]
            item["reconciliation_statuses"].add(evidence.reconciliation_status)

        return [
            {
                **item,
                "reconciliation_statuses": sorted(item["reconciliation_statuses"]),
            }
            for item in summary.values()
        ]
    finally:
        db.close()


@router.get("/metlife/evidence")
async def get_metlife_payment_evidence(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    product_branch: Optional[str] = Query(None, description="VIDA or GMM"),
    policy_number: Optional[str] = Query(None, description="Policy number"),
    reconciliation_status: Optional[str] = Query(None, description="matched, unmatched, ambiguous, failed"),
    limit: int = Query(200, ge=1, le=1000)
):
    return get_payment_evidence_for_insurer(
        "metlife",
        start_date=start_date,
        end_date=end_date,
        product_branch=product_branch,
        policy_number=policy_number,
        reconciliation_status=reconciliation_status,
        limit=limit,
    )


@router.get("/metlife/summary")
async def get_metlife_payment_evidence_summary(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    product_branch: Optional[str] = Query(None, description="VIDA or GMM"),
):
    return get_payment_evidence_summary_for_insurer(
        "metlife",
        start_date=start_date,
        end_date=end_date,
        product_branch=product_branch,
    )


@router.get("/sura/evidence")
async def get_sura_payment_evidence(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    product_branch: Optional[str] = Query(None, description="VIDA or DANOS"),
    policy_number: Optional[str] = Query(None, description="Policy number"),
    reconciliation_status: Optional[str] = Query(None, description="matched, unmatched, ambiguous, failed"),
    limit: int = Query(200, ge=1, le=1000)
):
    return get_payment_evidence_for_insurer(
        "sura",
        start_date=start_date,
        end_date=end_date,
        product_branch=product_branch,
        policy_number=policy_number,
        reconciliation_status=reconciliation_status,
        limit=limit,
    )


@router.get("/sura/summary")
async def get_sura_payment_evidence_summary(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    product_branch: Optional[str] = Query(None, description="VIDA or DANOS"),
):
    return get_payment_evidence_summary_for_insurer(
        "sura",
        start_date=start_date,
        end_date=end_date,
        product_branch=product_branch,
    )


@router.get("/vida")
async def get_cobranza_vida(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    insurer: str = Query("Metlife", description="Insurer name")
):
    db = SessionLocal()
    try:
        results = []
        
        # Build query joining Policy and Client
        query = db.query(Payment).join(Policy).join(Client)
        
        # Apply date filters
        if start_date:
            try:
                sd = datetime.strptime(start_date, "%Y-%m-%d").date()
                query = query.filter(Payment.received_date >= sd)
            except:
                pass
        if end_date:
            try:
                ed = datetime.strptime(end_date, "%Y-%m-%d").date()
                query = query.filter(Payment.received_date <= ed)
            except:
                pass
                
        if insurer.lower() == "metlife":
            # Metlife Vida
            query = query.filter(Policy.insurer_id == "metlife").filter(Policy.product_id == "prod_met_vida")
            payments = query.all()
            for pay in payments:
                pol = pay.policy
                pct = 0.0 if prospector_commission_is_expired(pol) else (float(pol.commission_percentage) if pol.commission_percentage else 0.0)
                com = float(pay.paid_amount) * (pct / 100.0) if pay.paid_amount else 0.0
                
                results.append({
                    "# de Póliza": pol.policy_number,
                    "Producto": pol.product.name if pol.product else "Metlife Vida",
                    "Conducto de Cobro": "Conducto de Cobro",
                    "Fecha de Pago del Recibo": format_date(pay.received_date),
                    "Año de Vida Póliza": 1,
                    "Prima Pagada": float(pay.paid_amount) if pay.paid_amount else 0.0,
                    "Comisión Bruto": com,
                    "Comisión Neta": com
                })
                
        elif insurer.lower() == "sura":
            # SURA Cobranza
            query = query.filter(Policy.insurer_id == "sura")
            payments = query.all()
            for pay in payments:
                pol = pay.policy
                pct = 0.0 if prospector_commission_is_expired(pol) else (float(pol.commission_percentage) if pol.commission_percentage else 0.0)
                com = float(pay.paid_amount) * pct if pay.paid_amount else 0.0 # Sura percentage is often absolute decimal
                
                results.append({
                    "Daños/Vida": "Vida",
                    "Grupo": "",
                    "Oficina": "Oficina SURA",
                    "Ramo": pol.product.branch if pol.product else "GMM",
                    "Póliza": pol.policy_number,
                    "Contratante": pol.client.full_name if pol.client else "CONTRATANTE",
                    "Clave Agente": "Agente",
                    "Tipo de Cambio": "MXN",
                    "# Recibo": "",
                    "Serie de Recibo": "",
                    "Prima Total": float(pay.expected_amount) if pay.expected_amount else 0.0,
                    "Prima Neta": float(pay.paid_amount) if pay.paid_amount else 0.0,
                    "% Comisión pagado": pct,
                    "Comisión de derecho": "Derecho",
                    "Monto Comisión Neta": com,
                    "Total Comisión pagado": com,
                    "# Liquidación": "",
                    "# Comprobante": "",
                    "Fecha aplicación de la póliza": format_date(pay.received_date)
                })
                
        elif insurer.upper() in ["AARCO_AXA", "AARCO"]:
            # Aarco base cobranza
            query = query.filter(Policy.insurer_id == "aarco")
            payments = query.all()
            for pay in payments:
                pol = pay.policy
                pct = 0.0 if prospector_commission_is_expired(pol) else (float(pol.commission_percentage) if pol.commission_percentage else 0.0)
                com = float(pay.paid_amount) * (pct / 100.0) if pay.paid_amount else 0.0
                prospectador = pol.client.metadata_json.get("prospectador", "") if pol.client else ""
                
                results.append({
                    "CIA": "AARCO",
                    "NUM_POL": pol.policy_number,
                    "CLIENTE": pol.client.full_name if pol.client else "CLIENTE",
                    "PROSPECTADOR": prospectador,
                    "F_COBRO": format_date(pay.received_date),
                    "PRIMA_NETA_MN": float(pay.paid_amount) if pay.paid_amount else 0.0,
                    "COM_APL_MN": com,
                    "% COMISION PROSPECTADOR": pct,
                    "$ COMISION PROSPECTADOR": com
                })
                
        return results

    except Exception as e:
        print(f"Error loading Cobranza: {e}")
        return []
    finally:
        db.close()

@router.get("/gmm")
async def get_cobranza_gmm(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    insurer: str = Query("Metlife", description="Insurer name")
):
    db = SessionLocal()
    try:
        results = []
        
        query = db.query(Payment).join(Policy).join(Client)
        
        if start_date:
            try:
                sd = datetime.strptime(start_date, "%Y-%m-%d").date()
                query = query.filter(Payment.received_date >= sd)
            except:
                pass
        if end_date:
            try:
                ed = datetime.strptime(end_date, "%Y-%m-%d").date()
                query = query.filter(Payment.received_date <= ed)
            except:
                pass
                
        if insurer.lower() == "metlife":
            query = query.filter(Policy.insurer_id == "metlife").filter(Policy.product_id == "prod_met_gmm")
            payments = query.all()
            for pay in payments:
                pol = pay.policy
                pct = 0.0 if prospector_commission_is_expired(pol) else (float(pol.commission_percentage) if pol.commission_percentage else 0.0)
                com = float(pay.paid_amount) * (pct / 100.0) if pay.paid_amount else 0.0
                
                results.append({
                    "# de Póliza": pol.policy_number,
                    "Producto": pol.product.name if pol.product else "Metlife GMM",
                    "Conducto de Cobro": "Conducto de Cobro",
                    "Fecha de Pago del Recibo": format_date(pay.received_date),
                    "Año de Vida Póliza": 1,
                    "Estado": pay.status.upper(),
                    "Prima Pagada": float(pay.paid_amount) if pay.paid_amount else 0.0,
                    "Comisión Bruto": com,
                    "Comisión Neta": com,
                    "IVA Causado": float(pay.paid_amount) * 0.16 if pay.paid_amount else 0.0
                })
                
        elif insurer.lower() == "sura":
            # SURA GMM
            query = query.filter(Policy.insurer_id == "sura")
            payments = query.all()
            for pay in payments:
                pol = pay.policy
                pct = 0.0 if prospector_commission_is_expired(pol) else (float(pol.commission_percentage) if pol.commission_percentage else 0.0)
                com = float(pay.paid_amount) * pct if pay.paid_amount else 0.0
                
                results.append({
                    "Daños/Vida": "Vida",
                    "Grupo": "",
                    "Oficina": "Oficina SURA",
                    "Ramo": pol.product.branch if pol.product else "GMM",
                    "Póliza": pol.policy_number,
                    "Contratante": pol.client.full_name if pol.client else "CONTRATANTE",
                    "Clave Agente": "Agente",
                    "Tipo de Cambio": "MXN",
                    "# Recibo": "",
                    "Serie de Recibo": "",
                    "Prima Total": float(pay.expected_amount) if pay.expected_amount else 0.0,
                    "Prima Neta": float(pay.paid_amount) if pay.paid_amount else 0.0,
                    "% Comisión pagado": pct,
                    "Comisión de derecho": "Derecho",
                    "Monto Comisión Neta": com,
                    "Total Comisión pagado": com,
                    "# Liquidación": "",
                    "# Comprobante": "",
                    "Fecha aplicación de la póliza": format_date(pay.received_date)
                })
                
        return results

    except Exception as e:
        print(f"Error loading Cobranza GMM: {e}")
        return []
    finally:
        db.close()
