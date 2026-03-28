import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401 — registers models with Base.metadata

from app import db
from app.routes import browse as browse_router
from app.routes import settings as settings_router
from app.routes import workspaces as workspaces_router

BASE_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    reset_on_startup = os.environ.get("CHATMASALA_RESET_DB_ON_STARTUP", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    db.bootstrap_db(reset=reset_on_startup)
    yield


app = FastAPI(title="ChatMasala", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(workspaces_router.router)
app.include_router(settings_router.router)
app.include_router(browse_router.router)


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})
