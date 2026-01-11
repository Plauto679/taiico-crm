from fastapi import APIRouter, HTTPException, Query, Body
import pandas as pd
from typing import List, Optional
from datetime import datetime, timedelta
from config import METLIFE_PATHS, SURA_PATHS, SHEET_NAMES
import numpy as np
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from config import METLIFE_PATHS, SURA_PATHS, AARCO_PATHS, SHEET_NAMES, CLIENT_EMAILS_PATH

# Load env variables if not already loaded (simple loader as per user usage)
# Since we created .env in backend/, we can load it.
ENV_PATH = Path('backend/.env').resolve() if os.path.exists('backend/.env') else Path('.env').resolve()

def load_env_file():
    if not ENV_PATH.exists():
        return
    for raw_line in ENV_PATH.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

load_env_file()

def normalize_name(value: str) -> str:
    if not value:
        return ""
    return " ".join(str(value).strip().upper().split())

def get_client_email(client_name: str) -> Optional[str]:
    """
    Search for client email in CLIENT_EMAILS_PATH.
    """
    if not CLIENT_EMAILS_PATH.exists():
        print(f"Client emails file found: {CLIENT_EMAILS_PATH}")
        return None
        
    try:
        df = pd.read_excel(CLIENT_EMAILS_PATH)
        # Columns: 'Clientes', 'Mail'
        if 'Clientes' not in df.columns or 'Mail' not in df.columns:
            print("Columns 'Clientes' or 'Mail' not found in email file")
            return None
            
        norm_name = normalize_name(client_name)
        df['__norm'] = df['Clientes'].apply(normalize_name)
        
        match = df[df['__norm'] == norm_name]
        if not match.empty:
            return str(match.iloc[0]['Mail']).strip()
            
        return None
    except Exception as e:
        print(f"Error reading client emails: {e}")
        return None

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
    
    # CCs
    cc_list = ["pamela.alfaro@taiico.com", "clientes@taiico.com", "christopher.tinoco@taiico.com"]
    message["Cc"] = ", ".join(cc_list)
    
    message.set_content(body)

    for att in attachments:
        name = att.get("name")
        content = att.get("content")
        if name and content:
            message.add_attachment(
                content,
                maintype="application",
                subtype="octet-stream", # Generic binary
                filename=name,
            )

    with smtplib.SMTP(host, port) as server:
        if use_starttls:
            server.starttls()
        server.login(user, password)
        server.send_message(message)


router = APIRouter(
    prefix="/renovaciones",
    tags=["renovaciones"]
)

def clean_data(df: pd.DataFrame) -> List[dict]:
    """
    Convert DataFrame to a list of dicts, handling NaN/NaT values.
    """
    df = df.replace({np.nan: None})
    return df.to_dict(orient="records")

def parse_gmm_date(val):
    """
    Parse YYYYMMDD integer/string to ISO date string YYYY-MM-DD.
    """
    if pd.isna(val):
        return None
    s = str(int(val)).zfill(8)
    try:
        dt = datetime.strptime(s, "%Y%m%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None

def parse_vida_date(val):
    """
    Parse various date formats to ISO date string YYYY-MM-DD.
    """
    if pd.isna(val):
        return None
    try:
        dt = pd.to_datetime(val, errors='coerce')
        if pd.isna(dt):
            return None
        return dt.strftime("%Y-%m-%d")
    except:
        return None

def clean_money(val):
    """
    Convert currency string or number to float.
    """
    if pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    # Remove $ and ,
    s = str(val).replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None

def clean_gmm(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and normalize Metlife GMM data.
    Returns original columns as requested.
    """
    # 1. Date Conversion
    date_cols = ["FINIVIG", "FFINVIG", "PAGADOHASTA"]
    for col in date_cols:
        if col in df.columns:
            df[col] = df[col].apply(parse_gmm_date)

    # 2. Money Conversion
    money_cols = ["PRIMA", "PRIMA.1", "RECARGO", "GTOSEXP", "IVA", "DEDUCIBLE"]
    for col in money_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_money)

    # 3. Percentage Conversion
    if "COASEGURO" in df.columns:
        df["COASEGURO"] = pd.to_numeric(df["COASEGURO"], errors="coerce") / 100.0

    # 4. Select requested columns
    requested_cols = [
        "NPOLIZA", "POLORIG", "CONTRATANTE", "FFINVIG", 
        "PRIMA.1", "IVA", "NOMBREL", "DEDUCIBLE", "PAGADOHASTA",
        "COASEGURO", "ESTATUS_DE_RENOVACION", "EXPEDIENTE", "Email"
    ]
    
    # Ensure all columns exist
    for col in requested_cols:
        if col not in df.columns:
            df[col] = None
            
    # Remove duplicates based on Policy Number (NPOLIZA)
    # This ensures we only see one row per policy, even if the source has multiple rows (e.g. per insured)
    df = df[requested_cols].drop_duplicates(subset=["NPOLIZA"])
            
    return df

def clean_vida(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and normalize Metlife Vida data.
    Returns original columns as requested.
    """
    # 1. Date Conversion
    date_cols = ["INI_VIG", "FIN_VIG", "PAGADO_HASTA"]
    for col in date_cols:
        if col in df.columns:
            df[col] = df[col].apply(parse_vida_date)

    # 2. Money Conversion
    money_cols = ["PRIMA_ANUAL", "PRIMA_MODAL"]
    for col in money_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_money)

    # 3. Select requested columns
    requested_cols = [
        "POLIZA_ACTUAL", "CONTRATANTE", "INI_VIG", 
        "FIN_VIG", "FORMA_PAGO", "CONDUCTO_COBRO", 
        "AGENTE", "PRIMA_ANUAL", "PRIMA_MODAL", "PAGADO_HASTA",
        "ESTATUS_DE_RENOVACION", "EXPEDIENTE", "Email"
    ]
    
    # Ensure all columns exist
    for col in requested_cols:
        if col not in df.columns:
            df[col] = None

    return df[requested_cols]

def clean_sura(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and normalize SURA data.
    """
    # Columns: 'POLIZA', 'NOMBRE', 'INICIO VIGENCIA', 'FIN VIGENCIA', 'RAMO', 'PRIMA', 'PERIODICIDAD_PAGO', 'PROSPECTADOR', 'ESTATUS_DE_RENOVACION'
    
    # 1. Date Conversion
    date_cols = ["INICIO VIGENCIA", "FIN VIGENCIA"]
    for col in date_cols:
        if col in df.columns:
            df[col] = df[col].apply(parse_vida_date) # Use generic parser

    # 2. Money Conversion
    if "PRIMA" in df.columns:
        df["PRIMA"] = df["PRIMA"].apply(clean_money)

    requested_cols = [
        "POLIZA", "NOMBRE", "INICIO VIGENCIA", "FIN VIGENCIA", 
        "RAMO", "PRIMA", "PERIODICIDAD_PAGO", "PROSPECTADOR", 
        "ESTATUS_DE_RENOVACION", "EXPEDIENTE", "Email"
    ]
    
    for col in requested_cols:
        if col not in df.columns:
            df[col] = None
            
    return df[requested_cols]

@router.get("/upcoming")
async def get_upcoming_renewals(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    days: Optional[int] = Query(30, description="Legacy: Days to look ahead"),
    insurer: str = Query("Metlife", description="Insurer name"),
    type: str = Query("ALL", description="Policy type: ALL, VIDA, GMM")
):
    """
    Get upcoming renewals for a specific insurer and type.
    Supports date range filtering.
    """
    results = []
    
    # Determine date range
    today = datetime.now()
    
    if start_date and end_date:
        start_str = start_date
        end_str = end_date
    else:
        # Fallback to legacy 'days' logic if no range provided
        start_str = today.strftime("%Y-%m-%d")
        end_str = (today + timedelta(days=days)).strftime("%Y-%m-%d")

    if insurer.lower() == "metlife":
        # Load and process VIDA
        if type.upper() in ["ALL", "VIDA"]:
            try:
                df_vida = pd.read_excel(METLIFE_PATHS["RENOVACIONES_VIDA"], sheet_name=SHEET_NAMES["RENOVACIONES_VIDA"])
                df_vida = clean_vida(df_vida)
                
                # Filter by date on FIN_VIG
                if "FIN_VIG" in df_vida.columns:
                    mask = (df_vida["FIN_VIG"] >= start_str) & (df_vida["FIN_VIG"] <= end_str)
                    df_vida = df_vida[mask]
                
                results.extend(clean_data(df_vida))
            except Exception as e:
                print(f"Error loading Vida: {e}")

        # Load and process GMM
        if type.upper() in ["ALL", "GMM"]:
            try:
                df_gmm = pd.read_excel(METLIFE_PATHS["RENOVACIONES_GMM"], sheet_name=SHEET_NAMES["RENOVACIONES_GMM"])
                df_gmm = clean_gmm(df_gmm)
                
                # Filter by date on FFINVIG
                if "FFINVIG" in df_gmm.columns:
                    mask = (df_gmm["FFINVIG"] >= start_str) & (df_gmm["FFINVIG"] <= end_str)
                    df_gmm = df_gmm[mask]
                
                results.extend(clean_data(df_gmm))
            except Exception as e:
                 print(f"Error loading GMM: {e}")

    elif insurer.lower() == "sura":
        try:
            df_sura = pd.read_excel(SURA_PATHS["RENOVACIONES"])
            df_sura = clean_sura(df_sura)
            
            # Filter by date on FIN VIGENCIA
            if "FIN VIGENCIA" in df_sura.columns:
                mask = (df_sura["FIN VIGENCIA"] >= start_str) & (df_sura["FIN VIGENCIA"] <= end_str)
                df_sura = df_sura[mask]
                
            results.extend(clean_data(df_sura))
        except Exception as e:
            print(f"Error loading SURA: {e}")

    elif insurer.upper() == "AARCO_AXA":
        try:
            df_aarco = pd.read_excel(AARCO_PATHS["RENOVACIONES"])
            df_aarco = clean_aarco(df_aarco)
            
            # Filter by date on FIN VIGENCIA
            if "FIN VIGENCIA" in df_aarco.columns:
                mask = (df_aarco["FIN VIGENCIA"] >= start_str) & (df_aarco["FIN VIGENCIA"] <= end_str)
                df_aarco = df_aarco[mask]
                
            results.extend(clean_data(df_aarco))
        except Exception as e:
            print(f"Error loading AARCO: {e}")

    return results

@router.post("/update")
async def update_renewal_status(
    insurer: str = Body(..., embed=True),
    type: str = Body(..., embed=True),
    policy_number: str | int = Body(..., embed=True),
    new_status: str = Body(..., embed=True),
    expediente: Optional[str] = Body(None, embed=True)
):
    """
    Update the ESTATUS_DE_RENOVACION and EXPEDIENTE for a specific policy.
    """
    print(f"Received update request: Insurer={insurer}, Type={type}, Policy={policy_number}, Status={new_status}, Expediente={expediente}")
    
    file_path = None
    sheet_name = None
    id_col = None
    
    if insurer.lower() == "metlife":
        if type.upper() == "VIDA":
            file_path = METLIFE_PATHS["RENOVACIONES_VIDA"]
            sheet_name = SHEET_NAMES["RENOVACIONES_VIDA"]
            id_col = "POLIZA_ACTUAL"
        elif type.upper() == "GMM":
            file_path = METLIFE_PATHS["RENOVACIONES_GMM"]
            sheet_name = SHEET_NAMES["RENOVACIONES_GMM"]
            id_col = "NPOLIZA"
    elif insurer.lower() == "sura":
        file_path = SURA_PATHS["RENOVACIONES"]
        # Determine actual sheet name for SURA
        try:
            xl = pd.ExcelFile(file_path)
            sheet_name = xl.sheet_names[0] # Use the first sheet
            id_col = "POLIZA"
        except Exception as e:
            print(f"Error getting sheet name for SURA: {e}")
            raise HTTPException(status_code=500, detail="Error accessing SURA file")

    elif insurer.upper() == "AARCO_AXA":
        file_path = AARCO_PATHS["RENOVACIONES"]
        # Determine actual sheet name
        try:
            xl = pd.ExcelFile(file_path)
            sheet_name = xl.sheet_names[0]
            # Use exact ID col from user description or cleaned df? 
            # In update, we read raw excel, so we need raw column name.
            # User provided: "NUM POL  ACTUAL" (two spaces in description).
            # But wait, if we read raw, we must match raw.
            # actually, let's normalize columns in the raw df immediately after read to be safe?
            # Or just use the double space here.
            id_col = "NUM POL  ACTUAL" 
        except Exception as e:
             print(f"Error getting sheet name for AARCO: {e}")
             raise HTTPException(status_code=500, detail="Error accessing AARCO file")
             
    if not file_path or not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Read the Excel file
        print(f"Reading file: {file_path}, Sheet: {sheet_name}")
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        
        # Ensure columns exist
        if "ESTATUS_DE_RENOVACION" not in df.columns:
            print("Adding ESTATUS_DE_RENOVACION column")
            df["ESTATUS_DE_RENOVACION"] = None
        
        if "EXPEDIENTE" not in df.columns:
            print("Adding EXPEDIENTE column")
            df["EXPEDIENTE"] = None
            
        # Find and update the row
        # Convert ID column to string for comparison to be safe
        # Also clean the policy_number input
        policy_str = str(policy_number).strip()
        
        # Create a temporary string column for matching
        # Handle the column mapping for AARCO if needed
        # If we didn't rename cols in df yet, we access by id_col
        
        if id_col not in df.columns and insurer.upper() == "AARCO_AXA":
             # New schema uses "POLIZA"
             if "POLIZA" in df.columns:
                 id_col = "POLIZA"
             # Try double space version if single space not found (legacy check)
             elif "NUM POL  ACTUAL" in df.columns:
                 id_col = "NUM POL  ACTUAL"
                 
        if id_col not in df.columns:
             print(f"ID Column {id_col} not found in {df.columns.tolist()}")
             raise HTTPException(status_code=500, detail=f"ID Column {id_col} not found")

        df['__id_str'] = df[id_col].astype(str).str.strip().str.replace('.0', '', regex=False)
        policy_str_clean = policy_str.replace('.0', '')
        
        print(f"Searching for policy: {policy_str_clean} in column {id_col}")
        
        # Check if policy exists
        if policy_str_clean not in df['__id_str'].values:
             print(f"Policy {policy_str_clean} not found. Available IDs sample: {df['__id_str'].head().tolist()}")
             raise HTTPException(status_code=404, detail=f"Policy {policy_number} not found")
             
        # Update status
        mask = df['__id_str'] == policy_str_clean
        df.loc[mask, "ESTATUS_DE_RENOVACION"] = new_status
        
        # Update expediente if provided (allow empty string to clear it)
        if expediente is not None:
             df.loc[mask, "EXPEDIENTE"] = expediente
        
        # Drop temp column
        df = df.drop(columns=['__id_str'])
        
        # Save back to Excel
        print("Saving changes...")
        with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            
        print("Update successful")
        return {"message": "Policy updated successfully"}

    except Exception as e:
        print(f"Error updating policy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Keep legacy endpoints for backward compatibility if needed, but redirecting logic
@router.get("/vida")
async def get_renovaciones_vida(days: int = 30):
    return await get_upcoming_renewals(days=days, insurer="Metlife", type="VIDA")

@router.post("/send-email")
async def send_renewal_email_endpoint(
    insurer: str = Body(..., embed=True),
    type: str = Body(..., embed=True),
    policy_number: str | int = Body(..., embed=True),
    client_name: str = Body(..., embed=True),
    end_date: str = Body(..., embed=True), # Fin de Vigencia
    expediente: Optional[str] = Body(None, embed=True)
):
    """
    Send renewal email to the client using SMTP.
    Matches client name to email, constructs body, sends email, and updates 'Email' column.
    """
    print(f"Sending email for: {client_name}, Policy: {policy_number}")
    
    # 1. Get Client Email
    recipient_email = get_client_email(client_name)
    if not recipient_email:
        raise HTTPException(status_code=404, detail=f"No existe correo para cliente {client_name}. Favor de agregarlo en la base de 'Clientes Correos Taiico'.")

    # 2. Build Email Content
    subject = f"Renovacion {policy_number} {client_name}"
    
    body = (
        f"Buen día,\n"
        f"Comparto póliza {policy_number} con fecha Fin de Vigencia {end_date}.\n\n"
        f"La renovacion se encuentra adjunta en el correo.\n"
        f"Nos mantenemos en contacto para cualquier duda\n\n"
        f"Atentamente Taiico Life Advisors"
    )

    # 3. Handle Attachments (Expediente)
    # Expediente can be a folder path. If so, attach all files inside.
    attachments = []
    
    if expediente:
        # Clean path: remove quotes if present, strip whitespace
        expediente = expediente.strip().strip("'").strip('"')
        print(f"Processing Expediente path: {expediente}")
        
        if os.path.exists(expediente):
            if os.path.isdir(expediente):
                print(f"Path is a directory: {expediente}")
                # Is a directory, walk through it (non-recursive for now, or just top level files?)
                # User said "all the files that are inside". I'll assume top-level files to avoid nested chaos.
                try:
                    files = os.listdir(expediente)
                    print(f"Found {len(files)} files in directory")
                    for filename in files:
                        file_path = os.path.join(expediente, filename)
                        if os.path.isfile(file_path):
                            # Skip hidden files
                            if filename.startswith('.'):
                                continue
                            try:
                                with open(file_path, "rb") as f:
                                    attachments.append({
                                        "name": filename,
                                        "content": f.read()
                                    })
                            except Exception as e:
                                print(f"Error reading file {filename}: {e}")
                except Exception as e:
                     print(f"Error reading directory {expediente}: {e}")

            elif os.path.isfile(expediente):
                 # Is a file
                try:
                    with open(expediente, "rb") as f:
                        attachments.append({
                            "name": os.path.basename(expediente),
                            "content": f.read()
                        })
                except Exception as e:
                    print(f"Error reading file {expediente}: {e}")
        
        elif expediente.startswith("http"):
             body += f"\n\nLink al expediente: {expediente}"
    
    # 4. Send Email
    try:
        recipients = [r.strip() for r in recipient_email.split(",") if r.strip()]
        send_email_smtp(subject, body, recipients, attachments)
    except Exception as e:
        print(f"SMTP Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error al enviar correo: {str(e)}")

    # 5. Update 'Email' column in source file to 'Enviado'
    # Reuse update logic or copy-paste simplified version
    try:
        file_path = None
        sheet_name = None
        id_col = None
        
        if insurer.lower() == "metlife":
            if type.upper() == "VIDA":
                file_path = METLIFE_PATHS["RENOVACIONES_VIDA"]
                sheet_name = SHEET_NAMES["RENOVACIONES_VIDA"]
                id_col = "POLIZA_ACTUAL"
            elif type.upper() == "GMM":
                file_path = METLIFE_PATHS["RENOVACIONES_GMM"]
                sheet_name = SHEET_NAMES["RENOVACIONES_GMM"]
                id_col = "NPOLIZA"
        elif insurer.lower() == "sura":
            file_path = SURA_PATHS["RENOVACIONES"]
            # Determine actual sheet name for SURA
            if os.path.exists(file_path):
                 xl = pd.ExcelFile(file_path)
                 sheet_name = xl.sheet_names[0]
            else:
                 sheet_name = "Sheet1" # Fallback
            id_col = "POLIZA"
        elif insurer.upper() == "AARCO_AXA":
            file_path = AARCO_PATHS["RENOVACIONES"]
            if os.path.exists(file_path):
                 xl = pd.ExcelFile(file_path)
                 sheet_name = xl.sheet_names[0]
            else:
                 sheet_name = "Sheet1"
            # Updated to new schema
            id_col = "POLIZA"
            
        if file_path and os.path.exists(file_path):
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            if "Email" not in df.columns:
                df["Email"] = None
            
            policy_str = str(policy_number).strip()
            df['__id_str'] = df[id_col].astype(str).str.strip().str.replace('.0', '', regex=False)
            policy_str_clean = policy_str.replace('.0', '')
            
            mask = df['__id_str'] == policy_str_clean
            if mask.any():
                df.loc[mask, "Email"] = "Enviado"
                df = df.drop(columns=['__id_str'])
                with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            else:
                print("Policy not found for updating Email status")

    except Exception as e:
        print(f"Error updating Excel status: {e}")
        # Don't fail the request if email sent but excel update failed? Or warn?
        # User requirement: "whenever the email is sucesfully sent, the value of the column 'Email' should say 'Enviado'"
        

    return {"message": f"Correo enviado a {recipient_email}"}

def clean_aarco(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and normalize AARCO & AXA data.
    New Schema: ['PROMOTORIA', 'AGENTE', 'ASEGURADORA', 'POLIZA', 'RAMO', 'PRODUCTO',
       'CONTRATANTE', 'ASEGURADO', 'INICIO VIGENCIA', 'FIN VIGENCIA',
       'FRECUENCIA PAGO', 'CONDUCTO COBRO', 'PRIMA NETA ANUAL',
       'PRIMA TOTAL ANUAL', 'EXPEDIENTE', 'PROSPECTADOR', 'ESTATUS',
       'Email']
    """
    
    # 0. Datetime Conversion
    # The user mentioned types are datetime64[ns], but reading from Excel might need explicit conversion/parsing
    date_cols = ["INICIO VIGENCIA", "FIN VIGENCIA"]
    for col in date_cols:
        if col in df.columns:
            # First ensure it's datetime, falling back to string parsing if needed
            df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d')
            # Or use generic parser? pd.to_datetime usually smart enough used like this.
            # If they are already datetime objects from Excel, this works.
            
    # 1. Money Conversion
    money_cols = ["PRIMA NETA ANUAL", "PRIMA TOTAL ANUAL"]
    for col in money_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_money)

    requested_cols = [
        "POLIZA", "ASEGURADORA", "PROMOTORIA", "AGENTE", "PROSPECTADOR", "RAMO", "PRODUCTO", 
        "CONTRATANTE", "ASEGURADO", "INICIO VIGENCIA", "FIN VIGENCIA", 
        "PRIMA NETA ANUAL", "EXPEDIENTE", "Email"
    ]
    
    # Ensure all columns exist
    for col in requested_cols:
        if col not in df.columns:
             if col == "Email" and "EMAIL" in df.columns: # Case sensitivity check
                df["Email"] = df["EMAIL"]
             else:
                df[col] = None
    
    # Logic for ESTATUS_DE_RENOVACION (Editable Column) vs ESTATUS (Raw Column)
    # If the file already has ESTATUS_DE_RENOVACION (saved from previous edits), keep it.
    # If not, initialize it as None (or empty string/Default).
    if "ESTATUS_DE_RENOVACION" not in df.columns:
        df["ESTATUS_DE_RENOVACION"] = None

    # We Append it to requested cols to ensure it is returned
    requested_cols.append("ESTATUS_DE_RENOVACION")

    return df[requested_cols]

