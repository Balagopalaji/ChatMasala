"""HTTP-level tests for run routes using FastAPI TestClient."""

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
# Helpers
# ---------------------------------------------------------------------------

def _make_profile(db):
    """Create a minimal AgentProfile in db and return it."""
    from app.models import AgentProfile
    profile = AgentProfile(
        name="Test Agent",
        provider="claude",
        command_template="echo done",
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def create_run(client, db) -> int:
    """Create a profile, POST /runs, follow redirect, return the new run id."""
    profile = _make_profile(db)
    form_data = {
        "goal": "Build a widget.",
        "plan_text": "1. Design\n2. Implement",
        "workflow_type": "single_agent",
        "primary_agent_profile_id": str(profile.id),
        "workspace": "",
        "max_rounds": "3",
    }
    resp = client.post("/runs", data=form_data, follow_redirects=False)
    assert resp.status_code == 303, f"Expected 303, got {resp.status_code}"
    location = resp.headers["location"]
    # location is like /runs/1
    run_id = int(location.rstrip("/").split("/")[-1])
    return run_id


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


def test_run_list_empty(client):
    """GET /runs returns 200."""
    resp = client.get("/runs")
    assert resp.status_code == 200


def test_run_list_empty_state(client):
    """GET /runs shows legacy notice and empty-state message when no runs exist."""
    resp = client.get("/runs")
    assert resp.status_code == 200
    assert "legacy runs view" in resp.text
    assert "No runs yet." in resp.text


def test_new_run_form(client):
    """GET /runs/new returns 200 with the expected form fields."""
    resp = client.get("/runs/new")
    assert resp.status_code == 200
    body = resp.text
    assert "New Run" in body
    assert 'name="goal"' in body
    assert 'name="plan_text"' in body
    assert 'name="workflow_type"' in body
    assert 'name="workspace"' in body
    assert 'name="max_rounds"' in body
    assert 'action="/runs"' in body


def test_create_run_redirects(client_and_db):
    """POST /runs redirects to the run detail page."""
    client, db = client_and_db
    profile = _make_profile(db)
    form_data = {
        "goal": "Build a widget.",
        "plan_text": "1. Design\n2. Implement",
        "workflow_type": "single_agent",
        "primary_agent_profile_id": str(profile.id),
        "workspace": "",
        "max_rounds": "3",
    }
    resp = client.post("/runs", data=form_data, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/runs/")


def test_create_run_then_detail(client_and_db):
    """After creating a run, GET /runs/{id} returns 200 with the goal text."""
    client, db = client_and_db
    run_id = create_run(client, db)
    resp = client.get(f"/runs/{run_id}")
    assert resp.status_code == 200
    assert "Build a widget" in resp.text


def test_run_detail_shows_status(client_and_db):
    """Run detail page shows the initial 'draft' status."""
    client, db = client_and_db
    run_id = create_run(client, db)
    resp = client.get(f"/runs/{run_id}")
    assert resp.status_code == 200
    assert "draft" in resp.text


def test_run_detail_shows_no_turns(client_and_db):
    """Run detail page shows 'No turns yet.' for a fresh run."""
    client, db = client_and_db
    run_id = create_run(client, db)
    resp = client.get(f"/runs/{run_id}")
    assert resp.status_code == 200
    assert "No turns yet." in resp.text


def test_run_detail_shows_no_notes(client_and_db):
    """Run detail page shows 'No notes yet.' for a fresh run."""
    client, db = client_and_db
    run_id = create_run(client, db)
    resp = client.get(f"/runs/{run_id}")
    assert resp.status_code == 200
    assert "No notes yet." in resp.text


def test_run_detail_404(client):
    """GET /runs/99999 returns 404."""
    resp = client.get("/runs/99999")
    assert resp.status_code == 404


def test_run_list_shows_created_run(client_and_db):
    """After creating a run, it appears in the run list at /runs."""
    client, db = client_and_db
    create_run(client, db)
    resp = client.get("/runs")
    assert resp.status_code == 200
    assert "Build a widget" in resp.text


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
# Phase 3: Run Creation UX tests
# ---------------------------------------------------------------------------


def test_new_run_form_shows_workflow_options(client):
    """GET /runs/new shows both workflow preset values."""
    response = client.get("/runs/new")
    assert response.status_code == 200
    assert "single_agent" in response.text
    assert "builder_reviewer" in response.text


def test_new_run_form_shows_profile_dropdowns(client):
    """GET /runs/new contains the profile dropdown elements."""
    response = client.get("/runs/new")
    assert response.status_code == 200
    assert 'name="primary_agent_profile_id"' in response.text
    assert 'name="builder_agent_profile_id"' in response.text
    assert 'name="reviewer_agent_profile_id"' in response.text


def test_create_run_goal_required(client):
    """POST /runs with empty goal returns a non-200-redirect (422 unprocessable)."""
    response = client.post("/runs", data={"goal": ""}, follow_redirects=False)
    # FastAPI returns 422 for failed Form(...) validation
    assert response.status_code == 422


def test_create_run_auto_generates_title(client_and_db):
    """POST /runs auto-generates the title from the goal text."""
    from app.models import Run

    client, db = client_and_db
    profile = _make_profile(db)
    response = client.post("/runs", data={
        "goal": "Fix the authentication bug in the login form",
        "workflow_type": "single_agent",
        "primary_agent_profile_id": str(profile.id),
    }, follow_redirects=False)
    assert response.status_code == 303
    run = db.query(Run).first()
    assert run is not None
    assert run.title == "Fix the authentication bug in the login form"


def test_create_run_auto_generates_title_truncated(client_and_db):
    """POST /runs truncates a long goal to 60 chars and appends ellipsis."""
    from app.models import Run

    client, db = client_and_db
    profile = _make_profile(db)
    long_goal = "A" * 80
    response = client.post("/runs", data={
        "goal": long_goal,
        "workflow_type": "single_agent",
        "primary_agent_profile_id": str(profile.id),
    }, follow_redirects=False)
    assert response.status_code == 303
    run = db.query(Run).first()
    assert run is not None
    assert run.title == "A" * 60 + "..."


def test_create_run_single_agent(client_and_db):
    """POST /runs with single_agent workflow redirects successfully."""
    client, db = client_and_db
    profile = _make_profile(db)
    response = client.post("/runs", data={
        "goal": "Write a hello world script",
        "workflow_type": "single_agent",
        "primary_agent_profile_id": str(profile.id),
        "loop_enabled": "",
    }, follow_redirects=False)
    assert response.status_code == 303


def test_create_run_builder_reviewer_with_loop(client_and_db):
    """POST /runs with builder_reviewer + loop saves loop_enabled=True and max_rounds."""
    from app.models import Run, AgentProfile

    client, db = client_and_db
    builder = AgentProfile(
        name="Builder",
        provider="claude",
        command_template="echo done",
    )
    reviewer = AgentProfile(
        name="Reviewer",
        provider="claude",
        command_template="echo done",
    )
    db.add(builder)
    db.add(reviewer)
    db.commit()
    db.refresh(builder)
    db.refresh(reviewer)
    response = client.post("/runs", data={
        "goal": "Build a feature",
        "workflow_type": "builder_reviewer",
        "builder_agent_profile_id": str(builder.id),
        "reviewer_agent_profile_id": str(reviewer.id),
        "loop_enabled": "true",
        "max_rounds": "5",
    }, follow_redirects=False)
    assert response.status_code == 303
    run = db.query(Run).first()
    assert run is not None
    assert run.loop_enabled is True
    assert run.max_rounds == 5


def test_create_run_loop_disabled_when_not_sent(client_and_db):
    """POST /runs without loop_enabled checkbox stores loop_enabled=False."""
    from app.models import Run, AgentProfile

    client, db = client_and_db
    builder = AgentProfile(
        name="Builder",
        provider="claude",
        command_template="echo done",
    )
    reviewer = AgentProfile(
        name="Reviewer",
        provider="claude",
        command_template="echo done",
    )
    db.add(builder)
    db.add(reviewer)
    db.commit()
    db.refresh(builder)
    db.refresh(reviewer)
    response = client.post("/runs", data={
        "goal": "Build a feature",
        "workflow_type": "builder_reviewer",
        "builder_agent_profile_id": str(builder.id),
        "reviewer_agent_profile_id": str(reviewer.id),
        # loop_enabled not included — mimics unchecked checkbox
    }, follow_redirects=False)
    assert response.status_code == 303
    run = db.query(Run).first()
    assert run is not None
    assert run.loop_enabled is False


def test_workspace_suggestions_in_new_form(client_and_db):
    """GET /runs/new returns 200 with the workspace input field."""
    client, db = client_and_db
    response = client.get("/runs/new")
    assert response.status_code == 200
    assert 'name="workspace"' in response.text


# ---------------------------------------------------------------------------
# Phase 5: Run Detail Relay View tests
# ---------------------------------------------------------------------------


def test_run_detail_single_agent_renders(client_and_db):
    """Run detail page for single_agent shows 'Single Agent' workflow label."""
    from app.models import Run

    client, db = client_and_db
    run = Run(title="Test", goal="Do something", workflow_type="single_agent", status="draft")
    db.add(run)
    db.commit()
    response = client.get(f"/runs/{run.id}")
    assert response.status_code == 200
    assert "Single Agent" in response.text or "single_agent" in response.text


def test_run_detail_builder_reviewer_renders(client_and_db):
    """Run detail page for builder_reviewer shows Builder and Reviewer lanes."""
    from app.models import Run

    client, db = client_and_db
    run = Run(title="Test", goal="Build thing", workflow_type="builder_reviewer", status="draft")
    db.add(run)
    db.commit()
    response = client.get(f"/runs/{run.id}")
    assert response.status_code == 200
    assert "Builder" in response.text or "builder" in response.text


def test_run_detail_title_edit(client_and_db):
    """POST /runs/{id}/title updates the title and redirects."""
    from app.models import Run

    client, db = client_and_db
    run = Run(title="Old Title", goal="goal", workflow_type="single_agent", status="draft")
    db.add(run)
    db.commit()
    response = client.post(f"/runs/{run.id}/title", data={"title": "New Title"}, follow_redirects=False)
    assert response.status_code == 303


def test_run_detail_shows_goal(client_and_db):
    """Run detail page displays the run goal text."""
    from app.models import Run

    client, db = client_and_db
    run = Run(title="test", goal="Fix the authentication bug", workflow_type="single_agent", status="draft")
    db.add(run)
    db.commit()
    response = client.get(f"/runs/{run.id}")
    assert "Fix the authentication bug" in response.text


def test_run_detail_raw_output_collapsed(client_and_db):
    """Run detail page wraps raw prompt/output in a <details> element (collapsed by default)."""
    from app.models import Run, Turn

    client, db = client_and_db
    run = Run(title="test", goal="goal", workflow_type="single_agent", status="done")
    db.add(run)
    db.commit()
    turn = Turn(
        run_id=run.id,
        role="agent",
        sequence_number=1,
        prompt_text="prompt",
        raw_output_text="output",
        status="done",
    )
    db.add(turn)
    db.commit()
    response = client.get(f"/runs/{run.id}")
    assert response.status_code == 200
    # Raw details should be in a <details> element (collapsed by default)
    assert "<details" in response.text


# ---------------------------------------------------------------------------
# Validation: workflow type and profile checks
# ---------------------------------------------------------------------------


def test_create_run_invalid_workflow_rejected(client):
    response = client.post("/runs", data={
        "goal": "Do something",
        "workflow_type": "invalid_workflow",
    })
    assert response.status_code == 422
    assert "Unsupported workflow" in response.text


def test_create_run_single_agent_requires_profile(client):
    response = client.post("/runs", data={
        "goal": "Do something",
        "workflow_type": "single_agent",
        "primary_agent_profile_id": "",
    })
    assert response.status_code == 422
    assert "agent profile" in response.text.lower()


def test_create_run_builder_reviewer_requires_both_profiles(client):
    response = client.post("/runs", data={
        "goal": "Build thing",
        "workflow_type": "builder_reviewer",
        "builder_agent_profile_id": "",
        "reviewer_agent_profile_id": "",
    })
    assert response.status_code == 422
    assert "builder profile" in response.text.lower()


def test_create_run_single_agent_with_valid_profile(client_and_db):
    from app.models import AgentProfile
    client, db = client_and_db
    profile = AgentProfile(
        name="Validation Test Agent",
        provider="claude",
        command_template="echo done",
    )
    db.add(profile)
    db.commit()
    response = client.post("/runs", data={
        "goal": "Do something valid",
        "workflow_type": "single_agent",
        "primary_agent_profile_id": str(profile.id),
    }, follow_redirects=False)
    assert response.status_code == 303


def test_create_run_builder_reviewer_nonexistent_profile(client):
    response = client.post("/runs", data={
        "goal": "Build thing",
        "workflow_type": "builder_reviewer",
        "builder_agent_profile_id": "9999",
        "reviewer_agent_profile_id": "9998",
    })
    assert response.status_code == 422


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
    """Adding a second node auto-links the previous last node's output_node_id."""
    from app.models import Workspace, ChatNode

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

    db.expire(node1)
    node1 = db.query(ChatNode).filter(ChatNode.id == node1.id).first()
    node2 = db.query(ChatNode).filter(ChatNode.workspace_id == ws.id, ChatNode.name == "Node 2").first()
    assert node2 is not None
    assert node1.output_node_id == node2.id


def test_add_node_does_not_overwrite_existing_output_link(client_and_db):
    """Adding a third node does NOT overwrite an existing output_node_id on the second node."""
    from app.models import Workspace, ChatNode

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

    # Manually set node2 to point to node1 (unusual but user-configured)
    node2.output_node_id = node1.id
    db.commit()

    # Adding node3 should NOT change node2's already-set output_node_id
    resp = client.post(f"/workspaces/{ws.id}/nodes", data={"name": "Node 3"}, follow_redirects=False)
    assert resp.status_code == 303

    db.expire(node2)
    node2 = db.query(ChatNode).filter(ChatNode.id == node2.id).first()
    # node2 already had output_node_id set to node1.id — should remain unchanged
    assert node2.output_node_id == node1.id


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


def test_get_workspace_sandbox_creates_directory():
    """_get_workspace_sandbox(999) creates the directory under ~/.chatmasala/workspaces/999/."""
    import os
    import shutil
    from app.routes.workspaces import _get_workspace_sandbox

    expected = os.path.join(os.path.expanduser("~"), ".chatmasala", "workspaces", "999")
    # Clean up before the test in case it already exists
    if os.path.exists(expected):
        shutil.rmtree(expected)

    result = _get_workspace_sandbox(999)

    assert result == expected
    assert os.path.isdir(expected)

    # Cleanup
    shutil.rmtree(expected)


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
    assert node_data["loop_count"] == 0

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
