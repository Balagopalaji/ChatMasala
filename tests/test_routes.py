"""HTTP-level tests for thread routes using FastAPI TestClient."""

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FORM_DATA = {
    "title": "Test Thread",
    "task_text": "Build a widget.",
    "plan_text": "1. Design\n2. Implement",
    "builder_command": "claude --print",
    "reviewer_command": "claude --print",
    "working_directory": "",
    "max_rounds": "3",
}


def create_thread(client) -> int:
    """POST /threads, follow redirect, return the new thread id."""
    resp = client.post("/threads", data=FORM_DATA, follow_redirects=False)
    assert resp.status_code == 303, f"Expected 303, got {resp.status_code}"
    location = resp.headers["location"]
    # location is like /threads/1
    thread_id = int(location.rstrip("/").split("/")[-1])
    return thread_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_thread_list_empty(client):
    """GET / returns 200 and contains 'New Thread' link even when empty."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "New Thread" in resp.text


def test_thread_list_empty_state(client):
    """GET / shows empty-state message when no threads exist."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "No threads yet." in resp.text


def test_new_thread_form(client):
    """GET /threads/new returns 200 with the expected form fields."""
    resp = client.get("/threads/new")
    assert resp.status_code == 200
    body = resp.text
    assert "New Thread" in body
    assert 'name="title"' in body
    assert 'name="task_text"' in body
    assert 'name="plan_text"' in body
    assert 'name="builder_command"' in body
    assert 'name="reviewer_command"' in body
    assert 'name="working_directory"' in body
    assert 'name="max_rounds"' in body
    assert 'action="/threads"' in body


def test_create_thread_redirects(client):
    """POST /threads redirects to the thread detail page."""
    resp = client.post("/threads", data=FORM_DATA, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"].startswith("/threads/")


def test_create_thread_then_detail(client):
    """After creating a thread, GET /threads/{id} returns 200 with the title."""
    thread_id = create_thread(client)
    resp = client.get(f"/threads/{thread_id}")
    assert resp.status_code == 200
    assert FORM_DATA["title"] in resp.text


def test_thread_detail_shows_status(client):
    """Thread detail page shows the initial 'draft' status."""
    thread_id = create_thread(client)
    resp = client.get(f"/threads/{thread_id}")
    assert resp.status_code == 200
    assert "draft" in resp.text


def test_thread_detail_shows_no_turns(client):
    """Thread detail page shows 'No turns yet.' for a fresh thread."""
    thread_id = create_thread(client)
    resp = client.get(f"/threads/{thread_id}")
    assert resp.status_code == 200
    assert "No turns yet." in resp.text


def test_thread_detail_shows_no_notes(client):
    """Thread detail page shows 'No notes yet.' for a fresh thread."""
    thread_id = create_thread(client)
    resp = client.get(f"/threads/{thread_id}")
    assert resp.status_code == 200
    assert "No notes yet." in resp.text


def test_thread_detail_404(client):
    """GET /threads/99999 returns 404."""
    resp = client.get("/threads/99999")
    assert resp.status_code == 404


def test_thread_list_shows_created_thread(client):
    """After creating a thread, it appears in the thread list."""
    create_thread(client)
    resp = client.get("/")
    assert resp.status_code == 200
    assert FORM_DATA["title"] in resp.text


def test_health_endpoint(client):
    """GET /health returns 200 with status ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
