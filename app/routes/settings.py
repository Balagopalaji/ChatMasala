"""Settings routes — agent profile management."""

from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import os

from app.db import get_db
from app.models import AgentProfile

router = APIRouter()
BASE_DIR = Path(__file__).parent.parent  # routes/ -> app/
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, db: Session = Depends(get_db)):
    profiles = db.query(AgentProfile).order_by(AgentProfile.name).all()
    return templates.TemplateResponse(
        request,
        "settings.html",
        {"profiles": profiles},
    )


@router.get("/settings/profiles/new", response_class=HTMLResponse)
def new_profile_form(request: Request):
    return templates.TemplateResponse(
        request,
        "profile_form.html",
        {"profile": None, "error": None},
    )


@router.post("/settings/profiles/new")
def create_profile(
    request: Request,
    name: str = Form(...),
    provider: str = Form("claude"),
    command_template: str = Form(...),
    instruction_file: str = Form(...),
    db: Session = Depends(get_db),
):
    error = None
    if not os.path.isfile(instruction_file):
        error = f"Instruction file not found: {instruction_file}"
    if not error:
        existing = db.query(AgentProfile).filter(AgentProfile.name == name).first()
        if existing:
            error = f"A profile named '{name}' already exists."
    if error:
        return templates.TemplateResponse(
            request,
            "profile_form.html",
            {
                "profile": None,
                "error": error,
                "form_data": {
                    "name": name,
                    "provider": provider,
                    "command_template": command_template,
                    "instruction_file": instruction_file,
                },
            },
        )
    profile = AgentProfile(
        name=name,
        provider=provider,
        command_template=command_template,
        instruction_file=instruction_file,
    )
    db.add(profile)
    db.commit()
    return RedirectResponse("/settings", status_code=303)


@router.get("/settings/profiles/{profile_id}/edit", response_class=HTMLResponse)
def edit_profile_form(profile_id: int, request: Request, db: Session = Depends(get_db)):
    profile = db.query(AgentProfile).filter(AgentProfile.id == profile_id).first()
    if not profile:
        return RedirectResponse("/settings", status_code=303)
    return templates.TemplateResponse(
        request,
        "profile_form.html",
        {"profile": profile, "error": None},
    )


@router.post("/settings/profiles/{profile_id}/edit")
def update_profile(
    profile_id: int,
    request: Request,
    name: str = Form(...),
    provider: str = Form("claude"),
    command_template: str = Form(...),
    instruction_file: str = Form(...),
    db: Session = Depends(get_db),
):
    profile = db.query(AgentProfile).filter(AgentProfile.id == profile_id).first()
    if not profile:
        return RedirectResponse("/settings", status_code=303)
    error = None
    if not os.path.isfile(instruction_file):
        error = f"Instruction file not found: {instruction_file}"
    if not error:
        conflict = db.query(AgentProfile).filter(
            AgentProfile.name == name,
            AgentProfile.id != profile_id,
        ).first()
        if conflict:
            error = f"A profile named '{name}' already exists."
    if error:
        return templates.TemplateResponse(
            request,
            "profile_form.html",
            {
                "profile": profile,
                "error": error,
                "form_data": {
                    "name": name,
                    "provider": provider,
                    "command_template": command_template,
                    "instruction_file": instruction_file,
                },
            },
        )
    profile.name = name
    profile.provider = provider
    profile.command_template = command_template
    profile.instruction_file = instruction_file
    db.commit()
    return RedirectResponse("/settings", status_code=303)
