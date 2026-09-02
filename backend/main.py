import os
import time

from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from services import cobranza, renovaciones, cumpleanos, cumpleanos_agentes, agentes, cartera, auth, clientes, ingestion, drive_sources, renewal_ingestion, renewal_agent_api, client_email_directory, whatsapp, pendientes, mail_configuration, automatic_mails, recluta, password_management, base_loads, accesos, cotizaciones, audit_logs, rrhh, campanas, finanzas
from services.login_security import login_rate_limiter, secure_cookie_for
from services.authorization import current_access_profile, require_module_access
from services.session_auth import (
    COOKIE_NAME,
    create_session_token,
    current_username,
    session_idle_seconds,
)
from pydantic import BaseModel, Field
from database import engine
from services.performance import begin_request, end_request, install_sqlalchemy_timing, log_request, server_timing

is_production = os.getenv("TAIICO_ENV", "development").strip().casefold() == "production"
app = FastAPI(
    title="TAIICO CRM API",
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "X-Requested-With"],
)

install_sqlalchemy_timing(engine)


@app.middleware("http")
async def measure_request_performance(request: Request, call_next):
    token, metrics = begin_request()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        total_ms = (time.perf_counter() - metrics.started_at) * 1000
        measured_ms = sum(metrics.timings_ms.values())
        metrics.timings_ms["processing"] = max(0.0, total_ms - measured_ms)
        response.headers["Server-Timing"] = server_timing(metrics, total_ms)
        response.headers["X-Request-ID"] = metrics.request_id
        return response
    finally:
        total_ms = (time.perf_counter() - metrics.started_at) * 1000
        log_request(metrics=metrics, method=request.method, path=request.url.path, status=status_code, total_ms=total_ms)
        end_request(token)


@app.middleware("http")
async def audit_mutations(request: Request, call_next):
    if not audit_logs.should_audit(request):
        return await call_next(request)
    username, payload = await audit_logs.capture_request(request)
    try:
        response = await call_next(request)
    except Exception:
        if username:
            audit_logs.record_event(request, username, payload, 500)
        raise
    if username:
        audit_logs.record_event(request, username, payload, response.status_code)
    return response


@app.middleware("http")
async def prevent_sensitive_response_caching(request: Request, call_next):
    response = await call_next(request)
    if request.url.path != "/":
        response.headers["Cache-Control"] = "no-store"
    return response

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)


class PasswordResetConfirmRequest(BaseModel):
    token: str = Field(min_length=20, max_length=512)
    new_password: str = Field(min_length=8, max_length=256)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


@app.post("/login")
async def login(payload: LoginRequest, request: Request, response: Response):
    username = payload.username.strip().casefold()
    rate_limit_key = login_rate_limiter.key(request, username)
    login_rate_limiter.check(rate_limit_key)
    if auth.verify_credentials(username, payload.password):
        login_rate_limiter.clear(rate_limit_key)
        response.set_cookie(
            COOKIE_NAME,
            create_session_token(username),
            max_age=session_idle_seconds(),
            httponly=True,
            samesite="lax",
            secure=secure_cookie_for(request),
            path="/",
        )
        return {"success": True, "username": username, "message": "Login successful"}
    login_rate_limiter.record_failure(rate_limit_key)
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.post("/password/forgot")
async def forgot_password(payload: PasswordResetRequest, request: Request):
    email = payload.email.strip().casefold()
    rate_limit_key = login_rate_limiter.key(request, f"password-reset:{email}")
    login_rate_limiter.check(rate_limit_key)
    login_rate_limiter.record_failure(rate_limit_key)
    try:
        password_management.request_password_reset(email)
    except Exception as exc:
        # Never reveal whether an address is registered.
        print(f"Password reset email unavailable: {type(exc).__name__}: {exc}")
    return {
        "success": True,
        "message": "Si el correo está registrado, recibirás un enlace para restablecer tu contraseña.",
    }


@app.post("/password/reset")
async def reset_password(payload: PasswordResetConfirmRequest):
    try:
        password_management.consume_reset_token(payload.token, payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "message": "Contraseña actualizada"}


@app.post("/password/change")
async def change_password(
    payload: PasswordChangeRequest,
    username: str = Depends(current_username),
):
    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=400,
            detail="La contraseña nueva debe ser diferente a la actual",
        )
    try:
        password_management.change_password(
            username,
            payload.current_password,
            payload.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "message": "Contraseña actualizada"}


@app.get("/session")
async def session(profile=Depends(current_access_profile)):
    return {
        "authenticated": True,
        "username": profile.username,
        "role": profile.role,
        "promotorias": profile.promotorias,
        "rfc": profile.rfc,
        "module_permissions": profile.module_permissions,
        "central_admin": profile.is_central_admin,
    }


@app.post("/session/refresh")
async def refresh_session(
    request: Request,
    response: Response,
    username: str = Depends(current_username),
):
    response.set_cookie(
        COOKIE_NAME,
        create_session_token(username),
        max_age=session_idle_seconds(),
        httponly=True,
        samesite="lax",
        secure=secure_cookie_for(request),
        path="/",
    )
    return {"authenticated": True, "username": username}


@app.post("/logout")
async def logout(
    request: Request,
    response: Response,
    _username: str = Depends(current_username),
):
    response.delete_cookie(
        COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=secure_cookie_for(request),
    )
    return {"success": True}

@app.get("/")
def read_root():
    return {"status": "ok", "message": "TAIICO CRM Backend is running"}

app.include_router(cobranza.router, dependencies=[Depends(require_module_access("cobranza"))])
app.include_router(renovaciones.router, dependencies=[Depends(require_module_access("renovaciones"))])
app.include_router(cumpleanos.router, dependencies=[Depends(require_module_access("cumpleanos"))])
app.include_router(cumpleanos_agentes.router, dependencies=[Depends(require_module_access("cumpleanos_agentes"))])
app.include_router(agentes.router, dependencies=[Depends(require_module_access("agentes"))])
app.include_router(cartera.router, dependencies=[Depends(require_module_access("cartera"))])
app.include_router(clientes.router, dependencies=[Depends(require_module_access("clientes"))])
app.include_router(ingestion.router, dependencies=[Depends(require_module_access("cobranza", operation=True))])
app.include_router(drive_sources.router, dependencies=[Depends(require_module_access("cobranza", operation=True))])
app.include_router(renewal_ingestion.router, dependencies=[Depends(require_module_access("renovaciones", operation=True))])
app.include_router(renewal_agent_api.router)
app.include_router(client_email_directory.router, dependencies=[Depends(require_module_access("clientes"))])
app.include_router(whatsapp.router, dependencies=[Depends(require_module_access("renovaciones", operation=True))])
app.include_router(pendientes.router, dependencies=[Depends(require_module_access("pendientes"))])
app.include_router(mail_configuration.router, dependencies=[Depends(require_module_access("configuracion_mail"))])
app.include_router(automatic_mails.router, dependencies=[Depends(require_module_access("configuracion_mail"))])
app.include_router(recluta.router, dependencies=[Depends(require_module_access("recluta"))])
app.include_router(base_loads.router, dependencies=[Depends(require_module_access("carga_bases", operation=True))])
app.include_router(accesos.router, dependencies=[Depends(require_module_access("accesos", operation=True))])
app.include_router(cotizaciones.public_router)
app.include_router(cotizaciones.router, dependencies=[Depends(require_module_access("cotizaciones"))])
app.include_router(audit_logs.router, dependencies=[Depends(require_module_access("logs"))])
app.include_router(rrhh.router, dependencies=[Depends(require_module_access("rrhh"))])
app.include_router(campanas.router, dependencies=[Depends(require_module_access("campanas"))])
app.include_router(finanzas.router, dependencies=[Depends(require_module_access("finanzas"))])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=7777)
