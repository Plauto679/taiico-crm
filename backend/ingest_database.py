import os
import sys
import datetime
import pandas as pd
import numpy as np
from pathlib import Path
from sqlalchemy.orm import Session

# Add current folder to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import (
    engine, Base, get_db, SessionLocal,
    User, Insurer, Product, Client, Policy, Payment, Renewal, Task
)

# Resolve paths
BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
BASE_DIR = PROJECT_ROOT.parent # Points to Taiico Local - Antigravity CRM in this folder

# Excel folder locations
COBRANZA_DIR = BASE_DIR / "Bases de cobranza y comisiones"
CARTERA_DIR = BASE_DIR / "Relaciones de cartera"
RENOVACIONES_DIR = BASE_DIR / "Fechas de emision de Polizas y renovaciones"
EMAILS_DIR = BASE_DIR / "Correos de los clientes"

def clean_val(val):
    if pd.isna(val) or val is None:
        return None
    if isinstance(val, str):
        cleaned = val.strip()
        return cleaned if cleaned != "" else None
    return val

def safe_parse_date(date_val):
    if pd.isna(date_val) or date_val is None:
        return None
    try:
        # If it's a pandas timestamp
        if isinstance(date_val, (pd.Timestamp, datetime.datetime)):
            return date_val.date()
        # If it's an Excel serial date number
        if isinstance(date_val, (int, float)):
            return (datetime.datetime(1899, 12, 30) + datetime.timedelta(days=int(date_val))).date()
        # Parse string
        date_str = str(date_val).strip()
        # Common formats
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y'):
            try:
                return datetime.datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        # Fallback to substring date
        if len(date_str) >= 10:
            return datetime.datetime.strptime(date_str[:10], '%Y-%m-%d').date()
    except Exception as e:
        pass
    return None

def safe_parse_numeric(val, default=0.0):
    if pd.isna(val) or val is None:
        return default
    try:
        if isinstance(val, str):
            val = val.replace('$', '').replace(',', '').strip()
        return float(val)
    except:
        return default

def ingest():
    print("====================================================")
    print("STARTING TAIICO DATABASE CLOUD INGESTION MODULE")
    print("====================================================")
    
    # 1. Initialize schema
    print("\n--- Phase 1: Re-initializing Database Schema ---")
    Base.metadata.drop_all(bind=engine) # Drop old tables for a clean sync
    Base.metadata.create_all(bind=engine)
    print("Database schema successfully generated.")
    
    db: Session = SessionLocal()
    
    # Cache maps to prevent SQL unique/integrity constraints
    client_obj_cache = {} # Cache client entities by upper name
    policy_num_cache = {} # Cache policy entities by policy_number
    
    try:
        # 2. Seed default carriers (Insurers)
        print("\n--- Phase 2: Seeding Carriers ---")
        insurers = [
            Insurer(id="metlife", name="MetLife México", portal_url="https://www.metlife.com.mx"),
            Insurer(id="sura", name="Seguros SURA", portal_url="https://www.segurossura.com.mx"),
            Insurer(id="aarco", name="AARCO Agente de Seguros", portal_url="https://www.aarco.com.mx"),
            Insurer(id="axa", name="AXA Seguros", portal_url="https://axa.mx")
        ]
        for ins in insurers:
            db.merge(ins)
        db.commit()
        print("Insurers seeded successfully.")
        
        # 3. Seed default staff (Users)
        print("\n--- Phase 3: Seeding Internal Broker & Staff Roles ---")
        default_users = [
            User(id="usr_admin", name="Alberto Alfaro Mendoza", email="alberto.alfaro@taiico.com", role="management"),
            User(id="usr_pamela", name="Pamela Asmara Alfaro Mendoza", email="pamela.alfaro@taiico.com", role="broker"),
            User(id="usr_cobranza", name="Cobranza Staff", email="cobranza@taiico.com", role="cobranza"),
            User(id="usr_claims", name="Claims Agent", email="claims@taiico.com", role="claims"),
            User(id="usr_recruiter", name="Recruiter Agent", email="recruiter@taiico.com", role="recruiter")
        ]
        for user in default_users:
            db.merge(user)
        db.commit()
        print("Staff users seeded successfully.")

        # 4. Seed Products
        print("\n--- Phase 4: Seeding Standard Products ---")
        prod_met_vida = Product(id="prod_met_vida", insurer_id="metlife", name="MetLife Vida Individual", branch="VIDA")
        prod_met_gmm = Product(id="prod_met_gmm", insurer_id="metlife", name="MetLife Gastos Médicos Mayores (GMM)", branch="GMM")
        prod_sura_vida = Product(id="prod_sura_vida", insurer_id="sura", name="Sura Vida", branch="VIDA")
        prod_sura_gmm = Product(id="prod_sura_gmm", insurer_id="sura", name="Sura GMM", branch="GMM")
        prod_aarco_vida = Product(id="prod_aarco_vida", insurer_id="aarco", name="Aarco Vida", branch="VIDA")
        
        for p in [prod_met_vida, prod_met_gmm, prod_sura_vida, prod_sura_gmm, prod_aarco_vida]:
            db.merge(p)
        db.commit()
        print("Insurance products seeded successfully.")

        # 5. Ingest Client Emails & Phones
        print("\n--- Phase 5: Loading Client Contact Information ---")
        client_contact_map = {}
        email_excel = EMAILS_DIR / "Clientes Correos Taiico.xlsx"
        if email_excel.exists():
            print(f"Reading contacts from: {email_excel.name}")
            df_emails = pd.read_excel(email_excel)
            for _, row in df_emails.iterrows():
                name = clean_val(row.get('Clientes'))
                mail = clean_val(row.get('Mail'))
                phone = clean_val(row.get('Telefono'))
                if name:
                    client_contact_map[name.upper()] = {
                        "email": mail,
                        "phone": str(phone) if phone else None
                    }
            print(f"Loaded contact records for {len(client_contact_map)} clients.")
        else:
            print("[Warning] Clientes Correos Taiico.xlsx not found.")

        # 6. Parse and Ingest Metlife Cartera (sheet Vida and GMM)
        print("\n--- Phase 6: Parsing MetLife Cartera Excel ---")
        cartera_metlife_excel = CARTERA_DIR / "Cartera Metlife.xlsx"
        
        if cartera_metlife_excel.exists():
            # Ingest Metlife Vida
            try:
                df_met_vida = pd.read_excel(cartera_metlife_excel, sheet_name="Vida")
                print(f"Parsing MetLife Vida Cartera ({len(df_met_vida)} records)...")
                for _, row in df_met_vida.iterrows():
                    pol_num = clean_val(row.get('Poliza'))
                    contratante = clean_val(row.get('Contratante'))
                    prospectador = clean_val(row.get('PROSPECTADOR '))
                    pct = safe_parse_numeric(row.get('PORCENTAJE '))
                    
                    if not pol_num or not contratante:
                        continue
                    
                    pol_num_str = str(pol_num).split('.')[0].strip() # Clean integer conversion
                    contratante_upper = contratante.upper().strip()
                    
                    # Duplicate check
                    if pol_num_str in policy_num_cache:
                        continue
                    
                    # Resolve client
                    if contratante_upper not in client_obj_cache:
                        contact = client_contact_map.get(contratante_upper, {"email": None, "phone": None})
                        client = Client(
                            full_name=contratante,
                            email=contact["email"],
                            phone=contact["phone"],
                            responsible_user_id="usr_pamela",
                            status="active",
                            metadata_json={"prospectador": prospectador}
                        )
                        db.add(client)
                        db.flush()
                        client_obj_cache[contratante_upper] = client
                    
                    client = client_obj_cache[contratante_upper]
                    
                    # Create Policy
                    policy = Policy(
                        policy_number=pol_num_str,
                        client_id=client.id,
                        insurer_id="metlife",
                        product_id="prod_met_vida",
                        effective_start_date=datetime.date(2025, 1, 1), 
                        effective_end_date=datetime.date(2026, 1, 1),
                        status="in_force",
                        premium_amount=0.0,
                        payment_frequency="annual",
                        responsible_user_id="usr_pamela",
                        commission_percentage=pct
                    )
                    db.add(policy)
                    db.flush()
                    policy_num_cache[pol_num_str] = policy
            except Exception as e:
                print(f"Error reading Metlife Vida: {e}")
                db.rollback()
                
            # Ingest Metlife GMM
            try:
                df_met_gmm = pd.read_excel(cartera_metlife_excel, sheet_name="GMM")
                print(f"Parsing MetLife GMM Cartera ({len(df_met_gmm)} records)...")
                for _, row in df_met_gmm.iterrows():
                    pol_num = clean_val(row.get('POLIZA '))
                    pol_num_actual = clean_val(row.get('Poliza actual'))
                    contratante = clean_val(row.get('Contratante'))
                    prospectador = clean_val(row.get('PROSPECTADOR '))
                    pct = safe_parse_numeric(row.get('PORCENTAJE'))
                    
                    pol_num_to_use = pol_num_actual if pol_num_actual else pol_num
                    if not pol_num_to_use or not contratante:
                        continue
                    
                    pol_num_str = str(pol_num_to_use).split('.')[0].strip()
                    contratante_upper = contratante.upper().strip()
                    
                    # Duplicate check
                    if pol_num_str in policy_num_cache:
                        continue
                    
                    # Resolve client
                    if contratante_upper not in client_obj_cache:
                        contact = client_contact_map.get(contratante_upper, {"email": None, "phone": None})
                        client = Client(
                            full_name=contratante,
                            email=contact["email"],
                            phone=contact["phone"],
                            responsible_user_id="usr_pamela",
                            status="active",
                            metadata_json={"prospectador": prospectador}
                        )
                        db.add(client)
                        db.flush()
                        client_obj_cache[contratante_upper] = client
                    
                    client = client_obj_cache[contratante_upper]
                    
                    # Create Policy
                    policy = Policy(
                        policy_number=pol_num_str,
                        client_id=client.id,
                        insurer_id="metlife",
                        product_id="prod_met_gmm",
                        effective_start_date=datetime.date(2025, 1, 1),
                        effective_end_date=datetime.date(2026, 1, 1),
                        status="in_force",
                        premium_amount=0.0,
                        payment_frequency="annual",
                        responsible_user_id="usr_pamela",
                        commission_percentage=pct
                    )
                    db.add(policy)
                    db.flush()
                    policy_num_cache[pol_num_str] = policy
            except Exception as e:
                print(f"Error reading Metlife GMM: {e}")
                db.rollback()
            db.commit()
        else:
            print("[Warning] Cartera Metlife.xlsx not found.")

        # 7. Ingest SURA Cartera
        print("\n--- Phase 7: Parsing SURA Cartera Excel ---")
        cartera_sura_excel = CARTERA_DIR / "Cartera SURA.xlsx"
        if cartera_sura_excel.exists():
            try:
                df_sura = pd.read_excel(cartera_sura_excel, sheet_name="SURA")
                print(f"Parsing SURA Cartera ({len(df_sura)} records)...")
                for _, row in df_sura.iterrows():
                    pol_num = clean_val(row.get('PÓLIZA'))
                    prospectador = clean_val(row.get('PROSPECTADOR'))
                    pct = safe_parse_numeric(row.get('PORCENTAJE'))
                    
                    if not pol_num:
                        continue
                    
                    pol_num_str = str(pol_num).split('.')[0].strip()
                    
                    # Duplicate check
                    if pol_num_str in policy_num_cache:
                        continue
                    
                    contratante_placeholder = f"SURA CLIENT P-{pol_num_str}"
                    
                    if contratante_placeholder not in client_obj_cache:
                        client = Client(
                            full_name=contratante_placeholder,
                            responsible_user_id="usr_pamela",
                            status="active",
                            metadata_json={"prospectador": prospectador}
                        )
                        db.add(client)
                        db.flush()
                        client_obj_cache[contratante_placeholder] = client
                        
                    client = client_obj_cache[contratante_placeholder]
                    
                    policy = Policy(
                        policy_number=pol_num_str,
                        client_id=client.id,
                        insurer_id="sura",
                        product_id="prod_sura_gmm", 
                        effective_start_date=datetime.date(2025, 1, 1),
                        effective_end_date=datetime.date(2026, 1, 1),
                        status="in_force",
                        premium_amount=0.0,
                        payment_frequency="annual",
                        responsible_user_id="usr_pamela",
                        commission_percentage=pct
                    )
                    db.add(policy)
                    db.flush()
                    policy_num_cache[pol_num_str] = policy
                db.commit()
            except Exception as e:
                print(f"Error reading SURA Cartera: {e}")
                db.rollback()
        else:
            print("[Warning] Cartera SURA.xlsx not found.")

        # 8. Ingest Invoiced Payments (Cobranza Sheets)
        print("\n--- Phase 8: Reconciling Payments (Cobranza Ingestion) ---")
        
        # 8.1 Metlife Cobranza (Vida and GMM)
        metlife_cobranza = COBRANZA_DIR / "Metlife base cobranza.xlsx"
        if metlife_cobranza.exists():
            # Vida sheet
            try:
                df_cob_vida = pd.read_excel(metlife_cobranza, sheet_name="Vida")
                print(f"Ingesting Metlife Vida Payments ({len(df_cob_vida)} rows)...")
                for _, row in df_cob_vida.iterrows():
                    pol_num = clean_val(row.get('# de Póliza'))
                    prod_name = clean_val(row.get('Producto'))
                    fecha_pago = safe_parse_date(row.get('Fecha de Pago del Recibo'))
                    prima_pagada = safe_parse_numeric(row.get('Prima Pagada'))
                    com_neta = safe_parse_numeric(row.get('Comisión Neta'))
                    
                    if not pol_num:
                        continue
                    
                    pol_num_str = str(pol_num).split('.')[0].strip()
                    
                    policy = policy_num_cache.get(pol_num_str)
                    if policy:
                        policy.premium_amount = max(policy.premium_amount, prima_pagada)
                        
                        payment = Payment(
                            policy_id=policy.id,
                            client_id=policy.client_id,
                            expected_amount=prima_pagada,
                            paid_amount=prima_pagada,
                            due_date=fecha_pago if fecha_pago else datetime.date.today(),
                            received_date=fecha_pago,
                            status="paid" if fecha_pago else "missing",
                            grace_period_deadline=fecha_pago if fecha_pago else datetime.date.today(),
                            source_file="Metlife base cobranza.xlsx (Vida)",
                            notes=f"Ingested from Metlife base cobranza sheet. Product: {prod_name}. Commission: ${com_neta}"
                        )
                        db.add(payment)
                db.commit()
            except Exception as e:
                print(f"Error reading Metlife Vida Cobranza: {e}")
                db.rollback()

            # GMM sheet
            try:
                df_cob_gmm = pd.read_excel(metlife_cobranza, sheet_name="GMM")
                print(f"Ingesting Metlife GMM Payments ({len(df_cob_gmm)} rows)...")
                for _, row in df_cob_gmm.iterrows():
                    pol_num = clean_val(row.get('# de Póliza'))
                    prod_name = clean_val(row.get('Producto'))
                    fecha_pago = safe_parse_date(row.get('Fecha de Pago del Recibo'))
                    prima_pagada = safe_parse_numeric(row.get('Prima Pagada'))
                    com_neta = safe_parse_numeric(row.get('Comisión Neta'))
                    
                    if not pol_num:
                        continue
                    
                    pol_num_str = str(pol_num).split('.')[0].strip()
                    
                    policy = policy_num_cache.get(pol_num_str)
                    if policy:
                        policy.premium_amount = max(policy.premium_amount, prima_pagada)
                        
                        payment = Payment(
                            policy_id=policy.id,
                            client_id=policy.client_id,
                            expected_amount=prima_pagada,
                            paid_amount=prima_pagada,
                            due_date=fecha_pago if fecha_pago else datetime.date.today(),
                            received_date=fecha_pago,
                            status="paid" if fecha_pago else "missing",
                            grace_period_deadline=fecha_pago if fecha_pago else datetime.date.today(),
                            source_file="Metlife base cobranza.xlsx (GMM)",
                            notes=f"Ingested from Metlife base cobranza sheet. Product: {prod_name}. Commission: ${com_neta}"
                        )
                        db.add(payment)
                db.commit()
            except Exception as e:
                print(f"Error reading Metlife GMM Cobranza: {e}")
                db.rollback()

        # 8.2 SURA Cobranza
        sura_cobranza = COBRANZA_DIR / "SURA base cobranza.xlsx"
        if sura_cobranza.exists():
            try:
                df_sura_cob = pd.read_excel(sura_cobranza)
                print(f"Ingesting SURA Payments ({len(df_sura_cob)} rows)...")
                for _, row in df_sura_cob.iterrows():
                    pol_num = clean_val(row.get('Póliza'))
                    contratante = clean_val(row.get('Contratante'))
                    prima_neta = safe_parse_numeric(row.get('Prima Neta'))
                    fecha_pago = safe_parse_date(row.get('Fecha aplicación de la póliza'))
                    
                    if not pol_num:
                        continue
                    
                    pol_num_str = str(pol_num).split('.')[0].strip()
                    
                    policy = policy_num_cache.get(pol_num_str)
                    if policy:
                        client = policy.client
                        if client and "SURA CLIENT P-" in client.full_name and contratante:
                            # Re-cache using updated name
                            print(f"Reconciled client placeholder: {client.full_name} -> {contratante}")
                            client.full_name = contratante
                            contact = client_contact_map.get(contratante.upper().strip(), {"email": None, "phone": None})
                            client.email = contact["email"]
                            client.phone = contact["phone"]
                            db.flush()
                        
                        policy.premium_amount = max(policy.premium_amount, prima_neta)
                        
                        payment = Payment(
                            policy_id=policy.id,
                            client_id=policy.client_id,
                            expected_amount=prima_neta,
                            paid_amount=prima_neta,
                            due_date=fecha_pago if fecha_pago else datetime.date.today(),
                            received_date=fecha_pago,
                            status="paid" if fecha_pago else "missing",
                            grace_period_deadline=fecha_pago if fecha_pago else datetime.date.today(),
                            source_file="SURA base cobranza.xlsx",
                            notes=f"Ingested from SURA base cobranza."
                        )
                        db.add(payment)
                db.commit()
            except Exception as e:
                print(f"Error reading SURA Cobranza: {e}")
                db.rollback()

        # 8.3 AARCO Cobranza
        aarco_cobranza = COBRANZA_DIR / "AARCO base cobranza.xlsx"
        if aarco_cobranza.exists():
            try:
                df_aarco_cob = pd.read_excel(aarco_cobranza)
                print(f"Ingesting AARCO Payments & creating missing policies ({len(df_aarco_cob)} rows)...")
                for _, row in df_aarco_cob.iterrows():
                    pol_num = clean_val(row.get('NUM_POL'))
                    cliente = clean_val(row.get('CLIENTE'))
                    prospectador = clean_val(row.get('PROSPECTADOR'))
                    prima_neta = safe_parse_numeric(row.get('PRIMA_NETA_MN'))
                    fecha_pago = safe_parse_date(row.get('F_COBRO'))
                    cia = clean_val(row.get('CIA'))
                    
                    if not pol_num or not cliente:
                        continue
                    
                    pol_num_str = str(pol_num).strip()
                    cliente_upper = cliente.upper().strip()
                    
                    policy = policy_num_cache.get(pol_num_str)
                    if not policy:
                        if cliente_upper not in client_obj_cache:
                            contact = client_contact_map.get(cliente_upper, {"email": None, "phone": None})
                            client = Client(
                                full_name=cliente,
                                email=contact["email"],
                                phone=contact["phone"],
                                responsible_user_id="usr_pamela",
                                status="active",
                                metadata_json={"prospectador": prospectador}
                            )
                            db.add(client)
                            db.flush()
                            client_obj_cache[cliente_upper] = client
                        client = client_obj_cache[cliente_upper]
                        
                        policy = Policy(
                            policy_number=pol_num_str,
                            client_id=client.id,
                            insurer_id="aarco",
                            product_id="prod_aarco_vida",
                            effective_start_date=datetime.date(2025, 1, 1),
                            effective_end_date=datetime.date(2026, 1, 1),
                            status="in_force",
                            premium_amount=prima_neta,
                            payment_frequency="annual",
                            responsible_user_id="usr_pamela"
                        )
                        db.add(policy)
                        db.flush()
                        policy_num_cache[pol_num_str] = policy
                        
                    payment = Payment(
                        policy_id=policy.id,
                        client_id=policy.client_id,
                        expected_amount=prima_neta,
                        paid_amount=prima_neta,
                        due_date=fecha_pago if fecha_pago else datetime.date.today(),
                        received_date=fecha_pago,
                        status="paid" if fecha_pago else "missing",
                        grace_period_deadline=fecha_pago if fecha_pago else datetime.date.today(),
                        source_file="AARCO base cobranza.xlsx",
                        notes=f"Ingested from Aarco base. Insurance Company (CIA): {cia}."
                    )
                    db.add(payment)
                db.commit()
            except Exception as e:
                print(f"Error reading AARCO Cobranza: {e}")
                db.rollback()

        # 9. Ingest Renewals
        print("\n--- Phase 9: Ingesting Policy Renewals ---")
        
        def process_renewal_sheet(filepath, sheet_name=None, policy_col="POLIZA", end_date_col="FIN_VIG"):
            if not os.path.exists(filepath):
                print(f"[Warning] Renewal file not found: {os.path.basename(filepath)}")
                return
            try:
                df_ren = pd.read_excel(filepath, sheet_name=sheet_name) if sheet_name else pd.read_excel(filepath)
                print(f"Processing renewals from {os.path.basename(filepath)} ({len(df_ren)} records)...")
                
                processed_policies = set()
                for _, row in df_ren.iterrows():
                    pol_num = clean_val(row.get(policy_col))
                    fecha_fin = safe_parse_date(row.get(end_date_col))
                    estatus_ren = clean_val(row.get('ESTATUS_DE_RENOVACION'))
                    
                    if not pol_num or not fecha_fin:
                        continue
                    
                    pol_num_str = str(pol_num).split('.')[0].strip()
                    
                    if pol_num_str in processed_policies:
                        continue
                    processed_policies.add(pol_num_str)
                    
                    policy = policy_num_cache.get(pol_num_str)
                    if policy:
                        policy.effective_end_date = fecha_fin
                        policy.effective_start_date = fecha_fin - datetime.timedelta(days=365)
                        
                        today = datetime.date.today()
                        days_until_renewal = (fecha_fin - today).days
                        risk = "none"
                        if days_until_renewal <= 30:
                            risk = "high"
                        elif days_until_renewal <= 60:
                            risk = "medium"
                        elif days_until_renewal <= 90:
                            risk = "low"
                        
                        renewal = Renewal(
                            original_policy_id=policy.id,
                            client_id=policy.client_id,
                            status="approaching" if days_until_renewal > 0 else "in_progress",
                            renewal_deadline=fecha_fin,
                            risk_level=risk,
                            insurer_response=estatus_ren
                        )
                        db.add(renewal)
                db.commit()
            except Exception as e:
                print(f"Error processing renewal file {filepath}: {e}")
                db.rollback()

        # Ingest Metlife Vida Renovations
        process_renewal_sheet(
            filepath=RENOVACIONES_DIR / "Metlife Vida.xlsx",
            sheet_name="Vida",
            policy_col="POLIZA_ACTUAL",
            end_date_col="FIN_VIG"
        )
        
        # Ingest Metlife GMM Renovations
        process_renewal_sheet(
            filepath=RENOVACIONES_DIR / "Metlife GMM.xlsx",
            sheet_name="GMM",
            policy_col="NPOLIZA",
            end_date_col="FFINVIG"
        )
        
        # Ingest SURA Renovations
        process_renewal_sheet(
            filepath=RENOVACIONES_DIR / "SURA.xlsx",
            policy_col="POLIZA",
            end_date_col="FIN VIGENCIA"
        )

        # Ingest AARCO & AXA Renovations
        process_renewal_sheet(
            filepath=RENOVACIONES_DIR / "AARCO & AXA.xlsx",
            policy_col="POLIZA",
            end_date_col="FIN VIGENCIA"
        )

        print("\n====================================================")
        print("DATABASE INGESTION COMPLETED SUCCESSFULLY!")
        print("====================================================")
        
    except Exception as e:
        print(f"\n[FATAL ERROR] Ingestion aborted due to error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    ingest()
