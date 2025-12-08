from fastapi import APIRouter, HTTPException, Query, Body
import pandas as pd
from typing import List, Optional
from datetime import datetime, timedelta
from config import METLIFE_PATHS, SURA_PATHS, SHEET_NAMES
import numpy as np
import os

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
        "COASEGURO", "ESTATUS_DE_RENOVACION"
    ]
    
    # Ensure all columns exist
    for col in requested_cols:
        if col not in df.columns:
            df[col] = None
            
    return df[requested_cols]

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
        "PRIMA_ANUAL", "PRIMA_MODAL", "PAGADO_HASTA",
        "ESTATUS_DE_RENOVACION"
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
        "ESTATUS_DE_RENOVACION"
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

    return results

@router.post("/update")
async def update_renewal_status(
    insurer: str = Body(..., embed=True),
    type: str = Body(..., embed=True),
    policy_number: str = Body(..., embed=True),
    new_status: str = Body(..., embed=True)
):
    """
    Update the ESTATUS_DE_RENOVACION for a specific policy.
    """
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
        sheet_name = 0 # Default sheet for SURA
        id_col = "POLIZA"
        
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        # Read the Excel file
        # Note: We read all sheets to preserve them if we write back, 
        # but for simplicity and safety with pandas, we might just process the target sheet.
        # However, to avoid deleting other sheets, we should try to use ExcelWriter in append/replace mode if supported,
        # or read all, update one, write all.
        
        # Reading the specific sheet to update
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        
        # Ensure column exists
        if "ESTATUS_DE_RENOVACION" not in df.columns:
            df["ESTATUS_DE_RENOVACION"] = None
            
        # Find and update the row
        # Convert ID column to string for comparison to be safe
        df[id_col] = df[id_col].astype(str)
        
        # Check if policy exists
        if policy_number not in df[id_col].values:
             raise HTTPException(status_code=404, detail="Policy not found")
             
        # Update status
        mask = df[id_col] == str(policy_number)
        df.loc[mask, "ESTATUS_DE_RENOVACION"] = new_status
        
        # Save back to Excel
        # Using ExcelWriter with if_sheet_exists='replace' requires pandas >= 1.3 and engine='openpyxl'
        # We'll try to preserve other sheets by reading them if necessary, 
        # but for now let's assume single sheet or main sheet update is okay if we use mode='a'
        
        with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
            df.to_excel(writer, sheet_name=sheet_name if isinstance(sheet_name, str) else "Sheet1", index=False)
            
        return {"message": "Status updated successfully"}

    except Exception as e:
        print(f"Error updating status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Keep legacy endpoints for backward compatibility if needed, but redirecting logic
@router.get("/vida")
async def get_renovaciones_vida(days: int = 30):
    return await get_upcoming_renewals(days=days, insurer="Metlife", type="VIDA")

@router.get("/gmm")
async def get_renovaciones_gmm(days: int = 30):
    return await get_upcoming_renewals(days=days, insurer="Metlife", type="GMM")
