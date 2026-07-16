from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional
from pydantic import BaseModel
from database import SessionLocal, Client, User

router = APIRouter(prefix="/clientes", tags=["clientes"])


def normalize_optional_rfc(value: Optional[str]) -> Optional[str]:
    normalized = "".join(str(value or "").strip().upper().split())
    return normalized or None


class ClientModel(BaseModel):
    nombre: str
    rfc: Optional[str] = None
    correo: Optional[str] = None
    telefono: Optional[str] = None

@router.get("/", response_model=List[ClientModel])
async def get_clients():
    db = SessionLocal()
    try:
        clients = db.query(Client).order_by(Client.full_name).all()
        return [
            ClientModel(
                nombre=c.full_name,
                rfc=c.rfc,
                correo=c.email,
                telefono=c.phone
            ) for c in clients
        ]
    except Exception as e:
        print(f"Error fetching clients: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.post("/", response_model=ClientModel)
async def add_client(client: ClientModel):
    db = SessionLocal()
    try:
        client.rfc = normalize_optional_rfc(client.rfc)
        # Check if user exists to prevent foreign key errors
        user = db.query(User).filter(User.id == "usr_pamela").first()
        if not user:
            # Fallback seed user
            user = User(id="usr_pamela", name="Pamela Asmara Alfaro Mendoza", email="pamela.alfaro@taiico.com", role="broker")
            db.add(user)
            db.flush()

        new_client = Client(
            full_name=client.nombre,
            rfc=client.rfc,
            email=client.correo,
            phone=client.telefono,
            responsible_user_id="usr_pamela",
            status="active"
        )
        db.add(new_client)
        db.commit()
        return client
    except Exception as e:
        print(f"Error adding client: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

class UpdateClientRequest(BaseModel):
    original_nombre: str
    client: ClientModel

@router.post("/update")
async def update_client(req: UpdateClientRequest):
    db = SessionLocal()
    try:
        db_client = db.query(Client).filter(Client.full_name == req.original_nombre).first()
        if not db_client:
            raise HTTPException(status_code=404, detail="Client not found")
            
        db_client.full_name = req.client.nombre
        req.client.rfc = normalize_optional_rfc(req.client.rfc)
        db_client.rfc = req.client.rfc
        db_client.email = req.client.correo
        db_client.phone = req.client.telefono
        db.commit()
        return {"success": True, "client": req.client}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error updating client: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

class DeleteClientRequest(BaseModel):
    nombre: str

@router.post("/delete")
async def delete_client(req: DeleteClientRequest):
    db = SessionLocal()
    try:
        db_client = db.query(Client).filter(Client.full_name == req.nombre).first()
        if not db_client:
            raise HTTPException(status_code=404, detail="Client not found")
            
        db.delete(db_client)
        db.commit()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting client: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.get("/search")
async def search_client(name: str):
    db = SessionLocal()
    try:
        # Case insensitive exact match or fallback search
        term = name.strip()
        client = db.query(Client).filter(Client.full_name.ilike(term)).first()
        if client:
            return {"email": client.email}
        return {"email": None}
    except Exception as e:
        print(f"Error searching client: {e}")
        return {"email": None}
    finally:
        db.close()

def upsert_client_internal(nombre: str, correo: str):
    """
    Helper function to add or update a client's email internally.
    Called by Renovaciones module when sending an email with a manual override.
    """
    db = SessionLocal()
    try:
        client = db.query(Client).filter(Client.full_name.ilike(nombre.strip())).first()
        if client:
            print(f"Updating existing client {nombre} with new email {correo}")
            client.email = correo
        else:
            print(f"Auto-adding new client {nombre} with email {correo}")
            # Ensure usr_pamela exists
            user = db.query(User).filter(User.id == "usr_pamela").first()
            if not user:
                user = User(id="usr_pamela", name="Pamela Asmara Alfaro Mendoza", email="pamela.alfaro@taiico.com", role="broker")
                db.add(user)
                db.flush()

            new_client = Client(
                full_name=nombre.strip(),
                email=correo.strip(),
                responsible_user_id="usr_pamela",
                status="active"
            )
            db.add(new_client)
        db.commit()
    except Exception as e:
        print(f"Error in upsert_client_internal: {e}")
        db.rollback()
    finally:
        db.close()
