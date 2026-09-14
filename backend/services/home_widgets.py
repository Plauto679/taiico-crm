from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from database import HomeWidgetPreference, SessionLocal
from services.auth import AccessProfile, MODULES
from services.authorization import current_access_profile


router = APIRouter(prefix="/home-widgets", tags=["home-widgets"])
WIDGET_MODULES = tuple(module for module in MODULES if module != "inicio")


def allowed_widgets(profile: AccessProfile) -> list[str]:
    return [module for module in WIDGET_MODULES if profile.can_read(module)]


def selected_widgets(profile: AccessProfile, preference: HomeWidgetPreference | None) -> list[str]:
    allowed = set(allowed_widgets(profile))
    if preference is None:
        return [module for module in WIDGET_MODULES if module in allowed]
    return [module for module in preference.module_keys if module in allowed]


class HomeWidgetPayload(BaseModel):
    module_keys: list[str] = Field(max_length=len(WIDGET_MODULES))


@router.get("")
def get_home_widgets(profile: AccessProfile = Depends(current_access_profile)):
    db = SessionLocal()
    try:
        preference = db.get(HomeWidgetPreference, profile.username)
        return {
            "allowed": allowed_widgets(profile),
            "selected": selected_widgets(profile, preference),
            "customized": preference is not None,
        }
    finally:
        db.close()


@router.put("")
def set_home_widgets(
    payload: HomeWidgetPayload,
    profile: AccessProfile = Depends(current_access_profile),
):
    allowed = set(allowed_widgets(profile))
    if len(payload.module_keys) != len(set(payload.module_keys)):
        raise HTTPException(status_code=422, detail="No repitas tarjetas en Inicio")
    if any(module not in allowed for module in payload.module_keys):
        raise HTTPException(status_code=403, detail="Solo puedes agregar módulos a los que tienes acceso")
    db = SessionLocal()
    try:
        preference = db.get(HomeWidgetPreference, profile.username)
        if preference is None:
            preference = HomeWidgetPreference(username=profile.username, module_keys=payload.module_keys)
            db.add(preference)
        else:
            preference.module_keys = payload.module_keys
        db.commit()
        return {"allowed": allowed_widgets(profile), "selected": payload.module_keys, "customized": True}
    finally:
        db.close()
