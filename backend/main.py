from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from services import cobranza, renovaciones, cartera

app = FastAPI(title="TAIICO CRM API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:7777"],  # Next.js frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "TAIICO CRM Backend is running"}

app.include_router(cobranza.router)
app.include_router(renovaciones.router)
app.include_router(cartera.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=7777, reload=True)
