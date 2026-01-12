from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from services import cobranza, renovaciones, cartera, auth
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
async def login(request: LoginRequest):
    if auth.verify_credentials(request.username, request.password):
        return {"success": True, "message": "Login successful"}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/")
def read_root():
    return {"status": "ok", "message": "TAIICO CRM Backend is running"}

app.include_router(cobranza.router)
app.include_router(renovaciones.router)
app.include_router(cartera.router)
app.include_router(clientes.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=7777, reload=True)
