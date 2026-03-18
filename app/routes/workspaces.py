"""Workspace routes — list, create, detail, node management."""
import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.agents.cli_runner import run_agent
from app.db import get_db
from app.models import AgentProfile, AgentRole, ChatNode, ChatMessage, Workspace

router = APIRouter()
BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def _get_workspace_sandbox(ws_id: int) -> str:
    """Return the sandbox path for a workspace, creating it if needed.

    Sandbox lives at ~/.chatmasala/workspaces/{ws_id}/
    Agents run here when no explicit workspace_path is set.
    This keeps agent file activity isolated from both the ChatMasala
    source tree and the user's real projects.
    """
    sandbox = os.path.join(os.path.expanduser("~"), ".chatmasala", "workspaces", str(ws_id))
    os.makedirs(sandbox, exist_ok=True)
    return sandbox


@router.get("/workspaces", response_class=HTMLResponse)
async def workspace_list(request: Request, db: Session = Depends(get_db)):
    workspaces = db.query(Workspace).order_by(Workspace.updated_at.desc()).all()
    return templates.TemplateResponse(request, "workspace_list.html", {
        "workspaces": workspaces,
        "all_workspaces": workspaces,
    })


@router.post("/workspaces/new")
def create_workspace_immediate(
    db: Session = Depends(get_db),
):
    """Create a workspace immediately with defaults, then redirect to it."""
    ws = Workspace(title="New Workspace", workspace_path=None)
    db.add(ws)
    db.commit()
    db.refresh(ws)
    _get_workspace_sandbox(ws.id)  # create sandbox eagerly
    # Auto-create one default node
    node = ChatNode(workspace_id=ws.id, name="Node 1", order_index=0)
    # Assign the claude_default builtin agent, falling back to any builtin
    default_agent = db.query(AgentProfile).filter(
        AgentProfile.builtin_key == "claude_default"
    ).first() or db.query(AgentProfile).filter(
        AgentProfile.is_builtin == True  # noqa: E712
    ).order_by(AgentProfile.sort_order, AgentProfile.name).first()
    if default_agent:
        node.agent_profile_id = default_agent.id
    db.add(node)
    db.commit()
    return RedirectResponse(f"/workspaces/{ws.id}", status_code=303)


@router.post("/workspaces/{ws_id}/set-path")
def set_workspace_path(
    ws_id: int,
    workspace_path: str = Form(""),
    db: Session = Depends(get_db),
):
    ws = db.query(Workspace).filter(Workspace.id == ws_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws.workspace_path = workspace_path.strip() or None
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.post("/workspaces/{ws_id}/rename")
def rename_workspace(
    ws_id: int,
    title: str = Form(...),
    db: Session = Depends(get_db),
):
    ws = db.query(Workspace).filter(Workspace.id == ws_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws.title = title.strip() or ws.title
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.get("/workspaces/{ws_id}", response_class=HTMLResponse)
async def workspace_detail(ws_id: int, request: Request, db: Session = Depends(get_db)):
    ws = db.query(Workspace).filter(Workspace.id == ws_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    profiles = db.query(AgentProfile).order_by(AgentProfile.sort_order, AgentProfile.name).all()
    roles = db.query(AgentRole).order_by(AgentRole.sort_order, AgentRole.name).all()
    all_workspaces = db.query(Workspace).order_by(Workspace.updated_at.desc()).all()
    node_names = {n.id: n.name for n in ws.nodes}

    # Pre-compute loop group ranges for the workflow strip.
    # A loop group spans from min(source_idx, target_idx) to max(source_idx, target_idx)
    # so backward loops (target before source) are handled correctly.
    LOOP_COLORS = ["orange", "blue", "purple", "green"]  # symbolic names only
    node_index = {n.id: i for i, n in enumerate(ws.nodes)}
    loop_groups = []
    for i, node in enumerate(ws.nodes):
        if node.loop_node_id:
            tgt_idx = node_index.get(node.loop_node_id)
            if tgt_idx is not None:
                color_idx = len(loop_groups) % 4  # cycle through 4 colors
                loop_groups.append({
                    "start": min(i, tgt_idx),
                    "end": max(i, tgt_idx),
                    "max_loops": node.max_loops,
                    "loop_count": node.loop_count,
                    "color_idx": color_idx,
                })

    sandbox_path = _get_workspace_sandbox(ws.id)
    return templates.TemplateResponse(request, "workspace_detail.html", {
        "workspace": ws,
        "profiles": profiles,
        "roles": roles,
        "all_workspaces": all_workspaces,
        "node_names": node_names,
        "loop_groups": loop_groups,
        "sandbox_path": sandbox_path,
    })


@router.get("/workspaces/{ws_id}/status")
async def workspace_status(ws_id: int, db: Session = Depends(get_db)):
    """Lightweight polling endpoint — returns node statuses and latest messages."""
    ws = db.query(Workspace).filter(Workspace.id == ws_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    nodes = []
    for node in ws.nodes:
        msgs = [m for m in node.messages if m.conversation_version == node.conversation_version]
        nodes.append({
            "id": node.id,
            "status": node.status,
            "last_error": node.last_error,
            "loop_count": node.loop_count,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "message_kind": m.message_kind,
                    "status": m.status,
                    "content": m.content,
                    "source_node_id": m.source_node_id,
                }
                for m in msgs
            ],
        })

    return JSONResponse({"nodes": nodes})


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
    # Remember existing nodes before adding the new one
    existing_nodes = sorted(ws.nodes, key=lambda n: n.order_index)
    node = ChatNode(workspace_id=ws_id, name=name.strip() or "New Node", order_index=max_order + 1)
    # Assign the claude_default builtin agent, falling back to any builtin
    default_agent = db.query(AgentProfile).filter(
        AgentProfile.builtin_key == "claude_default"
    ).first() or db.query(AgentProfile).filter(
        AgentProfile.is_builtin == True  # noqa: E712
    ).order_by(AgentProfile.sort_order, AgentProfile.name).first()
    if default_agent:
        node.agent_profile_id = default_agent.id
    db.add(node)
    db.flush()  # get node.id
    # Auto-link the previous last node's output to the new node
    if existing_nodes:
        prev = existing_nodes[-1]
        if prev.output_node_id is None:
            prev.output_node_id = node.id
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
    # Clear inbound routes from sibling nodes pointing to this node (output_node_id and loop_node_id)
    db.query(ChatNode).filter(
        ChatNode.workspace_id == ws_id,
        ChatNode.output_node_id == node_id,
    ).update({"output_node_id": None})
    db.query(ChatNode).filter(
        ChatNode.workspace_id == ws_id,
        ChatNode.loop_node_id == node_id,
    ).update({"loop_node_id": None})
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


@router.post("/workspaces/{ws_id}/nodes/{node_id}/role")
def set_node_role(
    ws_id: int,
    node_id: int,
    agent_role_id: str = Form(""),
    db: Session = Depends(get_db),
):
    node = db.query(ChatNode).filter(ChatNode.id == node_id, ChatNode.workspace_id == ws_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    try:
        rid = int(agent_role_id) if agent_role_id else None
    except ValueError:
        rid = None
    node.agent_role_id = rid or None
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.post("/workspaces/{ws_id}/nodes/{node_id}/route")
def set_node_route(
    ws_id: int,
    node_id: int,
    output_node_id: str = Form(""),
    db: Session = Depends(get_db),
):
    node = db.query(ChatNode).filter(ChatNode.id == node_id, ChatNode.workspace_id == ws_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    try:
        oid = int(output_node_id) if output_node_id else None
    except ValueError:
        oid = None
    # Prevent self-loop
    if oid == node_id:
        oid = None
    if oid is not None:
        target = db.query(ChatNode).filter(ChatNode.id == oid).first()
        if not target or target.workspace_id != ws_id:
            raise HTTPException(status_code=400, detail="Route target must be in the same workspace")
    node.output_node_id = oid
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.post("/workspaces/{ws_id}/nodes/{node_id}/loop-route")
def set_node_loop_route(
    ws_id: int,
    node_id: int,
    loop_node_id: str = Form(""),
    max_loops: int = Form(3),
    db: Session = Depends(get_db),
):
    node = db.query(ChatNode).filter(ChatNode.id == node_id, ChatNode.workspace_id == ws_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    try:
        lid = int(loop_node_id) if loop_node_id else None
    except ValueError:
        lid = None
    # Prevent self-loop
    if lid == node_id:
        lid = None
    if lid is not None:
        target = db.query(ChatNode).filter(ChatNode.id == lid).first()
        if not target or target.workspace_id != ws_id:
            raise HTTPException(status_code=400, detail="Loop target must be in the same workspace")
    node.loop_node_id = lid
    node.max_loops = max(1, max_loops)
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

    # Capture route targets at send time
    output_node_id = node.output_node_id
    loop_node_id = node.loop_node_id
    max_loops = node.max_loops
    loop_count = node.loop_count

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
            _execute_node_send(node_id, asst_msg_id, output_node_id, loop_node_id, max_loops, loop_count, bg_db)
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
    node.loop_count = 0
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.post("/workspaces/{ws_id}/nodes/{node_id}/import-last")
def import_last_message(
    ws_id: int,
    node_id: int,
    background_tasks: BackgroundTasks,
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
    # Auto-run the node with the just-imported message (skip if already running)
    if node.status != "running" and node.agent_profile_id:
        background_tasks.add_task(_auto_run_node, node_id, None)
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


# ---------------------------------------------------------------------------
# Background execution helpers
# ---------------------------------------------------------------------------


def _execute_node_send(node_id: int, asst_msg_id: int, output_node_id, loop_node_id, max_loops, loop_count, db):
    """Execute CLI agent for a node send and update the assistant message.

    After success, applies GO/NO_GO sentinel detection if loop_node_id is set.
    If no loop_node_id, routes unconditionally to output_node_id (message delivery only).
    """
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

    # Load role instructions if a role is assigned
    role_instructions = ""
    if node.agent_role_id and node.agent_role and node.agent_role.instruction_file:
        role_path = Path(node.agent_role.instruction_file)
        if role_path.is_file():
            role_instructions = role_path.read_text()
        else:
            logger.warning(f"Role instruction file not found: {node.agent_role.instruction_file}")

    if role_instructions:
        prompt_text = role_instructions + "\n\n" + prompt_text

    raw_path = node.workspace.workspace_path if node.workspace else None
    workspace_path = raw_path if raw_path else _get_workspace_sandbox(node.workspace_id)

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
        return

    # Success path
    content = result.stdout.strip() or "[Agent returned empty output]"
    asst_msg.content = content
    asst_msg.status = "completed"
    asst_msg.completed_at = datetime.now(timezone.utc)

    if not loop_node_id:
        # No loop configured — route unconditionally to output_node_id and auto-run target
        node.status = "idle"
        node.last_error = None
        db.commit()
        if output_node_id:
            _deliver_auto_route(node_id, asst_msg_id, output_node_id, db, auto_run=True)
        return

    # Loop mode — check sentinel in final non-empty trimmed line
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    final_line = lines[-1].lower() if lines else ""

    if final_line == "go":
        # GO: route to output_node and auto-run target, stay idle
        node.status = "idle"
        node.last_error = None
        db.commit()
        if output_node_id:
            _deliver_auto_route(node_id, asst_msg_id, output_node_id, db, auto_run=True)
        return

    if final_line == "no_go":
        # Read fresh loop_count from DB to avoid stale data
        fresh_node = db.query(ChatNode).filter(ChatNode.id == node_id).first()
        current_loop_count = fresh_node.loop_count if fresh_node else loop_count
        if fresh_node:
            node = fresh_node

        if current_loop_count >= max_loops:
            # Circuit breaker — stop looping (don't increment loop_count)
            if output_node_id:
                node.status = "idle"
                node.last_error = None
                db.commit()
                _deliver_auto_route(node_id, asst_msg_id, output_node_id, db, auto_run=True)
            else:
                node.status = "needs_attention"
                node.last_error = "Max loops reached — no output node configured"
                db.commit()
            return

        # Loop back — increment loop_count, deliver to loop_node_id, then auto-run it
        node.loop_count = current_loop_count + 1

        # Check if loop target is already running before committing
        loop_target = db.query(ChatNode).filter(ChatNode.id == loop_node_id).first()
        if loop_target and loop_target.status == "running":
            # Deliver the message but do NOT auto-run; set source to needs_attention
            node.status = "needs_attention"
            node.last_error = "Loop target is already running — manual retry required once it finishes."
            db.commit()
            _deliver_auto_route(node_id, asst_msg_id, loop_node_id, db)
            return

        # Normal loop-back
        node.status = "idle"
        node.last_error = None
        db.commit()
        routed_msg_id = _deliver_auto_route(node_id, asst_msg_id, loop_node_id, db)

        # Auto-run loop target in a new background thread with its own DB session
        from app.db import SessionLocal
        t = threading.Thread(
            target=_auto_run_node,
            args=(loop_node_id, SessionLocal),
            daemon=True,
        )
        t.start()
        return

    # No sentinel — treat as NO_GO (loop back or route to output if max reached)
    fresh_node = db.query(ChatNode).filter(ChatNode.id == node_id).first()
    current_loop_count = fresh_node.loop_count if fresh_node else loop_count
    if fresh_node:
        node = fresh_node

    if current_loop_count >= max_loops:
        # Circuit breaker — stop looping (don't increment loop_count)
        if output_node_id:
            node.status = "idle"
            node.last_error = None
            db.commit()
            _deliver_auto_route(node_id, asst_msg_id, output_node_id, db, auto_run=True)
        else:
            node.status = "needs_attention"
            node.last_error = "Max loops reached — no output node configured"
            db.commit()
        return

    # Loop back — increment loop_count, deliver to loop_node_id, then auto-run it
    node.loop_count = current_loop_count + 1

    loop_target = db.query(ChatNode).filter(ChatNode.id == loop_node_id).first()
    if loop_target and loop_target.status == "running":
        node.status = "needs_attention"
        node.last_error = "Loop target is already running — manual retry required once it finishes."
        db.commit()
        _deliver_auto_route(node_id, asst_msg_id, loop_node_id, db)
        return

    # Normal loop-back
    node.status = "idle"
    node.last_error = None
    db.commit()
    _deliver_auto_route(node_id, asst_msg_id, loop_node_id, db)

    from app.db import SessionLocal
    t = threading.Thread(
        target=_auto_run_node,
        args=(loop_node_id, SessionLocal),
        daemon=True,
    )
    t.start()


def _auto_run_node(target_node_id: int, session_factory=None):
    """Open a new DB session and auto-run the target node with its existing conversation history."""
    from datetime import datetime, timezone
    from app.db import SessionLocal as _SessionLocal

    bg_db = (session_factory or _SessionLocal)()
    try:
        node = bg_db.query(ChatNode).filter(ChatNode.id == target_node_id).first()
        if not node:
            return
        if not node.agent_profile_id:
            node.status = "needs_attention"
            node.last_error = "No agent assigned — auto-run skipped"
            bg_db.commit()
            return

        # Next sequence number
        last = bg_db.query(ChatMessage).filter(
            ChatMessage.node_id == target_node_id,
            ChatMessage.conversation_version == node.conversation_version,
        ).order_by(ChatMessage.sequence_number.desc()).first()
        next_seq = (last.sequence_number + 1) if last else 1

        asst_msg = ChatMessage(
            node_id=target_node_id,
            sequence_number=next_seq,
            conversation_version=node.conversation_version,
            role="assistant",
            message_kind="assistant_reply",
            content="",
            status="running",
        )
        bg_db.add(asst_msg)
        node.status = "running"
        bg_db.commit()
        bg_db.refresh(asst_msg)

        # Capture route params from the node at this moment
        output_node_id = node.output_node_id
        loop_node_id = node.loop_node_id
        max_loops = node.max_loops
        loop_count = node.loop_count

        _execute_node_send(target_node_id, asst_msg.id, output_node_id, loop_node_id, max_loops, loop_count, bg_db)
    finally:
        bg_db.close()


def _deliver_auto_route(source_node_id: int, source_msg_id: int, target_node_id: int, db, auto_run: bool = False):
    """Deliver an auto-routed message to the target node. Returns routed message id or None.

    When auto_run=True, spawns _auto_run_node on the target after delivery (unless already
    running or missing an agent — in those cases the source node is flagged needs_attention).
    """
    src_msg = db.query(ChatMessage).filter(ChatMessage.id == source_msg_id).first()
    target_node = db.query(ChatNode).filter(ChatNode.id == target_node_id).first()
    if not src_msg or not target_node:
        return None

    # Workspace boundary check
    src_node = db.query(ChatNode).filter(ChatNode.id == source_node_id).first()
    if not src_node or src_node.workspace_id != target_node.workspace_id:
        return None  # refuse cross-workspace delivery silently

    # Prevent duplicate auto-route delivery
    exists = db.query(ChatMessage).filter(
        ChatMessage.node_id == target_node_id,
        ChatMessage.source_message_id == source_msg_id,
        ChatMessage.message_kind == "auto_route",
    ).first()
    if exists:
        routed_id = exists.id
    else:
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
        db.refresh(routed)
        routed_id = routed.id

    if not auto_run:
        return routed_id

    # Auto-run guards — re-read target to get fresh status
    fresh_target = db.query(ChatNode).filter(ChatNode.id == target_node_id).first()
    if not fresh_target:
        return routed_id

    if fresh_target.status == "running":
        # Delivered but can't auto-run — flag source node
        src = db.query(ChatNode).filter(ChatNode.id == source_node_id).first()
        if src:
            src.status = "needs_attention"
            src.last_error = "Output target is already running — message delivered, retry manually"
            db.commit()
        return routed_id

    if not fresh_target.agent_profile_id:
        # No agent — delivered but can't run
        fresh_target.status = "needs_attention"
        fresh_target.last_error = "No agent assigned — message delivered but auto-run skipped"
        db.commit()
        return routed_id

    # Spawn auto-run in a new thread (we're already in a background task)
    t = threading.Thread(target=_auto_run_node, args=(target_node_id, None), daemon=True)
    t.start()
    return routed_id
