"""Thread routes — list, create, detail, and lifecycle actions."""

import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

import app.orchestrator as orchestrator
from app.db import get_db, get_settings
from app.models import Thread, Turn, UserNote

router = APIRouter()
BASE_DIR = Path(__file__).parent.parent  # routes/ -> app/
templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.filters["from_json"] = json.loads


# ---------------------------------------------------------------------------
# Thread list
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def thread_list(request: Request, db: Session = Depends(get_db)):
    threads = db.query(Thread).order_by(Thread.updated_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "thread_list.html",
        {"threads": threads},
    )


# ---------------------------------------------------------------------------
# New thread form
# ---------------------------------------------------------------------------


@router.get("/threads/new", response_class=HTMLResponse)
async def thread_new(request: Request, db: Session = Depends(get_db)):
    settings = get_settings(db)
    threads = db.query(Thread).order_by(Thread.updated_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "thread_new.html",
        {"settings": settings, "threads": threads},
    )


# ---------------------------------------------------------------------------
# Create thread
# ---------------------------------------------------------------------------


@router.post("/threads")
async def thread_create(
    request: Request,
    db: Session = Depends(get_db),
    title: str = Form(...),
    task_text: str = Form(...),
    plan_text: str = Form(...),
    builder_command: str = Form(""),
    reviewer_command: str = Form(""),
    working_directory: str = Form(""),
    max_rounds: int = Form(0),
):
    settings = get_settings(db)

    # Fall back to global settings when form fields are empty
    resolved_builder = builder_command.strip() or settings.builder_command
    resolved_reviewer = reviewer_command.strip() or settings.reviewer_command
    resolved_working_dir = working_directory.strip() or settings.default_working_directory or None
    resolved_max_rounds = max_rounds if max_rounds > 0 else settings.default_max_rounds

    thread = Thread(
        title=title,
        task_text=task_text,
        plan_text=plan_text,
        builder_command=resolved_builder,
        reviewer_command=resolved_reviewer,
        working_directory=resolved_working_dir,
        max_rounds=resolved_max_rounds,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return RedirectResponse(url=f"/threads/{thread.id}", status_code=303)


# ---------------------------------------------------------------------------
# Thread detail
# ---------------------------------------------------------------------------


@router.get("/threads/{thread_id}", response_class=HTMLResponse)
async def thread_detail(
    request: Request,
    thread_id: int,
    db: Session = Depends(get_db),
):
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    turns = (
        db.query(Turn)
        .filter(Turn.thread_id == thread_id)
        .order_by(Turn.sequence_number)
        .all()
    )
    user_notes = (
        db.query(UserNote)
        .filter(UserNote.thread_id == thread_id)
        .order_by(UserNote.created_at)
        .all()
    )
    threads = db.query(Thread).order_by(Thread.updated_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "thread_detail.html",
        {
            "thread": thread,
            "turns": turns,
            "user_notes": user_notes,
            "threads": threads,
        },
    )


# ---------------------------------------------------------------------------
# Lifecycle actions
# ---------------------------------------------------------------------------


@router.post("/threads/{thread_id}/start")
async def thread_start(
    thread_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    background_tasks.add_task(orchestrator.start_thread, thread_id, db)
    return RedirectResponse(url=f"/threads/{thread_id}", status_code=303)


@router.post("/threads/{thread_id}/pause")
async def thread_pause(
    thread_id: int,
    db: Session = Depends(get_db),
):
    try:
        orchestrator.pause_thread(thread_id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/threads/{thread_id}", status_code=303)


@router.post("/threads/{thread_id}/resume")
async def thread_resume(
    thread_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    background_tasks.add_task(orchestrator.resume_thread, thread_id, db)
    return RedirectResponse(url=f"/threads/{thread_id}", status_code=303)


@router.post("/threads/{thread_id}/continue")
async def thread_continue(
    thread_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    background_tasks.add_task(orchestrator.continue_thread, thread_id, db)
    return RedirectResponse(url=f"/threads/{thread_id}", status_code=303)


@router.post("/threads/{thread_id}/stop")
async def thread_stop(
    thread_id: int,
    db: Session = Depends(get_db),
):
    try:
        orchestrator.stop_thread(thread_id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/threads/{thread_id}", status_code=303)


# ---------------------------------------------------------------------------
# User notes
# ---------------------------------------------------------------------------


@router.post("/threads/{thread_id}/notes")
async def thread_add_note(
    thread_id: int,
    db: Session = Depends(get_db),
    note_text: str = Form(...),
):
    try:
        orchestrator.add_user_note(thread_id, note_text, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/threads/{thread_id}", status_code=303)
