from __future__ import annotations

from fastapi import Depends, HTTPException

from services.auth import AccessProfile, get_access_profile
from services.session_auth import current_username
from services.performance import timed


def current_access_profile(
    username: str = Depends(current_username),
) -> AccessProfile:
    with timed("auth"):
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


def normalize_promotoria(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def profile_allows_promotoria(profile: AccessProfile, value: object) -> bool:
    """Fail closed for rows without a promotoria when the user is scoped."""
    if profile.is_central_admin:
        return True
    promotoria = normalize_promotoria(value)
    return bool(promotoria) and promotoria in set(profile.promotorias)


def require_promotoria_access(profile: AccessProfile, value: object) -> None:
    if not profile_allows_promotoria(profile, value):
        raise HTTPException(
            status_code=403,
            detail="El registro no pertenece a una promotoría autorizada para tu usuario",
        )
