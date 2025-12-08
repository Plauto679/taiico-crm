from fastapi import APIRouter, HTTPException, Query
import pandas as pd
from config import METLIFE_PATHS, SURA_PATHS, SHEET_NAMES
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

def clean_sura_cobranza(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and normalize SURA Cobranza data.
    """
    # Columns: 'Daños/Vida', 'Grupo', 'Oficina', 'Ramo', 'Póliza', 'Contratante', 'Clave Agente', 'Tipo de Cambio', '# Recibo', 'Serie de Recibo', 'Prima Total', 'Prima Neta', '% Comisión pagado', 'Comisión de derecho', 'Monto Comisión Neta', 'Total Comisión pagado', '# Liquidación', '# Comprobante', 'Fecha aplicación de la póliza'
    
    df.columns = df.columns.str.strip()
    
    # Date conversion
    if 'Fecha aplicación de la póliza' in df.columns:
        df['Fecha aplicación de la póliza'] = df['Fecha aplicación de la póliza'].apply(parse_date)
        
    # Money conversion
    money_cols = ['Prima Total', 'Prima Neta', 'Monto Comisión Neta', 'Total Comisión pagado']
    for col in money_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_money)
            
    # Percentage conversion
    if '% Comisión pagado' in df.columns:
        df['% Comisión pagado'] = pd.to_numeric(df['% Comisión pagado'], errors='coerce') / 100.0
        
    # Select all columns as requested (or specific ones? User listed all columns and types, implying we keep them)
    # User said: "To this table in order to display it properly we wil wrangle it in the backend"
    # I will keep all columns listed by the user.
    requested_cols = [
        'Daños/Vida', 'Grupo', 'Oficina', 'Ramo', 'Póliza', 'Contratante',
        'Clave Agente', 'Tipo de Cambio', '# Recibo', 'Serie de Recibo',
        'Prima Total', 'Prima Neta', '% Comisión pagado', 'Comisión de derecho',
        'Monto Comisión Neta', 'Total Comisión pagado', '# Liquidación',
        '# Comprobante', 'Fecha aplicación de la póliza'
    ]
    
    for col in requested_cols:
        if col not in df.columns:
            df[col] = None
            
    return df[requested_cols].replace({np.nan: None})

@router.get("/vida")
async def get_cobranza_vida(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    insurer: str = Query("Metlife", description="Insurer name")
):
    try:
        if insurer.lower() == "metlife":
            df = pd.read_excel(METLIFE_PATHS["COBRANZA"], sheet_name=SHEET_NAMES["COBRANZA_VIDA"])
            df = clean_vida(df)
            
            if start_date and end_date:
                if 'Fecha de Pago del Recibo' in df.columns:
                    mask = (df['Fecha de Pago del Recibo'] >= start_date) & (df['Fecha de Pago del Recibo'] <= end_date)
                    df = df[mask]
            return df.to_dict(orient="records")
        elif insurer.lower() == "sura":
            # SURA doesn't have separate Vida/GMM endpoints usually, but if frontend calls /vida for SURA, 
            # we might return the whole list or filter by 'Daños/Vida' if applicable.
            # User provided one file for SURA Cobranza.
            # Let's handle SURA in a generic way or return empty if strict.
            # For now, let's assume SURA calls might go to a new endpoint or we reuse this one.
            # Given the frontend structure, it's better to have a generic endpoint or handle it here.
            # Let's return the SURA data here if requested, or maybe filter by 'Vida' if that column exists?
            # The column is 'Daños/Vida'.
            df = pd.read_excel(SURA_PATHS["COBRANZA"], sheet_name="Cobranza")
            df = clean_sura_cobranza(df)
            
            if start_date and end_date:
                if 'Fecha aplicación de la póliza' in df.columns:
                    mask = (df['Fecha aplicación de la póliza'] >= start_date) & (df['Fecha aplicación de la póliza'] <= end_date)
                    df = df[mask]
            
            # Optional: Filter by 'Daños/Vida' if we want to mimic the endpoint structure
            # But SURA might be mixed. Let's return all for now or filter if 'Vida' is in the column.
            return df.to_dict(orient="records")
            
        return []
    except Exception as e:
        print(f"Error loading Cobranza Vida: {e}")
        return []

@router.get("/gmm")
async def get_cobranza_gmm(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    insurer: str = Query("Metlife", description="Insurer name")
):
    try:
        if insurer.lower() == "metlife":
            df = pd.read_excel(METLIFE_PATHS["COBRANZA"], sheet_name=SHEET_NAMES["COBRANZA_GMM"])
            df = clean_gmm(df)
            
            if start_date and end_date:
                 if 'Fecha de Pago del Recibo' in df.columns:
                    mask = (df['Fecha de Pago del Recibo'] >= start_date) & (df['Fecha de Pago del Recibo'] <= end_date)
                    df = df[mask]
            return df.to_dict(orient="records")
        elif insurer.lower() == "sura":
             # Same logic as above, return SURA data (maybe filtered)
             # Since SURA is one table, we can just return it here too, or return empty if we want to force 'Vida' tab usage.
             # User didn't specify splitting SURA.
             # Let's return it here too for now.
            df = pd.read_excel(SURA_PATHS["COBRANZA"], sheet_name="Cobranza")
            df = clean_sura_cobranza(df)
            
            if start_date and end_date:
                if 'Fecha aplicación de la póliza' in df.columns:
                    mask = (df['Fecha aplicación de la póliza'] >= start_date) & (df['Fecha aplicación de la póliza'] <= end_date)
                    df = df[mask]
            return df.to_dict(orient="records")

        return []
    except Exception as e:
        print(f"Error loading Cobranza GMM: {e}")
        return []
