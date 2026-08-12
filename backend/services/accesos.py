from __future__ import annotations

from fastapi import APIRouter, HTTPException

from services import auth


router = APIRouter(prefix="/accesos", tags=["accesos"])


@router.get("/config")
def get_access_config():
    return auth.access_modules_configuration()


@router.get("/users")
def get_access_users():
    try:
        return {"users": auth.list_access_users()}
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo leer el archivo de accesos: {exc}",
        ) from exc


@router.post("/users", status_code=201)
def create_access_user(payload: auth.AccessUserPayload):
    try:
        return {"user": auth.save_access_user(payload, create=True)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo crear el usuario: {exc}",
        ) from exc


@router.put("/users/{username}")
def update_access_user(username: str, payload: auth.AccessUserPayload):
    if username.strip().casefold() != payload.username.strip().casefold():
        raise HTTPException(
            status_code=400,
            detail="El usuario de la ruta no coincide con el usuario del formulario",
        )
    try:
        return {"user": auth.save_access_user(payload, create=False)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo actualizar el usuario: {exc}",
        ) from exc


@router.delete("/users/{username}")
def remove_access_user(username: str):
    try:
        auth.delete_access_user(username)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo eliminar el usuario: {exc}",
        ) from exc
    return {"success": True}
