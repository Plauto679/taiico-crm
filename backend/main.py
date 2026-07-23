import os

from fastapi import FastAPI, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from services import cobranza, renovaciones, cartera, auth, clientes, ingestion, drive_sources, renewal_ingestion, client_email_directory, whatsapp, pendientes, mail_configuration, recluta
from services.login_security import login_rate_limiter, secure_cookie_for
from services.session_auth import COOKIE_NAME, SESSION_SECONDS, create_session_token, current_username
from pydantic import BaseModel, Field

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


@app.middleware("http")
async def prevent_sensitive_response_caching(request: Request, call_next):
    response = await call_next(request)
    if request.url.path != "/":
        response.headers["Cache-Control"] = "no-store"
    return response

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=256)

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
            max_age=SESSION_SECONDS,
            httponly=True,
            samesite="lax",
            secure=secure_cookie_for(request),
            path="/",
        )
        return {"success": True, "username": username, "message": "Login successful"}
    login_rate_limiter.record_failure(rate_limit_key)
    raise HTTPException(status_code=401, detail="Invalid credentials")


@app.get("/session")
async def session(username: str = Depends(current_username)):
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

private_dependencies = [Depends(current_username)]

app.include_router(cobranza.router, dependencies=private_dependencies)
app.include_router(renovaciones.router, dependencies=private_dependencies)
app.include_router(cartera.router, dependencies=private_dependencies)
app.include_router(clientes.router, dependencies=private_dependencies)
app.include_router(ingestion.router, dependencies=private_dependencies)
app.include_router(drive_sources.router, dependencies=private_dependencies)
app.include_router(renewal_ingestion.router, dependencies=private_dependencies)
app.include_router(client_email_directory.router, dependencies=private_dependencies)
app.include_router(whatsapp.router, dependencies=private_dependencies)
app.include_router(pendientes.router, dependencies=private_dependencies)
app.include_router(mail_configuration.router, dependencies=private_dependencies)
app.include_router(recluta.router, dependencies=private_dependencies)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=7777)
