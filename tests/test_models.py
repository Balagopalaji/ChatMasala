"""Tests for app/models.py — SQLAlchemy ORM models using in-memory SQLite."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AgentProfile, AgentRole, ChatNode, Run, Turn, UserNote, Workspace


@pytest.fixture(scope="function")
def db_session():
    """Provide a fresh in-memory SQLite session for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# Run tests
# ---------------------------------------------------------------------------


def test_run_create(db_session):
    run = Run(
        title="Test Run",
        goal="Build a widget.",
        plan_text="1. Design\n2. Implement\n3. Test",
        workflow_type="single_agent",
        workspace="/tmp/project",
        max_rounds=5,
    )
    db_session.add(run)
    db_session.commit()

    queried = db_session.query(Run).filter_by(title="Test Run").one()
    assert queried.id is not None
    assert queried.title == "Test Run"
    assert queried.goal == "Build a widget."
    assert queried.plan_text == "1. Design\n2. Implement\n3. Test"
    assert queried.workspace == "/tmp/project"
    assert queried.status == "draft"
    assert queried.current_role is None
    assert queried.round_count == 0
    assert queried.max_rounds == 5
    assert queried.last_error is None
    assert queried.created_at is not None


def test_run_default_status_and_rounds(db_session):
    run = Run(
        title="Defaults Test",
        goal="Task.",
        plan_text="Plan.",
    )
    db_session.add(run)
    db_session.commit()

    queried = db_session.query(Run).filter_by(title="Defaults Test").one()
    assert queried.status == "draft"
    assert queried.round_count == 0
    assert queried.max_rounds == 3
    assert queried.workspace is None


# ---------------------------------------------------------------------------
# Turn tests
# ---------------------------------------------------------------------------


def test_turn_create(db_session):
    run = Run(
        title="Run for Turn",
        goal="Task.",
        plan_text="Plan.",
    )
    db_session.add(run)
    db_session.flush()  # get run.id without full commit

    turn = Turn(
        run_id=run.id,
        role="builder",
        sequence_number=1,
        prompt_text="You are the builder. Please do the task.",
    )
    db_session.add(turn)
    db_session.commit()

    queried_turn = db_session.query(Turn).filter_by(run_id=run.id).one()
    assert queried_turn.id is not None
    assert queried_turn.run_id == run.id
    assert queried_turn.role == "builder"
    assert queried_turn.sequence_number == 1
    assert queried_turn.prompt_text == "You are the builder. Please do the task."
    assert queried_turn.raw_output_text is None
    assert queried_turn.parsed_json is None
    assert queried_turn.status == "pending"
    assert queried_turn.started_at is None
    assert queried_turn.ended_at is None

    # Verify FK relationship
    assert queried_turn.run.title == "Run for Turn"


def test_turn_fk_enforced(db_session):
    """Creating a Turn with a non-existent run_id should raise an IntegrityError."""
    turn = Turn(
        run_id=99999,
        role="builder",
        sequence_number=1,
        prompt_text="prompt",
    )
    db_session.add(turn)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_multiple_turns_sequence(db_session):
    run = Run(
        title="Multi-turn Run",
        goal="Task.",
        plan_text="Plan.",
    )
    db_session.add(run)
    db_session.flush()

    turn1 = Turn(
        run_id=run.id, role="builder", sequence_number=1, prompt_text="p1"
    )
    turn2 = Turn(
        run_id=run.id, role="reviewer", sequence_number=2, prompt_text="p2"
    )
    db_session.add_all([turn1, turn2])
    db_session.commit()

    turns = (
        db_session.query(Turn)
        .filter_by(run_id=run.id)
        .order_by(Turn.sequence_number)
        .all()
    )
    assert len(turns) == 2
    assert turns[0].role == "builder"
    assert turns[1].role == "reviewer"


# ---------------------------------------------------------------------------
# UserNote tests
# ---------------------------------------------------------------------------


def test_usernote_create(db_session):
    run = Run(
        title="Run for Note",
        goal="Task.",
        plan_text="Plan.",
    )
    db_session.add(run)
    db_session.flush()

    note = UserNote(
        run_id=run.id,
        note_text="Please pay attention to error handling.",
    )
    db_session.add(note)
    db_session.commit()

    queried_note = db_session.query(UserNote).filter_by(run_id=run.id).one()
    assert queried_note.id is not None
    assert queried_note.run_id == run.id
    assert queried_note.note_text == "Please pay attention to error handling."
    assert queried_note.created_at is not None

    # Verify FK relationship
    assert queried_note.run.title == "Run for Note"


def test_run_relationships(db_session):
    """Verify that turns and user_notes appear in run.turns / run.user_notes."""
    run = Run(
        title="Rel Run",
        goal="Task.",
        plan_text="Plan.",
    )
    db_session.add(run)
    db_session.flush()

    turn = Turn(
        run_id=run.id, role="builder", sequence_number=1, prompt_text="p"
    )
    note = UserNote(run_id=run.id, note_text="n")
    db_session.add_all([turn, note])
    db_session.commit()

    db_session.expire(run)  # reload from DB
    assert len(run.turns) == 1
    assert len(run.user_notes) == 1
    assert run.turns[0].role == "builder"
    assert run.user_notes[0].note_text == "n"


# ---------------------------------------------------------------------------
# AgentProfile tests
# ---------------------------------------------------------------------------


def test_agent_profile_creation(db_session):
    profile = AgentProfile(
        name="Test Builder",
        provider="claude",
        command_template="claude --dangerously-skip-permissions",
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    assert profile.id is not None
    assert profile.name == "Test Builder"
    assert profile.provider == "claude"


def test_agent_profile_name_unique(db_session):
    p1 = AgentProfile(name="Unique", provider="claude", command_template="cmd")
    p2 = AgentProfile(name="Unique", provider="claude", command_template="cmd2")
    db_session.add(p1)
    db_session.commit()
    db_session.add(p2)
    import pytest
    with pytest.raises(Exception):
        db_session.commit()


# ---------------------------------------------------------------------------
# AgentRole tests
# ---------------------------------------------------------------------------


def test_agent_role_create(db_session):
    """AgentRole can be created and loaded back from the database."""
    role = AgentRole(
        slug="builder",
        name="Builder",
        description="Implements approved work.",
        instruction_file="profiles/agents/builder-v2.md",
        is_builtin=True,
        sort_order=5,
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    queried = db_session.query(AgentRole).filter_by(slug="builder").one()
    assert queried.id is not None
    assert queried.slug == "builder"
    assert queried.name == "Builder"
    assert queried.description == "Implements approved work."
    assert queried.instruction_file == "profiles/agents/builder-v2.md"
    assert queried.is_builtin is True
    assert queried.sort_order == 5


def test_agent_role_slug_unique(db_session):
    """Two AgentRole rows with the same slug should raise an IntegrityError."""
    r1 = AgentRole(slug="critic", name="Critic A", instruction_file="f.md")
    r2 = AgentRole(slug="critic", name="Critic B", instruction_file="f.md")
    db_session.add(r1)
    db_session.commit()
    db_session.add(r2)
    with pytest.raises(Exception):
        db_session.commit()


def test_chat_node_agent_role_id(db_session):
    """A ChatNode can have an agent_role_id assigned and the relationship loads."""
    ws = Workspace(title="Role Test WS")
    db_session.add(ws)
    db_session.flush()

    role = AgentRole(
        slug="planner",
        name="Planner",
        instruction_file="profiles/agents/planner.md",
    )
    db_session.add(role)
    db_session.flush()

    node = ChatNode(workspace_id=ws.id, name="Planning Node", agent_role_id=role.id)
    db_session.add(node)
    db_session.commit()
    db_session.refresh(node)

    assert node.agent_role_id == role.id
    assert node.agent_role is not None
    assert node.agent_role.slug == "planner"
