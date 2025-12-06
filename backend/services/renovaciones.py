from fastapi import APIRouter, HTTPException, Query
import pandas as pd
from typing import List, Optional
from datetime import datetime, timedelta
from config import METLIFE_PATHS, SHEET_NAMES
import numpy as np

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

    # 4. Map to Unified Schema
    # Create new columns for the unified schema
    df["poliza"] = df["NPOLIZA"].astype(str)
    df["polizaOrigen"] = df["POLORIG"].astype(str)
    df["contratante"] = df["CONTRATANTE"]
    df["rfcContratante"] = df["RFC"]
    df["fechaInicioVigencia"] = df["FINIVIG"]
    df["fechaFinVigencia"] = df["FFINVIG"]
    df["fechaRenovacion"] = df["FFINVIG"] # Canonical renewal date
    df["nombreAsegurado"] = df["NOMBREL"]
    df["conductoCobro"] = df["CONDCOB"]
    df["prima"] = df["PRIMA.1"] # Assuming PRIMA.1 is the main premium
    df["iva"] = df["IVA"]
    df["pagadoHasta"] = df["PAGADOHASTA"]
    df["deducible"] = df["DEDUCIBLE"]
    df["coaseguro"] = df["COASEGURO"]
    df["ramo"] = "GMM"
    df["estatus"] = df["ESTATUS"].astype(str)
    df["agente"] = df["NOMBRE"] # Agent Name

    # Select only unified columns
    unified_cols = [
        "poliza", "polizaOrigen", "contratante", "rfcContratante",
        "fechaInicioVigencia", "fechaFinVigencia", "fechaRenovacion",
        "nombreAsegurado", "conductoCobro", "prima", "iva",
        "pagadoHasta", "deducible", "coaseguro", "ramo", "estatus", "agente"
    ]
    # Ensure all columns exist
    for col in unified_cols:
        if col not in df.columns:
            df[col] = None
            
    return df[unified_cols]

def clean_vida(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and normalize Metlife Vida data.
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

    # 3. Map to Unified Schema
    df["poliza"] = df["POLIZA_ACTUAL"].astype(str)
    df["polizaOrigen"] = df["POLIZA_ORIGEN"].astype(str)
    df["contratante"] = df["CONTRATANTE"]
    df["rfcContratante"] = df["RFC_CONTRATANTE"]
    df["fechaInicioVigencia"] = df["INI_VIG"]
    df["fechaFinVigencia"] = df["FIN_VIG"]
    df["fechaRenovacion"] = df["FIN_VIG"] # Canonical renewal date
    df["producto"] = df["PDESC"]
    df["estatus"] = df["ESTATUS_POL"]
    df["formaPago"] = df["FORMA_PAGO"]
    df["conductoCobro"] = df["CONDUCTO_COBRO"]
    df["agente"] = df["NOM_AGENTE"]
    df["prima"] = df["PRIMA_ANUAL"]
    df["pagadoHasta"] = df["PAGADO_HASTA"]
    df["ramo"] = "VIDA"

    unified_cols = [
        "poliza", "polizaOrigen", "contratante", "rfcContratante",
        "fechaInicioVigencia", "fechaFinVigencia", "fechaRenovacion",
        "producto", "estatus", "formaPago", "conductoCobro",
        "agente", "prima", "pagadoHasta", "ramo"
    ]
    
    # Ensure all columns exist
    for col in unified_cols:
        if col not in df.columns:
            df[col] = None

    return df[unified_cols]

@router.get("/upcoming")
async def get_upcoming_renewals(
    days: int = Query(30, description="Days to look ahead"),
    insurer: str = Query("Metlife", description="Insurer name"),
    type: str = Query("ALL", description="Policy type: ALL, VIDA, GMM")
):
    """
    Get upcoming renewals for a specific insurer and type.
    """
    results = []
    
    if insurer.lower() != "metlife":
        # Placeholder for other insurers
        return []

    # Calculate date range
    today = datetime.now()
    future = today + timedelta(days=days)
    today_str = today.strftime("%Y-%m-%d")
    future_str = future.strftime("%Y-%m-%d")

    # Load and process VIDA
    if type.upper() in ["ALL", "VIDA"]:
        try:
            df_vida = pd.read_excel(METLIFE_PATHS["RENOVACIONES_VIDA"], sheet_name=SHEET_NAMES["RENOVACIONES_VIDA"])
            df_vida = clean_vida(df_vida)
            
            # Filter by date
            # Convert back to datetime for comparison, or compare strings (ISO format allows string comparison)
            # String comparison works for ISO dates: "2023-01-01" < "2023-02-01"
            mask = (df_vida["fechaRenovacion"] >= today_str) & (df_vida["fechaRenovacion"] <= future_str)
            df_vida = df_vida[mask]
            
            results.extend(clean_data(df_vida))
        except Exception as e:
            print(f"Error loading Vida: {e}")

    # Load and process GMM
    if type.upper() in ["ALL", "GMM"]:
        try:
            df_gmm = pd.read_excel(METLIFE_PATHS["RENOVACIONES_GMM"], sheet_name=SHEET_NAMES["RENOVACIONES_GMM"])
            df_gmm = clean_gmm(df_gmm)
            
            # Filter by date
            mask = (df_gmm["fechaRenovacion"] >= today_str) & (df_gmm["fechaRenovacion"] <= future_str)
            df_gmm = df_gmm[mask]
            
            results.extend(clean_data(df_gmm))
        except Exception as e:
             print(f"Error loading GMM: {e}")

    return results

# Keep legacy endpoints for backward compatibility if needed, but redirecting logic
@router.get("/vida")
async def get_renovaciones_vida(days: int = 30):
    return await get_upcoming_renewals(days=days, insurer="Metlife", type="VIDA")

@router.get("/gmm")
async def get_renovaciones_gmm(days: int = 30):
    return await get_upcoming_renewals(days=days, insurer="Metlife", type="GMM")
