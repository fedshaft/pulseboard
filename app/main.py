from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.routes import auth, sources
from app.core.bootstrap import ensure_bootstrap_admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_bootstrap_admin()
    yield

app = FastAPI(title = "PulseBoard", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(sources.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
