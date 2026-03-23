"""HTTP-level tests for application routes using FastAPI TestClient."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixture: isolated temp-file SQLite DB wired into the app's get_db dependency
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def client(tmp_path):
    """Return a TestClient with an isolated temp-file SQLite database."""
    from app.db import Base, get_db
    from app.main import app

    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture(scope="function")
def client_and_db(tmp_path):
    """Return (TestClient, db_session) sharing the same isolated SQLite database."""
    from app.db import Base, get_db
    from app.main import app

    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"

    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = TestingSession()

    def override_get_db():
        try:
            yield db
        finally:
            pass  # keep session open for the test to inspect

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c, db

    db.close()
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(client_and_db):
    """Return only the db_session from the client_and_db fixture."""
    _, db = client_and_db
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_home_redirects_to_workspaces(client):
    """GET / returns 200 and renders the workspace list page."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "New Workspace" in resp.text


def test_home_empty_state(client):
    """GET / shows empty-state message when no workspaces exist."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "No workspaces yet." in resp.text


def test_health_endpoint(client):
    """GET /health returns 200 with status ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_settings_page_shows_profiles(client):
    response = client.get("/settings")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Phase 9: Core Workspace Usability tests
# ---------------------------------------------------------------------------


def _make_builtin_agent(db):
    """Create a builtin AgentProfile in db and return it."""
    from app.models import AgentProfile
    profile = AgentProfile(
        name="Claude Sonnet",
        provider="claude",
        command_template="claude --model claude-sonnet-4-5",
        is_builtin=True,
        builtin_key="claude_sonnet",
        sort_order=1,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def test_post_workspaces_new_creates_workspace_and_node(client_and_db):
    """POST /workspaces/new creates a workspace with one default node and redirects."""
    from app.models import Workspace, ChatNode

    client, db = client_and_db
    resp = client.post("/workspaces/new", follow_redirects=False)
    assert resp.status_code == 303
    location = resp.headers["location"]
    assert location.startswith("/workspaces/")

    ws = db.query(Workspace).first()
    assert ws is not None
    assert ws.title == "New Workspace"

    nodes = db.query(ChatNode).filter(ChatNode.workspace_id == ws.id).all()
    assert len(nodes) == 1
    assert nodes[0].name == "Node 1"
    assert nodes[0].order_index == 0


def test_post_workspaces_new_no_form_page(client):
    """POST /workspaces/new redirects directly — no form page is shown."""
    resp = client.post("/workspaces/new", follow_redirects=False)
    assert resp.status_code == 303


def test_post_workspaces_new_assigns_builtin_agent(client_and_db):
    """POST /workspaces/new assigns the first builtin agent to the default node."""
    from app.models import Workspace, ChatNode

    client, db = client_and_db
    agent = _make_builtin_agent(db)

    resp = client.post("/workspaces/new", follow_redirects=False)
    assert resp.status_code == 303

    ws = db.query(Workspace).first()
    node = db.query(ChatNode).filter(ChatNode.workspace_id == ws.id).first()
    assert node.agent_profile_id == agent.id


def test_rename_workspace(client_and_db):
    """POST /workspaces/{ws_id}/rename updates the workspace title."""
    from app.models import Workspace

    client, db = client_and_db
    ws = Workspace(title="Old Title")
    db.add(ws)
    db.commit()
    db.refresh(ws)

    resp = client.post(f"/workspaces/{ws.id}/rename", data={"title": "New Title"}, follow_redirects=False)
    assert resp.status_code == 303

    db.expire(ws)
    ws = db.query(Workspace).filter(Workspace.id == ws.id).first()
    assert ws.title == "New Title"


def test_rename_workspace_404(client):
    """POST /workspaces/99999/rename returns 404."""
    resp = client.post("/workspaces/99999/rename", data={"title": "X"})
    assert resp.status_code == 404


def test_add_node_assigns_default_builtin_agent(client_and_db):
    """Adding a node automatically assigns the first builtin agent."""
    from app.models import Workspace, ChatNode

    client, db = client_and_db
    agent = _make_builtin_agent(db)

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    db.refresh(ws)

    resp = client.post(f"/workspaces/{ws.id}/nodes", data={"name": "Node 2"}, follow_redirects=False)
    assert resp.status_code == 303

    node = db.query(ChatNode).filter(ChatNode.workspace_id == ws.id).first()
    assert node.agent_profile_id == agent.id


def test_add_node_auto_links_previous_last_node(client_and_db):
    """Adding a second node auto-creates a default NodeEdge from the previous last node."""
    from app.models import Workspace, ChatNode, NodeEdge

    client, db = client_and_db

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    db.refresh(ws)

    # Add first node
    node1 = ChatNode(workspace_id=ws.id, name="Node 1", order_index=0)
    db.add(node1)
    db.commit()
    db.refresh(node1)

    # Add second node via route
    resp = client.post(f"/workspaces/{ws.id}/nodes", data={"name": "Node 2"}, follow_redirects=False)
    assert resp.status_code == 303

    node2 = db.query(ChatNode).filter(ChatNode.workspace_id == ws.id, ChatNode.name == "Node 2").first()
    assert node2 is not None

    # Should have created a default NodeEdge from node1 to node2
    edge = db.query(NodeEdge).filter(
        NodeEdge.source_node_id == node1.id,
        NodeEdge.target_node_id == node2.id,
        NodeEdge.trigger == "on_complete",
    ).first()
    assert edge is not None


def test_add_node_does_not_overwrite_existing_default_edge(client_and_db):
    """Adding a third node does NOT overwrite an existing default NodeEdge on the second node."""
    from app.models import Workspace, ChatNode, NodeEdge

    client, db = client_and_db

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    db.refresh(ws)

    node1 = ChatNode(workspace_id=ws.id, name="Node 1", order_index=0)
    node2 = ChatNode(workspace_id=ws.id, name="Node 2", order_index=1)
    db.add(node1)
    db.add(node2)
    db.commit()
    db.refresh(node1)
    db.refresh(node2)

    # Manually set node2 to have a default edge pointing somewhere (node1)
    existing_edge = NodeEdge(source_node_id=node2.id, target_node_id=node1.id, trigger="on_complete")
    db.add(existing_edge)
    db.commit()
    existing_edge_id = existing_edge.id

    # Adding node3 should NOT replace node2's existing default edge
    resp = client.post(f"/workspaces/{ws.id}/nodes", data={"name": "Node 3"}, follow_redirects=False)
    assert resp.status_code == 303

    # node2's default edge should still point to node1
    edge = db.query(NodeEdge).filter(NodeEdge.id == existing_edge_id).first()
    assert edge is not None
    assert edge.target_node_id == node1.id


# ---------------------------------------------------------------------------
# Phase 11: Provider, Agent, and Settings Cleanup tests
# ---------------------------------------------------------------------------


def test_seed_builtin_agents_upsert_no_duplicates(tmp_path):
    """Running seed_builtin_agents twice does not create duplicate rows."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db import Base, BUILTIN_AGENTS
    from app.models import AgentProfile

    db_path = tmp_path / "seed_test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    # Patch SessionLocal temporarily
    import app.db as db_module
    original_session = db_module.SessionLocal

    db_module.SessionLocal = Session
    try:
        db_module.seed_builtin_agents()
        db_module.seed_builtin_agents()  # second call — should upsert, not duplicate
    finally:
        db_module.SessionLocal = original_session

    db = Session()
    count = db.query(AgentProfile).filter(AgentProfile.is_builtin == True).count()  # noqa: E712
    db.close()
    engine.dispose()

    assert count == len(BUILTIN_AGENTS)


def test_seed_builtin_agents_correct_keys(tmp_path):
    """Seeded builtins have the correct builtin_keys and commands."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db import Base, BUILTIN_AGENTS
    from app.models import AgentProfile

    db_path = tmp_path / "seed_keys_test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    import app.db as db_module
    original_session = db_module.SessionLocal
    db_module.SessionLocal = Session
    try:
        db_module.seed_builtin_agents()
    finally:
        db_module.SessionLocal = original_session

    db = Session()
    claude = db.query(AgentProfile).filter(AgentProfile.builtin_key == "claude_default").first()
    codex = db.query(AgentProfile).filter(AgentProfile.builtin_key == "codex_default").first()
    gemini = db.query(AgentProfile).filter(AgentProfile.builtin_key == "gemini_default").first()
    db.close()
    engine.dispose()

    assert claude is not None
    assert claude.command_template == "claude --dangerously-skip-permissions"
    assert codex is not None
    assert codex.command_template == "codex exec -"
    assert gemini is not None
    assert gemini.command_template == "gemini"


def test_get_provider_status_returns_correct_keys():
    """get_provider_status returns a dict with claude, codex, and gemini keys."""
    from app.routes.settings import get_provider_status
    statuses = get_provider_status()
    assert "claude" in statuses
    assert "codex" in statuses
    assert "gemini" in statuses
    for val in statuses.values():
        assert val in ("connected", "not_detected", "cli_only")


def test_test_connection_endpoint_not_found(client):
    """POST /settings/test-connection returns JSON with success=False for missing binary."""
    resp = client.post("/settings/test-connection", data={
        "provider": "claude",
        "command": "nonexistent_binary_xyz",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data
    assert data["success"] is False
    assert "error" in data


def test_test_connection_endpoint_returns_json(client):
    """POST /settings/test-connection always returns JSON with success, output, error keys."""
    resp = client.post("/settings/test-connection", data={
        "provider": "codex",
        "command": "echo test",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "success" in data
    assert "output" in data
    assert "error" in data


def test_new_workspace_default_is_claude_default(client_and_db):
    """POST /workspaces/new assigns claude_default builtin to the node when present."""
    from app.models import Workspace, ChatNode, AgentProfile

    client, db = client_and_db
    # Seed the claude_default agent
    agent = AgentProfile(
        name="Claude",
        provider="claude",
        command_template="claude --dangerously-skip-permissions",
        is_builtin=True,
        builtin_key="claude_default",
        sort_order=0,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    resp = client.post("/workspaces/new", follow_redirects=False)
    assert resp.status_code == 303

    ws = db.query(Workspace).first()
    node = db.query(ChatNode).filter(ChatNode.workspace_id == ws.id).first()
    assert node.agent_profile_id == agent.id


def test_create_custom_agent_via_modal_route(client_and_db):
    """POST /settings/agents/new creates a custom (non-builtin) agent and redirects."""
    from app.models import AgentProfile

    client, db = client_and_db
    resp = client.post("/settings/agents/new", data={
        "name": "My Codex Agent",
        "provider_preset": "codex",
        "command_template": "",
        "instruction_file": "",
        "description": "A codex agent",
    }, follow_redirects=False)
    assert resp.status_code == 303

    agent = db.query(AgentProfile).filter(AgentProfile.name == "My Codex Agent").first()
    assert agent is not None
    assert agent.is_builtin is False
    assert agent.command_template == "codex exec -"


# ---------------------------------------------------------------------------
# set-path route tests
# ---------------------------------------------------------------------------


def test_set_workspace_path_sets_path(client_and_db):
    """POST /workspaces/{ws_id}/set-path sets workspace_path and redirects."""
    from app.models import Workspace

    client, db = client_and_db
    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    db.refresh(ws)

    resp = client.post(
        f"/workspaces/{ws.id}/set-path",
        data={"workspace_path": "/tmp/my-project"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == f"/workspaces/{ws.id}"

    db.expire(ws)
    ws = db.query(Workspace).filter(Workspace.id == ws.id).first()
    assert ws.workspace_path == "/tmp/my-project"


def test_set_workspace_path_empty_clears_to_none(client_and_db):
    """POST /workspaces/{ws_id}/set-path with empty string clears workspace_path to None."""
    from app.models import Workspace

    client, db = client_and_db
    ws = Workspace(title="WS", workspace_path="/existing/path")
    db.add(ws)
    db.commit()
    db.refresh(ws)

    resp = client.post(
        f"/workspaces/{ws.id}/set-path",
        data={"workspace_path": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    db.expire(ws)
    ws = db.query(Workspace).filter(Workspace.id == ws.id).first()
    assert ws.workspace_path is None


def test_get_workspace_sandbox_creates_directory(tmp_path):
    """_get_workspace_sandbox(999) creates the sandbox directory and returns its path."""
    import os
    from unittest.mock import patch
    from app.routes.workspaces import _get_workspace_sandbox

    fake_home = str(tmp_path)
    expected = os.path.join(fake_home, ".chatmasala", "workspaces", "999")

    with patch("os.path.expanduser", return_value=fake_home):
        result = _get_workspace_sandbox(999)

    assert result == expected
    assert os.path.isdir(expected)


def test_workspace_status_endpoint(client_and_db):
    """GET /workspaces/{ws_id}/status returns JSON with node statuses and messages."""
    from app.models import Workspace, ChatNode, ChatMessage

    client, db = client_and_db

    # Create a workspace with one node
    ws = Workspace(title="Status Test WS")
    db.add(ws)
    db.commit()
    db.refresh(ws)

    node = ChatNode(workspace_id=ws.id, name="Node A", order_index=0, status="idle")
    db.add(node)
    db.commit()
    db.refresh(node)

    # Add a message in the current conversation version
    msg = ChatMessage(
        node_id=node.id,
        sequence_number=1,
        conversation_version=node.conversation_version,
        role="user",
        message_kind="manual_user",
        content="Hello",
        status="completed",
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    resp = client.get(f"/workspaces/{ws.id}/status")
    assert resp.status_code == 200

    data = resp.json()
    assert "nodes" in data
    assert len(data["nodes"]) == 1

    node_data = data["nodes"][0]
    assert node_data["id"] == node.id
    assert node_data["status"] == "idle"

    assert len(node_data["messages"]) == 1
    msg_data = node_data["messages"][0]
    assert msg_data["id"] == msg.id
    assert msg_data["role"] == "user"
    assert msg_data["content"] == "Hello"
    assert msg_data["message_kind"] == "manual_user"
    assert msg_data["status"] == "completed"
    assert msg_data["source_node_id"] is None


def test_workspace_status_endpoint_404(client):
    """GET /workspaces/99999/status returns 404 for a non-existent workspace."""
    resp = client.get("/workspaces/99999/status")
    assert resp.status_code == 404


def test_set_default_edge_creates_node_edge(client_and_db):
    """POST /workspaces/{ws_id}/nodes/{node_id}/edges with trigger=on_complete creates a NodeEdge."""
    from app.models import Workspace, ChatNode, NodeEdge

    client, db = client_and_db

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    db.refresh(ws)

    node_a = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    db.add_all([node_a, node_b])
    db.commit()

    resp = client.post(
        f"/workspaces/{ws.id}/nodes/{node_a.id}/edges",
        data={"target_node_id": str(node_b.id), "trigger": "on_complete"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    edge = db.query(NodeEdge).filter(
        NodeEdge.source_node_id == node_a.id,
        NodeEdge.trigger == "on_complete",
    ).first()
    assert edge is not None
    assert edge.target_node_id == node_b.id


def test_set_default_edge_blank_deletes_edge(client_and_db):
    """POST .../edges/{edge_id}/delete deletes the existing edge."""
    from app.models import Workspace, ChatNode, NodeEdge

    client, db = client_and_db

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    db.refresh(ws)

    node_a = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    db.add_all([node_a, node_b])
    db.commit()

    # Create an edge first
    edge = NodeEdge(source_node_id=node_a.id, target_node_id=node_b.id, trigger="on_complete")
    db.add(edge)
    db.commit()
    edge_id = edge.id

    # Delete the edge via the delete endpoint
    resp = client.post(
        f"/workspaces/{ws.id}/nodes/{node_a.id}/edges/{edge_id}/delete",
        follow_redirects=False,
    )
    assert resp.status_code == 303

    remaining = db.query(NodeEdge).filter(NodeEdge.id == edge_id).first()
    assert remaining is None


def test_set_no_go_edge_creates_node_edge(client_and_db):
    """POST /workspaces/{ws_id}/nodes/{node_id}/edges with trigger=on_no_go creates an on_no_go NodeEdge."""
    from app.models import Workspace, ChatNode, NodeEdge

    client, db = client_and_db

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    db.refresh(ws)

    node_a = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    db.add_all([node_a, node_b])
    db.commit()

    resp = client.post(
        f"/workspaces/{ws.id}/nodes/{node_a.id}/edges",
        data={"target_node_id": str(node_b.id), "trigger": "on_no_go"},
        follow_redirects=False,
    )
    assert resp.status_code == 303

    edge = db.query(NodeEdge).filter(
        NodeEdge.source_node_id == node_a.id,
        NodeEdge.trigger == "on_no_go",
    ).first()
    assert edge is not None
    assert edge.target_node_id == node_b.id


def test_workspace_status_no_loop_count(client_and_db):
    """GET /workspaces/{ws_id}/status does not return loop_count in node data."""
    from app.models import Workspace, ChatNode

    client, db = client_and_db

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    db.refresh(ws)

    node = ChatNode(workspace_id=ws.id, name="Node A", order_index=0, status="idle")
    db.add(node)
    db.commit()

    resp = client.get(f"/workspaces/{ws.id}/status")
    assert resp.status_code == 200

    data = resp.json()
    node_data = data["nodes"][0]
    assert "loop_count" not in node_data
