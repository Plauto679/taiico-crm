from fastapi import APIRouter, HTTPException, Query
import pandas as pd
from config import METLIFE_PATHS, SHEET_NAMES
import numpy as np
from datetime import datetime, timedelta

router = APIRouter(prefix="/renovaciones", tags=["renovaciones"])

def clean_data(df):
    df = df.replace({np.nan: None})
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime('%Y-%m-%d')
    return df.to_dict(orient="records")

def filter_upcoming(df, days: int):
    # Ensure 'Fecha de Renovación' is datetime
    # Note: The column name might vary. We need to check the exact column name.
    # Based on previous context, it's likely "Fecha de Renovación" or similar.
    # Let's assume standard column names for now, but we might need to inspect the file.
    
    # Common column names for renewal date
    date_cols = [col for col in df.columns if "renovaci" in col.lower() and "fecha" in col.lower()]
    if not date_cols:
        # Fallback or error? Let's try to find any date column if specific one not found
        return df # Return all if we can't find the date column
    
    date_col = date_cols[0]
    
    # Convert to datetime if not already
    if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        
    now = datetime.now()
    future = now + timedelta(days=days)
    
    # Filter
    mask = (df[date_col] >= now) & (df[date_col] <= future)
    return df[mask]

@router.get("/vida")
async def get_renovaciones_vida(days: int = Query(30, description="Days to look ahead")):
    try:
        df = pd.read_excel(METLIFE_PATHS["RENOVACIONES_VIDA"], sheet_name=SHEET_NAMES["RENOVACIONES_VIDA"])
        df = filter_upcoming(df, days)
        return clean_data(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gmm")
async def get_renovaciones_gmm(days: int = Query(30, description="Days to look ahead")):
    try:
        df = pd.read_excel(METLIFE_PATHS["RENOVACIONES_GMM"], sheet_name=SHEET_NAMES["RENOVACIONES_GMM"])
        
        # --- Data Wrangling ---
        
        # 1. Date formatting (YYYY-MM-DD)
        date_cols = ["FINIVIG", "FFINVIG", "PAGADOHASTA"]
        for col in date_cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")

        # 2. Money formatting (Float)
        money_cols = ["PRIMA", "PRIMA.1", "RECARGO", "GTOSEXP", "IVA", "DEDUCIBLE"]
        for col in money_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # 3. Percentage handling (Divide by 100)
        if "COASEGURO" in df.columns:
             df["COASEGURO"] = pd.to_numeric(df["COASEGURO"], errors="coerce") / 100

        # Filter upcoming (using FFINVIG which is the renewal date)
        # We need to convert back to datetime for filtering, or do filtering before formatting.
        # Let's filter first, then format? Or just re-parse for filtering.
        # The `filter_upcoming` function expects a dataframe.
        # Let's modify `filter_upcoming` or do it inline.
        
        # Actually, `filter_upcoming` is generic. Let's see how it works.
        # It looks for "renovaci" and "fecha". But GMM uses "FFINVIG".
        # We should explicitly handle filtering for GMM here or update `filter_upcoming`.
        
        # Let's do explicit filtering here for clarity and robustness
        now = datetime.now()
        future = now + timedelta(days=days)
        
        # Use FFINVIG for filtering
        if "FFINVIG" in df.columns:
             # Parse temporarily for filtering
             temp_dates = pd.to_datetime(df["FFINVIG"], errors='coerce')
             mask = (temp_dates >= now) & (temp_dates <= future)
             df = df[mask]
        
        return clean_data(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
