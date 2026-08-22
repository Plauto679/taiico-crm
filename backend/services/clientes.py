from __future__ import annotations

from datetime import datetime
import re
from typing import List, Optional
from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError

from database import (
    Claim,
    Client,
    Conversation,
    Document,
    Payment,
    PaymentEvidenceRecord,
    Policy,
    Renewal,
    SessionLocal,
    User,
)
from services.client_identity_matching import build_identity_candidates
from services.client_merge import merge_duplicate_client
from services.client_folders import (
    build_client_folder_drive_service,
    client_folders_parent_id,
    list_folder_children,
    normalize_rfc,
    valid_client_rfc,
)
from services.client_registry import build_client_registry_audit


router = APIRouter(prefix="/clientes", tags=["clientes"])


class ClientModel(BaseModel):
    id: Optional[str] = None
    nombre: str
    rfc: Optional[str] = None
    correo: Optional[str] = None
    telefono: Optional[str] = None
    estado_identidad: str = "prospect"
    expediente_id: Optional[str] = None
    expediente_url: Optional[str] = None
    expediente_nombre: Optional[str] = None
    expediente_verificado: Optional[str] = None


class UpdateClientRequest(BaseModel):
    client: ClientModel
    client_id: Optional[str] = None
    original_nombre: Optional[str] = None


class DeleteClientRequest(BaseModel):
    client_id: Optional[str] = None
    nombre: Optional[str] = None


class MergeClientsRequest(BaseModel):
    canonical_id: str
    duplicate_ids: List[str]


def _optional_text(value: object) -> Optional[str]:
    normalized = " ".join(str(value or "").strip().split())
    return normalized or None


def normalize_optional_rfc(value: Optional[str]) -> Optional[str]:
    normalized = normalize_rfc(value)
    return normalized or None


def _validated_rfc(value: Optional[str]) -> Optional[str]:
    rfc = normalize_optional_rfc(value)
    if rfc and not valid_client_rfc(rfc):
        raise HTTPException(
            status_code=422,
            detail="El RFC debe tener un formato válido de persona física o moral.",
        )
    return rfc


def _drive_folder_id(value: Optional[str]) -> Optional[str]:
    text = _optional_text(value)
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.netloc and parsed.netloc not in {"drive.google.com", "www.drive.google.com"}:
        raise HTTPException(status_code=422, detail="El expediente debe ser una liga de Google Drive.")
    query_id = parse_qs(parsed.query).get("id", [None])[0]
    folder_match = re.search(r"/folders/([^/?#]+)", parsed.path)
    folder_id = query_id or (folder_match.group(1) if folder_match else None)
    if not folder_id or not re.fullmatch(r"[A-Za-z0-9_-]{10,}", folder_id):
        raise HTTPException(status_code=422, detail="No fue posible identificar la carpeta en la liga de Drive.")
    return folder_id


def _assert_unique_drive_folder(db, folder_id: Optional[str], *, excluding_id: Optional[str] = None) -> None:
    if not folder_id:
        return
    query = db.query(Client).filter(
        Client.drive_folder_id == folder_id,
        Client.status != "inactive",
    )
    if excluding_id:
        query = query.filter(Client.id != excluding_id)
    duplicate = query.first()
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"Esa carpeta ya está vinculada al cliente {duplicate.full_name}.",
        )


def _serialize_client(client: Client) -> ClientModel:
    return ClientModel(
        id=client.id,
        nombre=client.full_name,
        rfc=client.rfc,
        correo=client.email,
        telefono=client.phone,
        estado_identidad=client.identity_status,
        expediente_id=client.drive_folder_id,
        expediente_url=client.drive_folder_url,
        expediente_nombre=client.drive_folder_name,
        expediente_verificado=(
            client.drive_verified_at.isoformat() if client.drive_verified_at else None
        ),
    )


def _audit_client_payload(client: Client) -> dict:
    return {
        "id": client.id,
        "nombre": client.full_name,
        "rfc": client.rfc,
        "expediente_id": client.drive_folder_id,
    }


def _ensure_default_owner(db) -> str:
    user = db.query(User).filter(User.id == "usr_pamela").first()
    if not user:
        user = User(
            id="usr_pamela",
            name="Pamela Asmara Alfaro Mendoza",
            email="pamela.alfaro@taiico.com",
            role="broker",
        )
        db.add(user)
        db.flush()
    return user.id


def _assert_unique_rfc(db, rfc: Optional[str], *, excluding_id: Optional[str] = None) -> None:
    if not rfc:
        return
    query = db.query(Client).filter(func.upper(func.trim(Client.rfc)) == rfc)
    if excluding_id:
        query = query.filter(Client.id != excluding_id)
    duplicate = query.first()
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=(
                f"El RFC {rfc} ya pertenece a {duplicate.full_name}. "
                "Selecciona ese cliente en lugar de crear otro expediente."
            ),
        )


def _client_query(db, client_id: Optional[str], name: Optional[str]):
    if client_id:
        return db.query(Client).filter(Client.id == client_id).first()
    if name:
        return db.query(Client).filter(Client.full_name == name).first()
    return None


def _load_audit(db, *, detail_limit: int = 200) -> dict:
    clients = (
        db.query(Client)
        .filter(Client.status != "inactive")
        .order_by(Client.full_name)
        .all()
    )
    service = build_client_folder_drive_service()
    folders = list_folder_children(service, client_folders_parent_id())
    return build_client_registry_audit(
        [_audit_client_payload(client) for client in clients],
        folders,
        detail_limit=detail_limit,
    )


def _relationship_counts(db) -> dict[str, dict[str, int]]:
    models = {
        "pólizas": Policy,
        "pagos": Payment,
        "renovaciones": Renewal,
        "siniestros": Claim,
        "documentos": Document,
        "conversaciones": Conversation,
        "evidencias de pago": PaymentEvidenceRecord,
    }
    result: dict[str, dict[str, int]] = {}
    for label, model in models.items():
        result[label] = {
            str(client_id): int(count)
            for client_id, count in (
                db.query(model.client_id, func.count(model.id))
                .filter(model.client_id.isnot(None))
                .group_by(model.client_id)
                .all()
            )
        }
    return result


@router.get("/", response_model=List[ClientModel])
def get_clients():
    db = SessionLocal()
    try:
        clients = (
            db.query(Client)
            .filter(Client.status != "inactive")
            .order_by(Client.full_name)
            .all()
        )
        return [_serialize_client(client) for client in clients]
    finally:
        db.close()


@router.post("/", response_model=ClientModel)
def add_client(client: ClientModel):
    db = SessionLocal()
    try:
        name = _optional_text(client.nombre)
        if not name:
            raise HTTPException(status_code=422, detail="El nombre del cliente es obligatorio.")
        rfc = _validated_rfc(client.rfc)
        _assert_unique_rfc(db, rfc)
        new_client = Client(
            full_name=name,
            rfc=rfc,
            email=_optional_text(client.correo),
            phone=_optional_text(client.telefono),
            responsible_user_id=_ensure_default_owner(db),
            status="active",
            identity_status="identified" if rfc else "prospect",
        )
        db.add(new_client)
        db.commit()
        db.refresh(new_client)
        return _serialize_client(new_client)
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        db.close()


@router.post("/update")
def update_client(req: UpdateClientRequest):
    db = SessionLocal()
    try:
        db_client = _client_query(db, req.client_id or req.client.id, req.original_nombre)
        if not db_client:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        name = _optional_text(req.client.nombre)
        if not name:
            raise HTTPException(status_code=422, detail="El nombre del cliente es obligatorio.")
        rfc = _validated_rfc(req.client.rfc)
        _assert_unique_rfc(db, rfc, excluding_id=db_client.id)
        folder_provided = "expediente_url" in req.client.model_fields_set
        folder_id = _drive_folder_id(req.client.expediente_url) if folder_provided else None
        if folder_provided:
            _assert_unique_drive_folder(db, folder_id, excluding_id=db_client.id)
        previous_rfc = normalize_optional_rfc(db_client.rfc)
        db_client.full_name = name
        db_client.rfc = rfc
        db_client.email = _optional_text(req.client.correo)
        db_client.phone = _optional_text(req.client.telefono)
        db_client.identity_status = "identified" if rfc else "prospect"
        if previous_rfc != rfc:
            db_client.drive_folder_id = None
            db_client.drive_folder_url = None
            db_client.drive_folder_name = None
            db_client.drive_verified_at = None
        if folder_provided and folder_id:
            db_client.drive_folder_id = folder_id
            db_client.drive_folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
            db_client.drive_verified_at = datetime.utcnow()
        elif folder_provided:
            db_client.drive_folder_id = None
            db_client.drive_folder_url = None
            db_client.drive_folder_name = None
            db_client.drive_verified_at = None
        db.commit()
        db.refresh(db_client)
        return {"success": True, "client": _serialize_client(db_client)}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        db.close()


@router.post("/delete")
def delete_client(req: DeleteClientRequest):
    db = SessionLocal()
    try:
        db_client = _client_query(db, req.client_id, req.nombre)
        if not db_client:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        if db_client.identity_status != "prospect":
            raise HTTPException(
                status_code=409,
                detail="Solo se pueden eliminar prospectos. Los clientes identificados deben conservar su historial.",
            )
        linked_records = {
            "pólizas": len(db_client.policies),
            "pagos": len(db_client.payments),
            "renovaciones": len(db_client.renewals),
            "siniestros": len(db_client.claims),
            "documentos": len(db_client.documents),
            "conversaciones": len(db_client.conversations),
            "evidencias de pago": db.query(PaymentEvidenceRecord)
            .filter(PaymentEvidenceRecord.client_id == db_client.id)
            .count(),
        }
        linked_records = {label: count for label, count in linked_records.items() if count}

        # A client with operational history must remain in the database so its
        # policies and transactions keep a valid owner.  Hiding it from the
        # master registry is the safe equivalent of deletion in that case.
        if linked_records:
            db_client.status = "inactive"
            result = "archived"
        else:
            db.delete(db_client)
            result = "deleted"
        db.commit()
        return {
            "success": True,
            "result": result,
            "linked_records": linked_records,
        }
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "El cliente tiene información relacionada y no puede eliminarse físicamente. "
                "Actualiza la página e inténtalo nuevamente para archivarlo."
            ),
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        db.close()


@router.get("/search")
def search_client(name: str):
    db = SessionLocal()
    try:
        term = name.strip()
        normalized_rfc = normalize_rfc(term)
        client = (
            db.query(Client)
            .filter(
                Client.status != "inactive",
                or_(
                    Client.full_name.ilike(term),
                    func.upper(func.trim(Client.rfc)) == normalized_rfc,
                )
            )
            .first()
        )
        return {
            "id": client.id if client else None,
            "email": client.email if client else None,
            "rfc": client.rfc if client else None,
            "expediente_url": client.drive_folder_url if client else None,
        }
    finally:
        db.close()


@router.get("/registry-audit")
def client_registry_audit(detail_limit: int = Query(default=200, ge=10, le=1000)):
    db = SessionLocal()
    try:
        audit = _load_audit(db, detail_limit=detail_limit)
        audit.pop("safe_link_updates", None)
        audit["drive_folder_url"] = (
            f"https://drive.google.com/drive/folders/{client_folders_parent_id()}"
        )
        return audit
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No fue posible auditar los expedientes: {exc}") from exc
    finally:
        db.close()


@router.get("/identity-candidates")
def client_identity_candidates(limit: int = Query(default=200, ge=1, le=1000)):
    db = SessionLocal()
    try:
        clients = (
            db.query(Client)
            .filter(Client.status != "inactive")
            .order_by(Client.full_name)
            .all()
        )
        candidates = build_identity_candidates(
            [
                {
                    "id": client.id,
                    "name": client.full_name,
                    "rfc": client.rfc,
                    "email": client.email,
                    "phone": client.phone,
                    "identity_status": client.identity_status,
                    "status": client.status,
                    "drive_folder_url": client.drive_folder_url,
                }
                for client in clients
            ],
            _relationship_counts(db),
        )
        return {
            "groups": candidates[:limit],
            "total_groups": len(candidates),
            "truncated": len(candidates) > limit,
        }
    finally:
        db.close()


@router.post("/merge")
def merge_clients(req: MergeClientsRequest):
    duplicate_ids = list(dict.fromkeys(req.duplicate_ids))
    if not duplicate_ids:
        raise HTTPException(status_code=422, detail="Selecciona al menos un registro duplicado.")
    if req.canonical_id in duplicate_ids:
        raise HTTPException(status_code=422, detail="El cliente maestro no puede estar entre los duplicados.")

    db = SessionLocal()
    try:
        canonical = (
            db.query(Client)
            .filter(Client.id == req.canonical_id, Client.status != "inactive")
            .first()
        )
        if not canonical:
            raise HTTPException(status_code=404, detail="Cliente maestro no encontrado.")
        canonical_rfc = _validated_rfc(canonical.rfc)
        if not canonical_rfc:
            raise HTTPException(
                status_code=409,
                detail="Asigna un RFC válido al cliente maestro antes de homologar registros.",
            )

        results = []
        for duplicate_id in duplicate_ids:
            duplicate = (
                db.query(Client)
                .filter(Client.id == duplicate_id, Client.status != "inactive")
                .first()
            )
            if not duplicate:
                raise HTTPException(status_code=404, detail=f"No se encontró el duplicado {duplicate_id}.")
            duplicate_rfc = normalize_optional_rfc(duplicate.rfc)
            if duplicate_rfc and duplicate_rfc != canonical_rfc:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"{duplicate.full_name} tiene el RFC {duplicate_rfc}, distinto del RFC "
                        f"{canonical_rfc} del cliente maestro. Requiere revisión manual."
                    ),
                )
            results.append(
                merge_duplicate_client(
                    db,
                    canonical_id=req.canonical_id,
                    duplicate_id=duplicate_id,
                )
            )
        db.commit()
        return {
            "success": True,
            "canonical_id": req.canonical_id,
            "canonical_rfc": canonical_rfc,
            "merged_count": len(results),
            "results": results,
        }
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"No fue posible homologar porque existen relaciones incompatibles: {exc.orig}",
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"No fue posible homologar los clientes: {exc}") from exc
    finally:
        db.close()


@router.post("/sync-expedientes")
def sync_client_folder_links():
    db = SessionLocal()
    try:
        audit = _load_audit(db, detail_limit=1000)
        linked = []
        verified_at = datetime.utcnow()
        for mapping in audit["safe_link_updates"]:
            client = db.query(Client).filter(Client.id == mapping["client"]["id"]).first()
            if not client:
                continue
            folder = mapping["folder"]
            client.drive_folder_id = folder["id"]
            client.drive_folder_url = folder["url"]
            client.drive_folder_name = folder["name"]
            client.drive_verified_at = verified_at
            client.identity_status = "identified"
            linked.append({"client_id": client.id, "rfc": mapping["rfc"], "folder_id": folder["id"]})
        db.commit()
        return {
            "success": True,
            "linked": linked,
            "linked_count": len(linked),
            "skipped_duplicate_client_rfcs": audit["summary"]["duplicate_client_rfcs"],
            "skipped_duplicate_drive_rfcs": audit["summary"]["duplicate_drive_rfcs"],
        }
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=502, detail=f"No fue posible vincular los expedientes: {exc}") from exc
    finally:
        db.close()


def upsert_client_internal(nombre: str, correo: str):
    db = SessionLocal()
    try:
        client = db.query(Client).filter(Client.full_name.ilike(nombre.strip())).first()
        if client:
            client.email = correo.strip()
        else:
            db.add(Client(
                full_name=nombre.strip(),
                email=correo.strip(),
                responsible_user_id=_ensure_default_owner(db),
                status="active",
                identity_status="prospect",
            ))
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
