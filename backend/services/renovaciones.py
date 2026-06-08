from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Union
from datetime import datetime, timedelta
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from database import SessionLocal, Renewal, Policy, Client, Product, User

router = APIRouter(prefix="/renovaciones", tags=["renovaciones"])

def format_date(d):
    if d is None:
        return None
    return d.strftime("%Y-%m-%d")

def normalize_name(value: str) -> str:
    if not value:
        return ""
    return " ".join(str(value).strip().upper().split())

def send_email_smtp(subject: str, body: str, recipients: List[str], attachments: List[dict] = []):
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("SMTP_SENDER", user)
    use_starttls = os.environ.get("SMTP_USE_STARTTLS", "true").lower() in {"1", "true", "yes"}

    if not all([host, user, password, sender]):
        raise RuntimeError("Missing SMTP configuration")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    for att in attachments:
        name = att.get("name")
        content = att.get("content")
        if name and content:
            message.add_attachment(
                content,
                maintype="application",
                subtype="octet-stream",
                filename=name,
            )

    with smtplib.SMTP(host, port) as server:
        if use_starttls:
            server.starttls()
        server.login(user, password)
        server.send_message(message)

@router.get("/upcoming")
async def get_upcoming_renewals(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    days: Optional[int] = Query(30, description="Days to look ahead"),
    insurer: str = Query("Metlife", description="Insurer name"),
    type: str = Query("ALL", description="Policy type: ALL, VIDA, GMM")
):
    db = SessionLocal()
    try:
        results = []
        
        # Build base date range
        today = datetime.now().date()
        if start_date and end_date:
            try:
                sd = datetime.strptime(start_date, "%Y-%m-%d").date()
                ed = datetime.strptime(end_date, "%Y-%m-%d").date()
            except:
                sd = today
                ed = today + timedelta(days=days or 30)
        else:
            sd = today
            ed = today + timedelta(days=days or 30)
            
        # Base query joining Policy, Client, and Product
        query = db.query(Renewal).join(Policy, Renewal.original_policy_id == Policy.id).join(Client).join(Product)
        
        # Filter by date range
        query = query.filter(Renewal.renewal_deadline >= sd).filter(Renewal.renewal_deadline <= ed)
        
        # Filter by Insurer
        if insurer.lower() == "metlife":
            query = query.filter(Policy.insurer_id == "metlife")
            if type.upper() == "VIDA":
                query = query.filter(Policy.product_id == "prod_met_vida")
            elif type.upper() == "GMM":
                query = query.filter(Policy.product_id == "prod_met_gmm")
                
            renewals = query.all()
            
            for ren in renewals:
                pol = ren.original_policy
                if pol.product_id == "prod_met_vida":
                    results.append({
                        "POLIZA_ACTUAL": pol.policy_number,
                        "CONTRATANTE": pol.client.full_name if pol.client else "",
                        "INI_VIG": format_date(pol.effective_start_date),
                        "FIN_VIG": format_date(ren.renewal_deadline),
                        "FORMA_PAGO": pol.payment_frequency.upper(),
                        "CONDUCTO_COBRO": "Conducto de Cobro",
                        "AGENTE": "Pamela Asmara",
                        "PRIMA_ANUAL": float(pol.premium_amount) if pol.premium_amount else 0.0,
                        "PRIMA_MODAL": float(pol.premium_amount / 12) if pol.premium_amount else 0.0,
                        "PAGADO_HASTA": format_date(pol.effective_end_date),
                        "ESTATUS_DE_RENOVACION": ren.insurer_response,
                        "EXPEDIENTE": pol.document_link,
                        "Email": pol.client.email if pol.client else None
                    })
                else:
                    results.append({
                        "NPOLIZA": pol.policy_number,
                        "POLORIG": pol.policy_number,
                        "CONTRATANTE": pol.client.full_name if pol.client else "",
                        "FFINVIG": format_date(ren.renewal_deadline),
                        "PRIMA.1": float(pol.premium_amount) if pol.premium_amount else 0.0,
                        "IVA": float(pol.premium_amount) * 0.16 if pol.premium_amount else 0.0,
                        "NOMBREL": pol.client.full_name if pol.client else "",
                        "DEDUCIBLE": 0.0,
                        "PAGADOHASTA": format_date(pol.effective_end_date),
                        "COASEGURO": 0.0,
                        "ESTATUS_DE_RENOVACION": ren.insurer_response,
                        "EXPEDIENTE": pol.document_link,
                        "Email": pol.client.email if pol.client else None
                    })
                    
        elif insurer.lower() == "sura" or insurer == "Promotoria SURA":
            query = query.filter(Policy.insurer_id == "sura")
            renewals = query.all()
            
            for ren in renewals:
                pol = ren.original_policy
                prospectador = pol.client.metadata_json.get("prospectador", "") if pol.client else ""
                
                if insurer == "Promotoria SURA":
                    results.append({
                        "PÓLIZA": pol.policy_number,
                        "OFICINA": "SURA",
                        "RAMO": pol.product.branch if pol.product else "GMM",
                        "INICIO VIGENCIA": format_date(pol.effective_start_date),
                        "FIN VIGENCIA": format_date(ren.renewal_deadline),
                        "CONTRATANTE": pol.client.full_name if pol.client else "",
                        "PRIMA ANUALIZADA": float(pol.premium_amount) if pol.premium_amount else 0.0,
                        "AGENTE": "SURA Agent",
                        "NOMBRE RAMO": pol.product.name if pol.product else "GMM Product",
                        "PROCEDENCIA": "Promotoría",
                        "Poliza anterior": pol.policy_number,
                        "Llave Póliza": pol.policy_number,
                        "ESTATUS_DE_RENOVACION": ren.insurer_response,
                        "EXPEDIENTE": pol.document_link,
                        "Email": pol.client.email if pol.client else None,
                        "PROMOTOR": "SURA Promotor"
                    })
                else:
                    results.append({
                        "POLIZA": pol.policy_number,
                        "NOMBRE": pol.client.full_name if pol.client else "",
                        "INICIO VIGENCIA": format_date(pol.effective_start_date),
                        "FIN VIGENCIA": format_date(ren.renewal_deadline),
                        "RAMO": pol.product.branch if pol.product else "GMM",
                        "PRIMA": float(pol.premium_amount) if pol.premium_amount else 0.0,
                        "PERIODICIDAD_PAGO": pol.payment_frequency,
                        "PROSPECTADOR": prospectador,
                        "ESTATUS_DE_RENOVACION": ren.insurer_response,
                        "EXPEDIENTE": pol.document_link,
                        "Email": pol.client.email if pol.client else None
                    })
                    
        elif insurer.upper() in ["AARCO_AXA", "AARCO"]:
            query = query.filter(Policy.insurer_id == "aarco")
            renewals = query.all()
            
            for ren in renewals:
                pol = ren.original_policy
                prospectador = pol.client.metadata_json.get("prospectador", "") if pol.client else ""
                results.append({
                    "POLIZA": pol.policy_number,
                    "ASEGURADORA": "AARCO",
                    "PROMOTORIA": "AARCO Promotoria",
                    "AGENTE": "Aarco Agente",
                    "PROSPECTADOR": prospectador,
                    "RAMO": pol.product.branch if pol.product else "VIDA",
                    "PRODUCTO": pol.product.name if pol.product else "Vida Individual",
                    "CONTRATANTE": pol.client.full_name if pol.client else "",
                    "ASEGURADO": pol.client.full_name if pol.client else "",
                    "INICIO VIGENCIA": format_date(pol.effective_start_date),
                    "FIN VIGENCIA": format_date(ren.renewal_deadline),
                    "PRIMA NETA ANUAL": float(pol.premium_amount) if pol.premium_amount else 0.0,
                    "ESTATUS_DE_RENOVACION": ren.insurer_response,
                    "EXPEDIENTE": pol.document_link,
                    "Email": pol.client.email if pol.client else None
                })
                
        return results
    except Exception as e:
        print(f"Error fetching upcoming renewals: {e}")
        return []
    finally:
        db.close()

@router.post("/update")
async def update_renewal_status(
    insurer: str = Body(..., embed=True),
    type: str = Body(..., embed=True),
    policy_number: Union[str, int] = Body(..., embed=True),
    new_status: Optional[str] = Body(None, embed=True),
    expediente: Optional[str] = Body(None, embed=True),
    email: Optional[str] = Body(None, embed=True)
):
    """
    Update the ESTATUS_DE_RENOVACION, EXPEDIENTE, and EMAIL in the SQL database.
    """
    db = SessionLocal()
    try:
        policy_str = str(policy_number).strip().split('.')[0]
        policy = db.query(Policy).filter(Policy.policy_number == policy_str).first()
        
        if not policy:
            raise HTTPException(status_code=404, detail=f"Policy {policy_number} not found")
            
        # Retrieve related renewal
        renewal = db.query(Renewal).filter(Renewal.original_policy_id == policy.id).first()
        if not renewal:
            # Fallback create renewal if missing
            renewal = Renewal(
                original_policy_id=policy.id,
                client_id=policy.client_id,
                renewal_deadline=policy.effective_end_date,
                status="in_progress"
            )
            db.add(renewal)
            db.flush()
            
        if new_status is not None:
            renewal.insurer_response = new_status
            
        if expediente is not None:
            policy.document_link = expediente
            
        if email is not None and policy.client:
            policy.client.email = email
            
        db.commit()
        return {"message": "Policy and renewal updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating renewal: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/vida")
async def get_renovaciones_vida(days: int = 30):
    return await get_upcoming_renewals(days=days, insurer="Metlife", type="VIDA")

@router.post("/send-email")
async def send_renewal_email_endpoint(
    insurer: str = Body(..., embed=True),
    type: str = Body(..., embed=True),
    policy_number: Union[str, int] = Body(..., embed=True),
    client_name: str = Body(..., embed=True),
    end_date: str = Body(..., embed=True),
    expediente: Optional[str] = Body(None, embed=True)
):
    """
    Send renewal email using database details. Updates status in database upon success.
    """
    db = SessionLocal()
    try:
        policy_str = str(policy_number).strip().split('.')[0]
        policy = db.query(Policy).filter(Policy.policy_number == policy_str).first()
        
        if not policy or not policy.client:
            raise HTTPException(status_code=404, detail="Policy or client profile not found")
            
        recipient_email = policy.client.email
        if not recipient_email:
            raise HTTPException(
                status_code=404, 
                detail=f"No email registered for client {client_name}. Please update in the client card first."
            )
            
        # Build SMTP elements
        subject = f"Renovacion {policy_str} {policy.client.full_name}"
        body = (
            f"Buen día,\n"
            f"Comparto póliza {policy_str} con fecha Fin de Vigencia {end_date}.\n\n"
            f"La renovacion se encuentra adjunta en el correo o disponible en el sistema.\n"
            f"Nos mantenemos en contacto para cualquier duda\n\n"
            f"Atentamente Taiico Life Advisors"
        )
        
        # Read attachments if local folder exists
        attachments = []
        if expediente:
            exp_path = expediente.strip().strip("'").strip('"')
            if os.path.exists(exp_path):
                if os.path.isdir(exp_path):
                    for filename in os.listdir(exp_path):
                        file_path = os.path.join(exp_path, filename)
                        if os.path.isfile(file_path) and not filename.startswith('.'):
                            with open(file_path, "rb") as f:
                                attachments.append({
                                    "name": filename,
                                    "content": f.read()
                                })
                elif os.path.isfile(exp_path):
                    with open(exp_path, "rb") as f:
                        attachments.append({
                            "name": os.path.basename(exp_path),
                            "content": f.read()
                        })
            elif exp_path.startswith("http"):
                body += f"\n\nLink al expediente: {exp_path}"
                
        # Send Email
        recipients = [r.strip() for r in recipient_email.split(",") if r.strip()]
        send_email_smtp(subject, body, recipients, attachments)
        
        # Update database status
        renewal = db.query(Renewal).filter(Renewal.original_policy_id == policy.id).first()
        if renewal:
            renewal.insurer_response = "Enviado"
            db.commit()
            
        return {"message": f"Correo enviado a {recipient_email}"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error sending email: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al enviar correo: {str(e)}")
    finally:
        db.close()
