from fastapi import FastAPI, HTTPException, Body, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from services import cobranza, renovaciones, cartera, auth, clientes, ingestion, drive_sources, renewal_ingestion, client_email_directory, whatsapp, pendientes, mail_configuration, recluta
from services.session_auth import COOKIE_NAME, SESSION_SECONDS, create_session_token, current_username
from pydantic import BaseModel

app = FastAPI(title="TAIICO CRM API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:7777", "*"],  # Next.js frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/login")
async def login(request: LoginRequest, response: Response):
    if auth.verify_credentials(request.username, request.password):
        username = request.username.strip().casefold()
        response.set_cookie(
            COOKIE_NAME,
            create_session_token(username),
            max_age=SESSION_SECONDS,
            httponly=True,
            samesite="lax",
            secure=False,
            path="/",
        )
        return {"success": True, "username": username, "message": "Login successful"}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")


@app.get("/session")
async def session(username: str = Depends(current_username)):
    return {"authenticated": True, "username": username}


@app.post("/logout")
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"success": True}

@app.get("/")
def read_root():
    return {"status": "ok", "message": "TAIICO CRM Backend is running"}

app.include_router(cobranza.router)
app.include_router(renovaciones.router)
app.include_router(cartera.router)
app.include_router(clientes.router)
app.include_router(ingestion.router)
app.include_router(drive_sources.router)
app.include_router(renewal_ingestion.router)
app.include_router(client_email_directory.router)
app.include_router(whatsapp.router)
app.include_router(pendientes.router)
app.include_router(mail_configuration.router)
app.include_router(recluta.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=7777, reload=True)
