"""Workspace routes — list, create, detail, node management."""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.agents.cli_runner import run_agent
from app.db import get_db
from app.models import AgentProfile, AgentRole, ChatNode, ChatMessage, NodeEdge, Workspace

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


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    workspaces = db.query(Workspace).order_by(Workspace.updated_at.desc()).all()
    return templates.TemplateResponse(request, "workspace_list.html", {
        "workspaces": workspaces,
        "all_workspaces": workspaces,
    })


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

    # Build edge-based routing view data
    node_index = {n.id: i for i, n in enumerate(ws.nodes)}

    # outgoing_edges_by_node_id: node_id -> list of edge dicts sorted by sort_order
    outgoing_edges_by_node_id = {}
    for node in ws.nodes:
        edges = sorted(node.outbound_edges, key=lambda e: e.sort_order)
        outgoing_edges_by_node_id[node.id] = [
            {
                "edge_id": e.id,
                "target_node_id": e.target_node_id,
                "target_name": node_names.get(e.target_node_id, f"Node {e.target_node_id}"),
                "trigger": e.trigger,
                "label": e.label or "",
                "sort_order": e.sort_order,
            }
            for e in edges
        ]

    # incoming_sources_by_node_id: node_id -> list of source dicts
    incoming_sources_by_node_id = {n.id: [] for n in ws.nodes}
    for node in ws.nodes:
        for edge in node.outbound_edges:
            if edge.target_node_id in incoming_sources_by_node_id:
                incoming_sources_by_node_id[edge.target_node_id].append({
                    "source_node_id": node.id,
                    "source_name": node.name,
                    "trigger": edge.trigger,
                    "label": edge.label or "",
                })

    # revisit_groups: on_no_go edges for workflow strip overlay
    revisit_groups = []
    for node in ws.nodes:
        for edge in node.outbound_edges:
            if edge.trigger == "on_no_go":
                src_idx = node_index.get(node.id)
                tgt_idx = node_index.get(edge.target_node_id)
                if src_idx is not None and tgt_idx is not None:
                    color_idx = len(revisit_groups) % 4
                    target_name = node_names.get(edge.target_node_id, f"Node {edge.target_node_id}")
                    revisit_groups.append({
                        "start": min(src_idx, tgt_idx),
                        "end": max(src_idx, tgt_idx),
                        "source_node_id": node.id,
                        "target_node_id": edge.target_node_id,
                        "label": f"NO_GO → {target_name}",
                        "color_idx": color_idx,
                    })

    sandbox_path = _get_workspace_sandbox(ws.id)
    return templates.TemplateResponse(request, "workspace_detail.html", {
        "workspace": ws,
        "profiles": profiles,
        "roles": roles,
        "all_workspaces": all_workspaces,
        "node_names": node_names,
        "outgoing_edges_by_node_id": outgoing_edges_by_node_id,
        "incoming_sources_by_node_id": incoming_sources_by_node_id,
        "revisit_groups": revisit_groups,
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
    # Auto-link the previous last node to the new node via a default edge (if none exists)
    if existing_nodes:
        prev = existing_nodes[-1]
        existing_edge = db.query(NodeEdge).filter(
            NodeEdge.source_node_id == prev.id,
            NodeEdge.trigger == "on_complete",
        ).first()
        if not existing_edge:
            db.add(NodeEdge(source_node_id=prev.id, target_node_id=node.id, trigger="on_complete"))
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


@router.post("/workspaces/{ws_id}/nodes/{node_id}/routing-mode")
def set_routing_mode(
    ws_id: int,
    node_id: int,
    routing_mode: str = Form(...),
    db: Session = Depends(get_db),
):
    node = db.query(ChatNode).filter(ChatNode.id == node_id, ChatNode.workspace_id == ws_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if routing_mode not in ("auto", "human_gate"):
        raise HTTPException(status_code=400, detail="Invalid routing_mode")
    node.routing_mode = routing_mode
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.post("/workspaces/{ws_id}/nodes/{node_id}/node-type")
def set_node_type(
    ws_id: int,
    node_id: int,
    node_type: str = Form(...),
    db: Session = Depends(get_db),
):
    node = db.query(ChatNode).filter(ChatNode.id == node_id, ChatNode.workspace_id == ws_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if node_type not in ("agent", "human"):
        raise HTTPException(status_code=400, detail="Invalid node_type")
    node.node_type = node_type
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.post("/workspaces/{ws_id}/nodes/{node_id}/route-output")
async def route_output(
    ws_id: int,
    node_id: int,
    request: Request,
    message_id: int = Form(...),
    db: Session = Depends(get_db),
):
    """Human gate: deliver a specific completed message (by message_id) to selected edges."""
    node = db.query(ChatNode).filter(ChatNode.id == node_id, ChatNode.workspace_id == ws_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if node.status != "awaiting_route":
        raise HTTPException(status_code=400, detail="Node is not awaiting routing")

    form_data = await request.form()
    edge_id_strs = form_data.getlist("edge_ids")
    try:
        selected_edge_ids = [int(x) for x in edge_id_strs if x]
    except ValueError:
        selected_edge_ids = []

    if not selected_edge_ids:
        node.status = "idle"
        db.commit()
        return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)

    src_msg = db.query(ChatMessage).filter(
        ChatMessage.id == message_id,
        ChatMessage.node_id == node_id,
        ChatMessage.conversation_version == node.conversation_version,
        ChatMessage.status == "completed",
    ).first()
    if not src_msg:
        raise HTTPException(status_code=404, detail="Message not found or not completed")

    edges = db.query(NodeEdge).filter(
        NodeEdge.source_node_id == node_id,
        NodeEdge.id.in_(selected_edge_ids),
    ).all()

    for edge in edges:
        edge_entry = {
            "edge_id": edge.id,
            "target_node_id": edge.target_node_id,
            "trigger": edge.trigger,
            "label": edge.label or "",
            "sort_order": edge.sort_order,
        }
        _deliver_routed_message(node_id, src_msg.id, edge_entry, db)

    node.status = "idle"
    node.last_error = None
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.post("/workspaces/{ws_id}/nodes/{node_id}/edges")
def add_edge(
    ws_id: int,
    node_id: int,
    target_node_id: str = Form(""),
    trigger: str = Form("on_complete"),
    label: str = Form(""),
    db: Session = Depends(get_db),
):
    node = db.query(ChatNode).filter(ChatNode.id == node_id, ChatNode.workspace_id == ws_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if trigger not in ("on_complete", "on_no_go"):
        raise HTTPException(status_code=400, detail="Invalid trigger value")
    try:
        tid = int(target_node_id) if target_node_id.strip() else None
    except ValueError:
        tid = None
    if not tid or tid == node_id:
        raise HTTPException(status_code=400, detail="Invalid target node")
    target = db.query(ChatNode).filter(ChatNode.id == tid, ChatNode.workspace_id == ws_id).first()
    if not target:
        raise HTTPException(status_code=400, detail="Target must be in the same workspace")
    # Auto-assign sort_order as max existing + 1
    max_order = db.query(NodeEdge).filter(
        NodeEdge.source_node_id == node_id
    ).with_entities(NodeEdge.sort_order).all()
    next_order = (max(o[0] for o in max_order) + 1) if max_order else 0

    db.add(NodeEdge(
        source_node_id=node_id,
        target_node_id=tid,
        trigger=trigger,
        label=label.strip() or None,
        sort_order=next_order,
    ))
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.post("/workspaces/{ws_id}/nodes/{node_id}/edges/{edge_id}/update")
def update_edge(
    ws_id: int,
    node_id: int,
    edge_id: int,
    target_node_id: str = Form(""),
    trigger: str = Form("on_complete"),
    label: str = Form(""),
    sort_order: int = Form(0),
    db: Session = Depends(get_db),
):
    node = db.query(ChatNode).filter(ChatNode.id == node_id, ChatNode.workspace_id == ws_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    edge = db.query(NodeEdge).filter(NodeEdge.id == edge_id, NodeEdge.source_node_id == node_id).first()
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    if trigger not in ("on_complete", "on_no_go"):
        raise HTTPException(status_code=400, detail="Invalid trigger value")
    try:
        tid = int(target_node_id) if target_node_id.strip() else None
    except ValueError:
        tid = None
    if not tid or tid == node_id:
        raise HTTPException(status_code=400, detail="Invalid target node")
    target = db.query(ChatNode).filter(ChatNode.id == tid, ChatNode.workspace_id == ws_id).first()
    if not target:
        raise HTTPException(status_code=400, detail="Target must be in the same workspace")
    edge.target_node_id = tid
    edge.trigger = trigger
    edge.label = label.strip() or None
    edge.sort_order = sort_order
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.post("/workspaces/{ws_id}/nodes/{node_id}/edges/{edge_id}/delete")
def delete_edge(
    ws_id: int,
    node_id: int,
    edge_id: int,
    db: Session = Depends(get_db),
):
    node = db.query(ChatNode).filter(ChatNode.id == node_id, ChatNode.workspace_id == ws_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    edge = db.query(NodeEdge).filter(NodeEdge.id == edge_id, NodeEdge.source_node_id == node_id).first()
    if not edge:
        raise HTTPException(status_code=404, detail="Edge not found")
    db.delete(edge)
    db.commit()
    return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)


@router.post("/workspaces/{ws_id}/nodes/{node_id}/edges/{edge_id}/reorder")
def reorder_edge(
    ws_id: int,
    node_id: int,
    edge_id: int,
    direction: str = Form(...),  # "up" or "down"
    db: Session = Depends(get_db),
):
    node = db.query(ChatNode).filter(ChatNode.id == node_id, ChatNode.workspace_id == ws_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    # Load all edges for this source, ordered by sort_order then id for stability
    edges = db.query(NodeEdge).filter(
        NodeEdge.source_node_id == node_id
    ).order_by(NodeEdge.sort_order, NodeEdge.id).all()
    idx = next((i for i, e in enumerate(edges) if e.id == edge_id), None)
    if idx is None:
        raise HTTPException(status_code=404, detail="Edge not found")
    if direction == "up" and idx > 0:
        swap = edges[idx - 1]
    elif direction == "down" and idx < len(edges) - 1:
        swap = edges[idx + 1]
    else:
        return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)
    # Swap sort_order values and reindex the whole list for stability
    edges[idx], edges[idx - 1 if direction == "up" else idx + 1] = swap, edges[idx]
    for i, e in enumerate(edges):
        e.sort_order = i
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
    if node.status == "awaiting_route":
        raise HTTPException(status_code=400, detail="Node is awaiting a routing decision — route or reset before sending again")

    content = content.strip()
    if not content:
        return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)

    # Snapshot outbound edges at send time (routing changes during execution won't affect this send)
    edge_snapshot = [
        {"edge_id": e.id, "target_node_id": e.target_node_id, "trigger": e.trigger, "label": e.label or "", "sort_order": e.sort_order}
        for e in node.outbound_edges
    ]

    if node.node_type == "human":
        # Human node: user message IS the output — no agent, no assistant placeholder
        last = db.query(ChatMessage).filter(
            ChatMessage.node_id == node_id,
            ChatMessage.conversation_version == node.conversation_version,
        ).order_by(ChatMessage.sequence_number.desc()).first()
        next_seq = (last.sequence_number + 1) if last else 1

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

        if node.routing_mode == "human_gate":
            node.status = "awaiting_route"
        else:
            node.status = "idle"
        node.last_error = None
        db.commit()
        db.refresh(user_msg)

        if node.routing_mode == "auto":
            # Fan out to all on_complete edges immediately (synchronous — human nodes are fast)
            on_complete = [e for e in edge_snapshot if e["trigger"] == "on_complete"]
            for edge_entry in on_complete:
                _deliver_routed_message(node_id, user_msg.id, edge_entry, db)

        return RedirectResponse(f"/workspaces/{ws_id}", status_code=303)

    # Agent node path — existing code below unchanged
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
            _execute_node_send(node_id, asst_msg_id, edge_snapshot, bg_db)
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


def _append_message(db, *, node_id: int, conversation_version: int, role: str,
                    message_kind: str, content: str, status: str = "completed",
                    source_node_id=None, source_message_id=None) -> "ChatMessage":
    """Append a message to a node's transcript, computing the next sequence_number."""
    last = db.query(ChatMessage).filter(
        ChatMessage.node_id == node_id,
        ChatMessage.conversation_version == conversation_version,
    ).order_by(ChatMessage.sequence_number.desc()).first()
    next_seq = (last.sequence_number + 1) if last else 1
    msg = ChatMessage(
        node_id=node_id,
        sequence_number=next_seq,
        conversation_version=conversation_version,
        role=role,
        message_kind=message_kind,
        content=content,
        status=status,
        source_node_id=source_node_id,
        source_message_id=source_message_id,
    )
    db.add(msg)
    return msg


def _execute_node_send(node_id: int, asst_msg_id: int, edge_snapshot: list, db):
    """Execute CLI agent for a node send and update the assistant message.

    After success, selects delivery target(s) based on edge_snapshot:
    - Only default edge: deliver unconditionally
    - no_go edge present: inspect final line for GO/NO_GO sentinel
      GO → deliver default edge
      NO_GO → deliver no_go edge
      neither → set source needs_attention
    - No edges: end idle, no delivery
    Delivery is append-only; target nodes are never auto-run.
    """
    from datetime import datetime, timezone

    node = db.query(ChatNode).filter(ChatNode.id == node_id).first()
    if not node:
        return

    asst_msg = db.query(ChatMessage).filter(ChatMessage.id == asst_msg_id).first()
    if not asst_msg:
        return

    try:
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

        asst_msg.prompt_text = prompt_text

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
            return

        # Success path
        content = result.stdout.strip() or "[Agent returned empty output]"
        asst_msg.content = content
        asst_msg.status = "completed"
        asst_msg.completed_at = datetime.now(timezone.utc)

        # Re-read node to get fresh routing_mode
        fresh_node = db.query(ChatNode).filter(ChatNode.id == node_id).first()
        if fresh_node:
            node = fresh_node

        if node.routing_mode == "human_gate":
            node.status = "awaiting_route"
            node.last_error = None
            db.commit()
            return

        # Partition edges by trigger
        on_complete_edges = [e for e in edge_snapshot if e["trigger"] == "on_complete"]
        on_no_go_edges = [e for e in edge_snapshot if e["trigger"] == "on_no_go"]

        if not edge_snapshot:
            # No outbound edges — end idle
            node.status = "idle"
            node.last_error = None
            db.commit()
            return

        if not on_no_go_edges:
            # No NO_GO edges — deliver to all on_complete edges unconditionally
            node.status = "idle"
            node.last_error = None
            db.commit()
            for edge in on_complete_edges:
                _deliver_routed_message(node_id, asst_msg_id, edge, db)
            return

        # on_no_go edges present — check sentinel
        lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
        final_line = lines[-1].upper() if lines else ""

        if final_line == "GO":
            node.status = "idle"
            node.last_error = None
            db.commit()
            for edge in on_complete_edges:
                _deliver_routed_message(node_id, asst_msg_id, edge, db)
            return

        if final_line == "NO_GO":
            node.status = "idle"
            node.last_error = None
            db.commit()
            for edge in on_no_go_edges:
                _deliver_routed_message(node_id, asst_msg_id, edge, db)
            return

        # Neither GO nor NO_GO — needs attention
        node.status = "needs_attention"
        node.last_error = "Routed node did not end with GO or NO_GO"
        db.commit()

    except Exception as exc:
        logger.exception(f"Unexpected error in _execute_node_send for node {node_id}")
        try:
            asst_msg.status = "failed"
            asst_msg.error_text = str(exc)
            node.status = "needs_attention"
            node.last_error = f"Unexpected error: {exc}"
            db.commit()
        except Exception:
            pass


def _deliver_routed_message(source_node_id: int, source_msg_id: int, edge_entry: dict, db) -> bool:
    """Deliver a routed message to the target node. Returns True if delivered, False if skipped.

    Append-only — never auto-runs the target node.
    """
    target_node_id = edge_entry["target_node_id"]
    src_msg = db.query(ChatMessage).filter(ChatMessage.id == source_msg_id).first()
    target_node = db.query(ChatNode).filter(ChatNode.id == target_node_id).first()

    if not src_msg or not target_node:
        # Target deleted after send started — flag source
        src_node = db.query(ChatNode).filter(ChatNode.id == source_node_id).first()
        if src_node:
            src_node.status = "needs_attention"
            src_node.last_error = f"Delivery failed: target node {target_node_id} not found"
            db.commit()
        return False

    # Workspace boundary check
    src_node = db.query(ChatNode).filter(ChatNode.id == source_node_id).first()
    if not src_node or src_node.workspace_id != target_node.workspace_id:
        return False

    # Prevent duplicate delivery
    exists = db.query(ChatMessage).filter(
        ChatMessage.node_id == target_node_id,
        ChatMessage.source_message_id == source_msg_id,
        ChatMessage.message_kind == "auto_route",
    ).first()
    if exists:
        return True

    _append_message(
        db,
        node_id=target_node_id,
        conversation_version=target_node.conversation_version,
        role="user",
        message_kind="auto_route",
        content=src_msg.content,
        source_node_id=source_node_id,
        source_message_id=source_msg_id,
    )
    db.commit()
    return True
