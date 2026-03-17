"""Workspace routes — list, create, detail, node management."""
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.agents.cli_runner import run_agent
from app.db import get_db
from app.models import AgentProfile, ChatNode, ChatMessage, Workspace

router = APIRouter()
BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@router.get("/workspaces", response_class=HTMLResponse)
async def workspace_list(request: Request, db: Session = Depends(get_db)):
    workspaces = db.query(Workspace).order_by(Workspace.updated_at.desc()).all()
    return templates.TemplateResponse(request, "workspace_list.html", {"workspaces": workspaces})


@router.get("/workspaces/new", response_class=HTMLResponse)
async def new_workspace_form(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(request, "workspace_new.html", {})


@router.post("/workspaces")
def create_workspace(
    request: Request,
    title: str = Form(...),
    workspace_path: str = Form(""),
    db: Session = Depends(get_db),
):
    ws = Workspace(
        title=title.strip(),
        workspace_path=workspace_path.strip() or None,
    )
    db.add(ws)
    db.commit()
    db.refresh(ws)
    # Auto-create one default node
    node = ChatNode(workspace_id=ws.id, name="Node 1", order_index=0)
    db.add(node)
    db.commit()
    return RedirectResponse(f"/workspaces/{ws.id}", status_code=303)


@router.get("/workspaces/{ws_id}", response_class=HTMLResponse)
async def workspace_detail(ws_id: int, request: Request, db: Session = Depends(get_db)):
    ws = db.query(Workspace).filter(Workspace.id == ws_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    profiles = db.query(AgentProfile).order_by(AgentProfile.sort_order, AgentProfile.name).all()
    all_workspaces = db.query(Workspace).order_by(Workspace.updated_at.desc()).all()
    node_names = {n.id: n.name for n in ws.nodes}
    return templates.TemplateResponse(request, "workspace_detail.html", {
        "workspace": ws,
        "profiles": profiles,
        "all_workspaces": all_workspaces,
        "node_names": node_names,
    })


@router.post("/workspaces/{ws_id}/nodes")
def add_node(
    ws_id: int,
    name: str = Form("New Node"),
    db: Session = Depends(get_db),
):
    ws = db.query(Workspace).filter(Workspace.id == ws_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    max_order = max((n.order_index for n in ws.nodes), default=-1)
    node = ChatNode(workspace_id=ws_id, name=name.strip() or "New Node", order_index=max_order + 1)
    db.add(node)
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.post("/workspaces/{ws_id}/nodes/{node_id}/rename")
def rename_node(
    ws_id: int,
    node_id: int,
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    node = db.query(ChatNode).filter(ChatNode.id == node_id, ChatNode.workspace_id == ws_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if node.status == "running":
        raise HTTPException(status_code=400, detail="Cannot rename a running node")
    node.name = name.strip() or node.name
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.post("/workspaces/{ws_id}/nodes/{node_id}/delete")
def delete_node(
    ws_id: int,
    node_id: int,
    db: Session = Depends(get_db),
):
    node = db.query(ChatNode).filter(ChatNode.id == node_id, ChatNode.workspace_id == ws_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if node.status == "running":
        raise HTTPException(status_code=400, detail="Cannot delete a running node")
    # Clear inbound routes from sibling nodes pointing to this node
    db.query(ChatNode).filter(
        ChatNode.workspace_id == ws_id,
        ChatNode.downstream_node_id == node_id,
    ).update({"downstream_node_id": None})
    db.delete(node)
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.post("/workspaces/{ws_id}/nodes/{node_id}/agent")
def set_node_agent(
    ws_id: int,
    node_id: int,
    agent_profile_id: str = Form(""),
    db: Session = Depends(get_db),
):
    node = db.query(ChatNode).filter(ChatNode.id == node_id, ChatNode.workspace_id == ws_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    try:
        pid = int(agent_profile_id) if agent_profile_id else None
    except ValueError:
        pid = None
    node.agent_profile_id = pid
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.post("/workspaces/{ws_id}/nodes/{node_id}/route")
def set_node_route(
    ws_id: int,
    node_id: int,
    downstream_node_id: str = Form(""),
    db: Session = Depends(get_db),
):
    node = db.query(ChatNode).filter(ChatNode.id == node_id, ChatNode.workspace_id == ws_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    try:
        did = int(downstream_node_id) if downstream_node_id else None
    except ValueError:
        did = None
    # Prevent self-loop
    if did == node_id:
        did = None
    if did is not None:
        target = db.query(ChatNode).filter(ChatNode.id == did).first()
        if not target or target.workspace_id != ws_id:
            raise HTTPException(status_code=400, detail="Route target must be in the same workspace")
    node.downstream_node_id = did
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.post("/workspaces/{ws_id}/nodes/{node_id}/send")
def send_message(
    ws_id: int,
    node_id: int,
    background_tasks: BackgroundTasks,
    content: str = Form(...),
    db: Session = Depends(get_db),
):
    from app.db import SessionLocal
    node = db.query(ChatNode).filter(ChatNode.id == node_id, ChatNode.workspace_id == ws_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if node.status == "running":
        raise HTTPException(status_code=400, detail="Node is already running")

    content = content.strip()
    if not content:
        return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)

    # Capture route target at send time
    downstream_node_id = node.downstream_node_id

    # Next sequence number
    last = db.query(ChatMessage).filter(
        ChatMessage.node_id == node_id,
        ChatMessage.conversation_version == node.conversation_version
    ).order_by(ChatMessage.sequence_number.desc()).first()
    next_seq = (last.sequence_number + 1) if last else 1

    # Save user message
    user_msg = ChatMessage(
        node_id=node_id,
        sequence_number=next_seq,
        conversation_version=node.conversation_version,
        role="user",
        message_kind="manual_user",
        content=content,
        status="completed",
    )
    db.add(user_msg)

    # Placeholder assistant message (running)
    asst_msg = ChatMessage(
        node_id=node_id,
        sequence_number=next_seq + 1,
        conversation_version=node.conversation_version,
        role="assistant",
        message_kind="assistant_reply",
        content="",
        status="running",
    )
    db.add(asst_msg)
    node.status = "running"
    db.commit()
    db.refresh(asst_msg)
    asst_msg_id = asst_msg.id

    def bg_send():
        bg_db = SessionLocal()
        try:
            _execute_node_send(node_id, asst_msg_id, downstream_node_id, bg_db)
        finally:
            bg_db.close()

    background_tasks.add_task(bg_send)
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.post("/workspaces/{ws_id}/nodes/{node_id}/reset")
def reset_node(
    ws_id: int,
    node_id: int,
    db: Session = Depends(get_db),
):
    node = db.query(ChatNode).filter(ChatNode.id == node_id, ChatNode.workspace_id == ws_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if node.status == "running":
        raise HTTPException(status_code=400, detail="Cannot reset a running node")
    node.conversation_version += 1
    node.status = "idle"
    node.last_error = None
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.post("/workspaces/{ws_id}/nodes/{node_id}/import-last")
def import_last_message(
    ws_id: int,
    node_id: int,
    source_node_id: str = Form(""),
    db: Session = Depends(get_db),
):
    node = db.query(ChatNode).filter(ChatNode.id == node_id, ChatNode.workspace_id == ws_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if not source_node_id:
        return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)
    try:
        src_id = int(source_node_id)
    except ValueError:
        return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)

    src_node = db.query(ChatNode).filter(ChatNode.id == src_id, ChatNode.workspace_id == ws_id).first()
    if not src_node:
        return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)

    # Find last assistant message from source node's current conversation
    src_msg = db.query(ChatMessage).filter(
        ChatMessage.node_id == src_id,
        ChatMessage.role == "assistant",
        ChatMessage.conversation_version == src_node.conversation_version,
        ChatMessage.status == "completed",
    ).order_by(ChatMessage.sequence_number.desc()).first()

    if not src_msg:
        return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)

    # Prevent duplicate import (same source_message_id already in this node's current conversation)
    exists = db.query(ChatMessage).filter(
        ChatMessage.node_id == node_id,
        ChatMessage.source_message_id == src_msg.id,
        ChatMessage.conversation_version == node.conversation_version,
    ).first()
    if exists:
        return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)

    last = db.query(ChatMessage).filter(
        ChatMessage.node_id == node_id,
        ChatMessage.conversation_version == node.conversation_version,
    ).order_by(ChatMessage.sequence_number.desc()).first()
    next_seq = (last.sequence_number + 1) if last else 1

    imported = ChatMessage(
        node_id=node_id,
        sequence_number=next_seq,
        conversation_version=node.conversation_version,
        role="user",
        message_kind="manual_import",
        content=src_msg.content,
        source_node_id=src_id,
        source_message_id=src_msg.id,
        status="completed",
    )
    db.add(imported)
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


# ---------------------------------------------------------------------------
# Background execution helpers
# ---------------------------------------------------------------------------


def _execute_node_send(node_id: int, asst_msg_id: int, downstream_node_id, db):
    """Execute CLI agent for a node send and update the assistant message."""
    from datetime import datetime, timezone

    node = db.query(ChatNode).filter(ChatNode.id == node_id).first()
    if not node:
        return

    asst_msg = db.query(ChatMessage).filter(ChatMessage.id == asst_msg_id).first()
    if not asst_msg:
        return

    profile = node.agent_profile if node.agent_profile_id else None

    if not profile:
        asst_msg.content = "[No agent configured for this node]"
        asst_msg.status = "failed"
        asst_msg.error_text = "No agent profile assigned"
        asst_msg.completed_at = datetime.now(timezone.utc)
        node.status = "needs_attention"
        node.last_error = "No agent profile assigned"
        db.commit()
        return

    # Build conversation history for this node's current version
    history_msgs = db.query(ChatMessage).filter(
        ChatMessage.node_id == node_id,
        ChatMessage.conversation_version == node.conversation_version,
        ChatMessage.id != asst_msg_id,
        ChatMessage.status == "completed",
    ).order_by(ChatMessage.sequence_number).all()

    # Build prompt: concatenate history
    prompt_parts = []
    for m in history_msgs:
        role_label = m.role.upper()
        prompt_parts.append(f"{role_label}: {m.content}")
    prompt_text = "\n\n".join(prompt_parts)
    asst_msg.prompt_text = prompt_text

    workspace_path = node.workspace.workspace_path if node.workspace else None

    result = run_agent(
        command=profile.command_template,
        prompt=prompt_text,
        working_directory=workspace_path,
    )
    asst_msg.raw_output_text = result.stdout

    if result.error or result.timed_out or result.exit_code != 0:
        stderr_snippet = result.stderr.strip()[:500] if result.stderr else ""
        if result.error:
            error_detail = result.error
        elif result.timed_out:
            error_detail = "Agent timed out after 300s"
        else:
            error_detail = f"Exit {result.exit_code}" + (f": {stderr_snippet}" if stderr_snippet else "")
        display = result.error or stderr_snippet or result.stdout.strip() or "(no output)"
        asst_msg.content = f"[Agent error]\n{display}"
        asst_msg.status = "failed"
        asst_msg.error_text = error_detail
        asst_msg.completed_at = datetime.now(timezone.utc)
        node.status = "needs_attention"
        node.last_error = error_detail
        db.commit()
        # Do NOT auto-route failed output
    else:
        asst_msg.content = result.stdout.strip() or "[Agent returned empty output]"
        asst_msg.status = "completed"
        asst_msg.completed_at = datetime.now(timezone.utc)
        node.status = "idle"
        node.last_error = None
        db.commit()
        # Auto-route only on success
        if downstream_node_id:
            _deliver_auto_route(node_id, asst_msg_id, downstream_node_id, db)


def _deliver_auto_route(source_node_id: int, source_msg_id: int, target_node_id: int, db):
    """Deliver an auto-routed message to the target node."""
    src_msg = db.query(ChatMessage).filter(ChatMessage.id == source_msg_id).first()
    target_node = db.query(ChatNode).filter(ChatNode.id == target_node_id).first()
    if not src_msg or not target_node:
        return

    # Workspace boundary check
    src_node = db.query(ChatNode).filter(ChatNode.id == source_node_id).first()
    if not src_node or src_node.workspace_id != target_node.workspace_id:
        return  # refuse cross-workspace delivery silently

    # Prevent duplicate auto-route delivery
    exists = db.query(ChatMessage).filter(
        ChatMessage.node_id == target_node_id,
        ChatMessage.source_message_id == source_msg_id,
        ChatMessage.message_kind == "auto_route",
    ).first()
    if exists:
        return

    last = db.query(ChatMessage).filter(
        ChatMessage.node_id == target_node_id,
        ChatMessage.conversation_version == target_node.conversation_version,
    ).order_by(ChatMessage.sequence_number.desc()).first()
    next_seq = (last.sequence_number + 1) if last else 1

    routed = ChatMessage(
        node_id=target_node_id,
        sequence_number=next_seq,
        conversation_version=target_node.conversation_version,
        role="user",
        message_kind="auto_route",
        content=src_msg.content,
        source_node_id=source_node_id,
        source_message_id=source_msg_id,
        status="completed",
    )
    db.add(routed)
    db.commit()
