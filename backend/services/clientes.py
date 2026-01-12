from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional
import pandas as pd
import os
from pydantic import BaseModel
from config import CLIENT_EMAILS_PATH

router = APIRouter(prefix="/clientes", tags=["clientes"])

class Client(BaseModel):
    nombre: str
    correo: Optional[str] = None
    telefono: Optional[str] = None

@router.get("/", response_model=List[Client])
async def get_clients():
    try:
        if not os.path.exists(CLIENT_EMAILS_PATH):
            return []
        
        df = pd.read_excel(CLIENT_EMAILS_PATH)
        
        # Normalize columns
        # Expected: ['Clientes', 'Mail', 'Telefono']
        # Map to: nombre, correo, telefono
        
        clients = []
        for _, row in df.iterrows():
            cliente = row.get('Clientes')
            
            # Skip empty rows
            if pd.isna(cliente):
                continue
                
            mail = row.get('Mail')
            tel = row.get('Telefono')
            
            clients.append(Client(
                nombre=str(cliente).strip(),
                correo=str(mail).strip() if pd.notna(mail) else None,
                telefono=str(tel).strip() if pd.notna(tel) else None
            ))
            
        return clients
        
    except Exception as e:
        print(f"Error reading clients: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=Client)
async def add_client(client: Client):
    try:
        if not os.path.exists(CLIENT_EMAILS_PATH):
            # Create new file if doesn't exist? Or error?
            # Assuming file structure usually exists, but we can create empty df
             df = pd.DataFrame(columns=['Clientes', 'Mail', 'Telefono'])
        else:
             df = pd.read_excel(CLIENT_EMAILS_PATH)
        
        # Check if client already exists? (Optional, but good practice)
        # For now, just append as requested.
        
        new_row = {
            'Clientes': client.nombre,
            'Mail': client.correo,
            'Telefono': client.telefono
        }
        
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        
        # Save
        with pd.ExcelWriter(CLIENT_EMAILS_PATH, engine='openpyxl', mode='w') as writer:
             df.to_excel(writer, index=False)
             
        return client
        
    except Exception as e:
        print(f"Error adding client: {e}")
        raise HTTPException(status_code=500, detail=str(e))
