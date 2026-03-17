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
        instruction_file="profiles/agents/single-agent.md",
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


def test_new_profile_form(client):
    response = client.get("/settings/profiles/new")
    assert response.status_code == 200


def test_create_profile_missing_instruction_file(client, tmp_path):
    response = client.post("/settings/profiles/new", data={
        "name": "Test",
        "provider": "claude",
        "command_template": "claude",
        "instruction_file": "/nonexistent/path/file.md",
    })
    assert response.status_code == 200
    assert "not found" in response.text.lower()


def test_create_profile_success(client, tmp_path):
    # Create a real instruction file
    f = tmp_path / "agent.md"
    f.write_text("# Instructions")
    response = client.post("/settings/profiles/new", data={
        "name": "My Agent",
        "provider": "claude",
        "command_template": "claude",
        "instruction_file": str(f),
    })
    assert response.status_code in (200, 303)


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
        instruction_file="profiles/agents/single-agent.md",
    )
    reviewer = AgentProfile(
        name="Reviewer",
        provider="claude",
        command_template="echo done",
        instruction_file="profiles/agents/single-agent.md",
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
        instruction_file="profiles/agents/single-agent.md",
    )
    reviewer = AgentProfile(
        name="Reviewer",
        provider="claude",
        command_template="echo done",
        instruction_file="profiles/agents/single-agent.md",
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
        instruction_file="profiles/agents/single-agent.md",
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
