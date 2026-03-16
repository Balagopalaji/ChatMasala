"""Tests for app/models.py — SQLAlchemy ORM models using in-memory SQLite."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Thread, Turn, UserNote


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
# Thread tests
# ---------------------------------------------------------------------------


def test_thread_create(db_session):
    thread = Thread(
        title="Test Thread",
        task_text="Build a widget.",
        plan_text="1. Design\n2. Implement\n3. Test",
        builder_command="claude --print",
        reviewer_command="claude --print",
        working_directory="/tmp/project",
        max_rounds=5,
    )
    db_session.add(thread)
    db_session.commit()

    queried = db_session.query(Thread).filter_by(title="Test Thread").one()
    assert queried.id is not None
    assert queried.title == "Test Thread"
    assert queried.task_text == "Build a widget."
    assert queried.plan_text == "1. Design\n2. Implement\n3. Test"
    assert queried.builder_command == "claude --print"
    assert queried.reviewer_command == "claude --print"
    assert queried.working_directory == "/tmp/project"
    assert queried.status == "draft"
    assert queried.current_role is None
    assert queried.round_count == 0
    assert queried.max_rounds == 5
    assert queried.last_error is None
    assert queried.created_at is not None
    assert queried.updated_at is not None


def test_thread_default_status_and_rounds(db_session):
    thread = Thread(
        title="Defaults Test",
        task_text="Task.",
        plan_text="Plan.",
        builder_command="cmd",
        reviewer_command="cmd",
    )
    db_session.add(thread)
    db_session.commit()

    queried = db_session.query(Thread).filter_by(title="Defaults Test").one()
    assert queried.status == "draft"
    assert queried.round_count == 0
    assert queried.max_rounds == 3
    assert queried.working_directory is None


# ---------------------------------------------------------------------------
# Turn tests
# ---------------------------------------------------------------------------


def test_turn_create(db_session):
    thread = Thread(
        title="Thread for Turn",
        task_text="Task.",
        plan_text="Plan.",
        builder_command="cmd",
        reviewer_command="cmd",
    )
    db_session.add(thread)
    db_session.flush()  # get thread.id without full commit

    turn = Turn(
        thread_id=thread.id,
        role="builder",
        sequence_number=1,
        prompt_text="You are the builder. Please do the task.",
    )
    db_session.add(turn)
    db_session.commit()

    queried_turn = db_session.query(Turn).filter_by(thread_id=thread.id).one()
    assert queried_turn.id is not None
    assert queried_turn.thread_id == thread.id
    assert queried_turn.role == "builder"
    assert queried_turn.sequence_number == 1
    assert queried_turn.prompt_text == "You are the builder. Please do the task."
    assert queried_turn.raw_output_text is None
    assert queried_turn.parsed_json is None
    assert queried_turn.status == "pending"
    assert queried_turn.started_at is None
    assert queried_turn.ended_at is None

    # Verify FK relationship
    assert queried_turn.thread.title == "Thread for Turn"


def test_turn_fk_enforced(db_session):
    """Creating a Turn with a non-existent thread_id should raise an IntegrityError."""
    turn = Turn(
        thread_id=99999,
        role="builder",
        sequence_number=1,
        prompt_text="prompt",
    )
    db_session.add(turn)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_multiple_turns_sequence(db_session):
    thread = Thread(
        title="Multi-turn Thread",
        task_text="Task.",
        plan_text="Plan.",
        builder_command="cmd",
        reviewer_command="cmd",
    )
    db_session.add(thread)
    db_session.flush()

    turn1 = Turn(
        thread_id=thread.id, role="builder", sequence_number=1, prompt_text="p1"
    )
    turn2 = Turn(
        thread_id=thread.id, role="reviewer", sequence_number=2, prompt_text="p2"
    )
    db_session.add_all([turn1, turn2])
    db_session.commit()

    turns = (
        db_session.query(Turn)
        .filter_by(thread_id=thread.id)
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
    thread = Thread(
        title="Thread for Note",
        task_text="Task.",
        plan_text="Plan.",
        builder_command="cmd",
        reviewer_command="cmd",
    )
    db_session.add(thread)
    db_session.flush()

    note = UserNote(
        thread_id=thread.id,
        note_text="Please pay attention to error handling.",
    )
    db_session.add(note)
    db_session.commit()

    queried_note = db_session.query(UserNote).filter_by(thread_id=thread.id).one()
    assert queried_note.id is not None
    assert queried_note.thread_id == thread.id
    assert queried_note.note_text == "Please pay attention to error handling."
    assert queried_note.created_at is not None

    # Verify FK relationship
    assert queried_note.thread.title == "Thread for Note"


def test_thread_relationships(db_session):
    """Verify that turns and user_notes appear in thread.turns / thread.user_notes."""
    thread = Thread(
        title="Rel Thread",
        task_text="Task.",
        plan_text="Plan.",
        builder_command="cmd",
        reviewer_command="cmd",
    )
    db_session.add(thread)
    db_session.flush()

    turn = Turn(
        thread_id=thread.id, role="builder", sequence_number=1, prompt_text="p"
    )
    note = UserNote(thread_id=thread.id, note_text="n")
    db_session.add_all([turn, note])
    db_session.commit()

    db_session.expire(thread)  # reload from DB
    assert len(thread.turns) == 1
    assert len(thread.user_notes) == 1
    assert thread.turns[0].role == "builder"
    assert thread.user_notes[0].note_text == "n"
