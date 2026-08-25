from fastapi import FastAPI
from app.api.routes import auth

app = FastAPI(title = "PulseBoard")

app.include_router(auth.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
