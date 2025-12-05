from fastapi import APIRouter, HTTPException, Query
import pandas as pd
from config import METLIFE_PATHS, SHEET_NAMES
import numpy as np

router = APIRouter(prefix="/cartera", tags=["cartera"])

def clean_data(df):
    df = df.replace({np.nan: None})
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime('%Y-%m-%d')
    return df.to_dict(orient="records")

def search_dataframe(df, query: str):
    if not query:
        return df
    
    query = query.lower()
    
    # Search in all string columns
    mask = np.column_stack([df[col].astype(str).str.lower().str.contains(query, na=False) for col in df.columns])
    return df.loc[mask.any(axis=1)]

@router.get("/search")
async def search_cartera(query: str = Query(..., min_length=1)):
    try:
        # Load both Vida and GMM
        df_vida = pd.read_excel(METLIFE_PATHS["CARTERA"], sheet_name=SHEET_NAMES["CARTERA_VIDA"])
        df_vida['Tipo'] = 'VIDA'
        
        df_gmm = pd.read_excel(METLIFE_PATHS["CARTERA"], sheet_name=SHEET_NAMES["CARTERA_GMM"])
        df_gmm['Tipo'] = 'GMM'
        
        # Combine
        df = pd.concat([df_vida, df_gmm], ignore_index=True)
        
        # Search
        results = search_dataframe(df, query)
        
        return clean_data(results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
