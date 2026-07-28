from __future__ import annotations

from fastapi import Depends, HTTPException

from services.auth import AccessProfile, get_access_profile
from services.session_auth import current_username


def current_access_profile(
    username: str = Depends(current_username),
) -> AccessProfile:
    try:
        return get_access_profile(username)
    except KeyError as exc:
        raise HTTPException(
            status_code=403,
            detail="Tu usuario no tiene un perfil de acceso configurado",
        ) from exc


def require_module_access(module: str, *, operation: bool = False):
    def dependency(
        profile: AccessProfile = Depends(current_access_profile),
    ) -> AccessProfile:
        allowed = (
            profile.can_operate(module)
            if operation
            else profile.can_read(module)
        )
        if not allowed:
            raise HTTPException(
                status_code=403,
                detail="No tienes permiso para acceder a este módulo",
            )
        return profile

    return dependency
