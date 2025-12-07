from fastapi import APIRouter, HTTPException, Query
import pandas as pd
from config import METLIFE_PATHS, SHEET_NAMES
import numpy as np
from typing import Optional, List
from datetime import datetime, timedelta

router = APIRouter(prefix="/cobranza", tags=["cobranza"])

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

def parse_date(val):
    """
    Parse date to ISO string YYYY-MM-DD.
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

def clean_vida(df: pd.DataFrame) -> pd.DataFrame:
    # Columns to keep: '# de Póliza', 'Producto', 'Conducto de Cobro', 'Fecha de Pago del Recibo', 'Año de Vida Póliza', 'Prima Pagada', 'Comisión Bruto', 'Comisión Neta'
    
    # Normalize columns if needed (strip spaces)
    df.columns = df.columns.str.strip()
    
    # Date conversion
    if 'Fecha de Pago del Recibo' in df.columns:
        df['Fecha de Pago del Recibo'] = df['Fecha de Pago del Recibo'].apply(parse_date)
        
    # Money conversion
    money_cols = ['Prima Pagada', 'Comisión Bruto', 'Comisión Neta']
    for col in money_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_money)

    requested_cols = [
        '# de Póliza', 'Producto', 'Conducto de Cobro', 
        'Fecha de Pago del Recibo', 'Año de Vida Póliza', 
        'Prima Pagada', 'Comisión Bruto', 'Comisión Neta'
    ]
    
    # Ensure columns exist
    for col in requested_cols:
        if col not in df.columns:
            df[col] = None
            
    return df[requested_cols].replace({np.nan: None})

def clean_gmm(df: pd.DataFrame) -> pd.DataFrame:
    # Columns to keep: '# de Póliza', 'Producto', 'Conducto de Cobro', 'Fecha de Pago del Recibo', 'Año de Vida Póliza', 'Estado', 'Prima Pagada', 'Comisión Bruto', 'Comisión Neta', 'IVA Causado'
    
    df.columns = df.columns.str.strip()
    
    # Date conversion
    if 'Fecha de Pago del Recibo' in df.columns:
        df['Fecha de Pago del Recibo'] = df['Fecha de Pago del Recibo'].apply(parse_date)

    # Money conversion
    money_cols = ['Prima Pagada', 'Comisión Bruto', 'Comisión Neta', 'IVA Causado']
    for col in money_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_money)
            
    # Handle 'Estado' mapping if 'Estado' column doesn't exist but 'Estatus Recibo' does
    if 'Estado' not in df.columns and 'Estatus Recibo' in df.columns:
        df['Estado'] = df['Estatus Recibo']

    requested_cols = [
        '# de Póliza', 'Producto', 'Conducto de Cobro', 
        'Fecha de Pago del Recibo', 'Año de Vida Póliza', 
        'Estado', 'Prima Pagada', 'Comisión Bruto', 
        'Comisión Neta', 'IVA Causado'
    ]
    
    for col in requested_cols:
        if col not in df.columns:
            df[col] = None
            
    return df[requested_cols].replace({np.nan: None})

@router.get("/vida")
async def get_cobranza_vida(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD")
):
    try:
        df = pd.read_excel(METLIFE_PATHS["COBRANZA"], sheet_name=SHEET_NAMES["COBRANZA_VIDA"])
        df = clean_vida(df)
        
        if start_date and end_date:
            # Filter by 'Fecha de Pago del Recibo'
            if 'Fecha de Pago del Recibo' in df.columns:
                # Ensure we are comparing strings in ISO format
                mask = (df['Fecha de Pago del Recibo'] >= start_date) & (df['Fecha de Pago del Recibo'] <= end_date)
                df = df[mask]
                
        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gmm")
async def get_cobranza_gmm(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD")
):
    try:
        df = pd.read_excel(METLIFE_PATHS["COBRANZA"], sheet_name=SHEET_NAMES["COBRANZA_GMM"])
        df = clean_gmm(df)
        
        if start_date and end_date:
             if 'Fecha de Pago del Recibo' in df.columns:
                mask = (df['Fecha de Pago del Recibo'] >= start_date) & (df['Fecha de Pago del Recibo'] <= end_date)
                df = df[mask]

        return df.to_dict(orient="records")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
