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
            
            # Handle Phone Number Formatting
            if pd.notna(tel):
                try:
                    # Convert to float first to handle strings "123.0", then to int
                    tel_clean = int(float(tel))
                    tel_str = str(tel_clean)
                except ValueError:
                    tel_str = str(tel).strip()
            else:
                tel_str = None

            clients.append(Client(
                nombre=str(cliente).strip(),
                correo=str(mail).strip() if pd.notna(mail) else None,
                telefono=tel_str
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

class UpdateClientRequest(BaseModel):
    original_nombre: str
    client: Client

@router.post("/update")
async def update_client(req: UpdateClientRequest):
    try:
        if not os.path.exists(CLIENT_EMAILS_PATH):
            raise HTTPException(status_code=404, detail="Database file not found")
            
        df = pd.read_excel(CLIENT_EMAILS_PATH)
        
        # Find the index of the client to update
        # We assume 'Clientes' column is the identifier and is unique enough for now
        mask = df['Clientes'].astype(str).str.strip() == req.original_nombre
        
        if not mask.any():
            raise HTTPException(status_code=404, detail="Client not found")
            
        # Update values
        idx = df[mask].index[0]
        df.at[idx, 'Clientes'] = req.client.nombre
        df.at[idx, 'Mail'] = req.client.correo
        df.at[idx, 'Telefono'] = req.client.telefono
        
        # Save
        with pd.ExcelWriter(CLIENT_EMAILS_PATH, engine='openpyxl', mode='w') as writer:
             df.to_excel(writer, index=False)
             
        return {"success": True, "client": req.client}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating client: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class DeleteClientRequest(BaseModel):
    nombre: str

@router.post("/delete")
async def delete_client(req: DeleteClientRequest):
    try:
        if not os.path.exists(CLIENT_EMAILS_PATH):
             raise HTTPException(status_code=404, detail="Database file not found")
            
        df = pd.read_excel(CLIENT_EMAILS_PATH)
        
        initial_len = len(df)
        # Filter out the client
        df = df[df['Clientes'].astype(str).str.strip() != req.nombre]
        
        if len(df) == initial_len:
             raise HTTPException(status_code=404, detail="Client not found")

        # Save
        with pd.ExcelWriter(CLIENT_EMAILS_PATH, engine='openpyxl', mode='w') as writer:
             df.to_excel(writer, index=False)
             
        return {"success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting client: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search")
async def search_client(name: str):
    try:
        if not os.path.exists(CLIENT_EMAILS_PATH):
            return {"email": None}
            
        df = pd.read_excel(CLIENT_EMAILS_PATH)
        
        # Normalize logic: similar to Renovaciones
        def normalize_name(val):
            if not val: return ""
            return " ".join(str(val).strip().upper().split())
            
        target_norm = normalize_name(name)
        df['__norm'] = df['Clientes'].apply(normalize_name)
        
        match = df[df['__norm'] == target_norm]
        
        if not match.empty and 'Mail' in match.columns:
            val = match.iloc[0]['Mail']
            if pd.notna(val) and str(val).strip():
                return {"email": str(val).strip()}
                
        return {"email": None}
        
    except Exception as e:
        print(f"Error searching client: {e}")
        return {"email": None}

def upsert_client_internal(nombre: str, correo: str):
# ... existing code ...
    """
    Helper function to add or update a client's email internally.
    Called by Renovaciones module when sending an email with a manual override.
    """
    try:
        if not os.path.exists(CLIENT_EMAILS_PATH):
             # Create new
             df = pd.DataFrame(columns=['Clientes', 'Mail', 'Telefono'])
        else:
             df = pd.read_excel(CLIENT_EMAILS_PATH)
        
        # Check if client exists
        # Name matching logic: strip and exact match?
        mask = df['Clientes'].astype(str).str.strip().str.lower() == nombre.strip().lower()
        
        if mask.any():
            # Update existing
            idx = df[mask].index[0]
            print(f"Updating existing client {nombre} with new email {correo}")
            df.at[idx, 'Mail'] = correo
            # Retain phone? Yes, we just update mail.
        else:
            # Add new
            print(f"Auto-adding new client {nombre} with email {correo}")
            new_row = {
                'Clientes': nombre.strip(),
                'Mail': correo.strip(),
                'Telefono': None
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            
        # Save
        with pd.ExcelWriter(CLIENT_EMAILS_PATH, engine='openpyxl', mode='w') as writer:
             df.to_excel(writer, index=False)
             
    except Exception as e:
        print(f"Error in upsert_client_internal: {e}")
        # Build resiliently: don't crash the email sending if this fails, just log it.
