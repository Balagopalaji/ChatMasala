"""Settings routes — view and save global agent configuration."""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db, get_settings, save_settings
from app.models import Thread
from app.schemas import SettingsData

router = APIRouter()
BASE_DIR = Path(__file__).parent.parent  # routes/ -> app/
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@router.get("/settings", response_class=HTMLResponse)
async def settings_get(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    threads = db.query(Thread).order_by(Thread.updated_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"settings": settings, "threads": threads},
    )


@router.post("/settings")
async def settings_post(
    request: Request,
    db: Session = Depends(get_db),
    builder_command: str = Form(""),
    reviewer_command: str = Form(""),
    default_working_directory: str = Form(""),
    default_max_rounds: int = Form(3),
):
    data = SettingsData(
        builder_command=builder_command.strip(),
        reviewer_command=reviewer_command.strip(),
        default_working_directory=default_working_directory.strip(),
        default_max_rounds=default_max_rounds,
    )
    save_settings(db, data)
    return RedirectResponse(url="/", status_code=303)
