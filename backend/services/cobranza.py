from fastapi import APIRouter, HTTPException
import pandas as pd
from config import METLIFE_PATHS, SHEET_NAMES
import numpy as np

router = APIRouter(prefix="/cobranza", tags=["cobranza"])

def clean_data(df):
    # Replace NaN with None (which becomes null in JSON)
    df = df.replace({np.nan: None})
    
    # Convert dates to ISO string if they are datetime objects
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime('%Y-%m-%d')
            
    return df.to_dict(orient="records")

@router.get("/vida")
async def get_cobranza_vida():
    try:
        df = pd.read_excel(METLIFE_PATHS["COBRANZA"], sheet_name=SHEET_NAMES["COBRANZA_VIDA"])
        return clean_data(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/gmm")
async def get_cobranza_gmm():
    try:
        df = pd.read_excel(METLIFE_PATHS["COBRANZA"], sheet_name=SHEET_NAMES["COBRANZA_GMM"])
        return clean_data(df)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
