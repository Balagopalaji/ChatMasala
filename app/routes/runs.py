"""Run routes — list, create, detail, and lifecycle actions."""

import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

import app.orchestrator as orchestrator
from app.db import get_db
from app.models import AgentProfile, ChatMessage, ChatNode, Run, Turn, UserNote, Workspace

router = APIRouter()
BASE_DIR = Path(__file__).parent.parent  # routes/ -> app/
templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.filters["from_json"] = json.loads

SUPPORTED_WORKFLOWS = {"single_agent", "builder_reviewer"}


# ---------------------------------------------------------------------------
# Run list
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    workspaces = db.query(Workspace).order_by(Workspace.updated_at.desc()).all()
    return templates.TemplateResponse(request, "workspace_list.html", {"workspaces": workspaces})


@router.get("/runs", response_class=HTMLResponse)
async def run_list(request: Request, db: Session = Depends(get_db)):
    runs = db.query(Run).order_by(Run.updated_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "run_list.html",
        {"runs": runs},
    )


# ---------------------------------------------------------------------------
# New run form
# ---------------------------------------------------------------------------


@router.get("/runs/new", response_class=HTMLResponse)
async def new_run_form(request: Request, db: Session = Depends(get_db)):
    profiles = db.query(AgentProfile).order_by(AgentProfile.name).all()
    recent_workspaces = (
        db.query(Run.workspace)
        .filter(Run.workspace != None, Run.workspace != "")
        .order_by(Run.created_at.desc())
        .distinct()
        .limit(5)
        .all()
    )
    recent_workspaces = [r[0] for r in recent_workspaces]
    return templates.TemplateResponse(
        request,
        "run_new.html",
        {
            "profiles": profiles,
            "recent_workspaces": recent_workspaces,
        },
    )


# ---------------------------------------------------------------------------
# Create run
# ---------------------------------------------------------------------------


@router.post("/runs")
def create_run(
    request: Request,
    goal: str = Form(...),
    plan_text: str = Form(""),
    workflow_type: str = Form("single_agent"),
    primary_agent_profile_id: str = Form(""),
    builder_agent_profile_id: str = Form(""),
    reviewer_agent_profile_id: str = Form(""),
    workspace: str = Form(""),
    loop_enabled: str = Form(""),
    max_rounds: int = Form(3),
    db: Session = Depends(get_db),
):
    def parse_id(val):
        try:
            return int(val) if val else None
        except (ValueError, TypeError):
            return None

    errors = []

    if workflow_type not in SUPPORTED_WORKFLOWS:
        errors.append(f"Unsupported workflow '{workflow_type}'. Choose Single Agent or Builder → Reviewer.")

    primary_id = parse_id(primary_agent_profile_id)
    builder_id = parse_id(builder_agent_profile_id)
    reviewer_id = parse_id(reviewer_agent_profile_id)

    if workflow_type == "single_agent":
        if not primary_id:
            errors.append("Single Agent workflow requires an agent profile.")
        elif not db.query(AgentProfile).filter(AgentProfile.id == primary_id).first():
            errors.append("Selected agent profile does not exist.")

    elif workflow_type == "builder_reviewer":
        if not builder_id:
            errors.append("Builder → Reviewer workflow requires a builder profile.")
        elif not db.query(AgentProfile).filter(AgentProfile.id == builder_id).first():
            errors.append("Selected builder profile does not exist.")
        if not reviewer_id:
            errors.append("Builder → Reviewer workflow requires a reviewer profile.")
        elif not db.query(AgentProfile).filter(AgentProfile.id == reviewer_id).first():
            errors.append("Selected reviewer profile does not exist.")

    if errors:
        profiles = db.query(AgentProfile).order_by(AgentProfile.name).all()
        recent_workspaces = (
            db.query(Run.workspace)
            .filter(Run.workspace != None, Run.workspace != "")
            .order_by(Run.created_at.desc())
            .distinct()
            .limit(5)
            .all()
        )
        recent_workspaces = [r[0] for r in recent_workspaces]
        return templates.TemplateResponse(
            request=request,
            name="run_new.html",
            context={
                "profiles": profiles,
                "recent_workspaces": recent_workspaces,
                "errors": errors,
                "form_data": {
                    "goal": goal,
                    "plan_text": plan_text,
                    "workflow_type": workflow_type,
                    "primary_agent_profile_id": primary_agent_profile_id,
                    "builder_agent_profile_id": builder_agent_profile_id,
                    "reviewer_agent_profile_id": reviewer_agent_profile_id,
                    "workspace": workspace,
                    "loop_enabled": loop_enabled,
                    "max_rounds": max_rounds,
                },
            },
            status_code=422,
        )

    title = goal[:60].strip()
    if len(goal) > 60:
        title += "..."

    run = Run(
        title=title,
        goal=goal,
        plan_text=plan_text or None,
        workflow_type=workflow_type,
        primary_agent_profile_id=primary_id,
        builder_agent_profile_id=builder_id,
        reviewer_agent_profile_id=reviewer_id,
        workspace=workspace or None,
        loop_enabled=(loop_enabled == "true"),
        max_rounds=max_rounds,
        status="draft",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return RedirectResponse(f"/runs/{run.id}", status_code=303)


# ---------------------------------------------------------------------------
# Run detail
# ---------------------------------------------------------------------------


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def run_detail(
    run_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    run = db.query(Run).filter(Run.id == run_id).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    turns = (
        db.query(Turn)
        .filter(Turn.run_id == run_id)
        .order_by(Turn.sequence_number)
        .all()
    )
    notes = (
        db.query(UserNote)
        .filter(UserNote.run_id == run_id)
        .order_by(UserNote.created_at)
        .all()
    )
    runs = db.query(Run).order_by(Run.updated_at.desc()).all()
    profiles = {}
    for pid in [run.primary_agent_profile_id, run.builder_agent_profile_id, run.reviewer_agent_profile_id]:
        if pid:
            p = db.query(AgentProfile).filter(AgentProfile.id == pid).first()
            if p:
                profiles[pid] = p
    return templates.TemplateResponse(
        request,
        "run_detail.html",
        {
            "run": run,
            "turns": turns,
            "notes": notes,
            "runs": runs,
            "profiles": profiles,
        },
    )


# ---------------------------------------------------------------------------
# Title edit
# ---------------------------------------------------------------------------


@router.post("/runs/{run_id}/title")
def update_run_title(
    run_id: int,
    title: str = Form(...),
    db: Session = Depends(get_db),
):
    run = db.query(Run).filter(Run.id == run_id).first()
    if run and title.strip():
        run.title = title.strip()
        db.commit()
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


# ---------------------------------------------------------------------------
# Lifecycle actions
# ---------------------------------------------------------------------------


@router.post("/runs/{run_id}/start")
def start_run(run_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    from app.db import SessionLocal
    def bg_start():
        bg_db = SessionLocal()
        try:
            orchestrator.start_thread(run_id, bg_db)
        finally:
            bg_db.close()
    background_tasks.add_task(bg_start)
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@router.post("/runs/{run_id}/pause")
async def pause_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    try:
        orchestrator.pause_thread(run_id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


@router.post("/runs/{run_id}/resume")
def resume_run(run_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    from app.db import SessionLocal
    def bg_resume():
        bg_db = SessionLocal()
        try:
            orchestrator.resume_thread(run_id, bg_db)
        finally:
            bg_db.close()
    background_tasks.add_task(bg_resume)
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@router.post("/runs/{run_id}/continue")
def continue_run(run_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    from app.db import SessionLocal
    def bg_continue():
        bg_db = SessionLocal()
        try:
            orchestrator.continue_thread(run_id, bg_db)
        finally:
            bg_db.close()
    background_tasks.add_task(bg_continue)
    return RedirectResponse(f"/runs/{run_id}", status_code=303)


@router.post("/runs/{run_id}/stop")
async def stop_run(
    run_id: int,
    db: Session = Depends(get_db),
):
    try:
        orchestrator.stop_thread(run_id, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)


# ---------------------------------------------------------------------------
# User notes
# ---------------------------------------------------------------------------


@router.post("/runs/{run_id}/notes")
async def add_note(
    run_id: int,
    db: Session = Depends(get_db),
    note_text: str = Form(...),
):
    try:
        orchestrator.add_user_note(run_id, note_text, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url=f"/runs/{run_id}", status_code=303)
