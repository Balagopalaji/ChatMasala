from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401 — registers models with Base.metadata

from app import db
from app.routes import threads as threads_router
from app.routes import settings as settings_router

BASE_DIR = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="ChatMasala", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

app.include_router(threads_router.router)
app.include_router(settings_router.router)


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})
