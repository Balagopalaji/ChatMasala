"""Tests for app/orchestrator.py — deterministic routing logic."""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.cli_runner import RunResult
from app.db import Base
from app.models import Thread, Turn, UserNote
from app.orchestrator import (
    get_latest_user_note,
    resume_thread,
    start_thread,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_BUILDER_OUTPUT = """\
===STRUCTURED_OUTPUT===
STATUS: READY_FOR_REVIEW
SUMMARY: Done
CHANGED_ARTIFACTS: none
CHECKS_RUN: lint=PASS
BLOCKERS: none
HANDOFF_NOTE: Ready for review
===END_STRUCTURED_OUTPUT===
"""

VALID_REVIEWER_APPROVE_OUTPUT = """\
===STRUCTURED_OUTPUT===
VERDICT: APPROVE
SUMMARY: Looks good
OPEN_ISSUES: none
CHECKS_VERIFIED: lint=PASS
NEXT_ACTION: close_thread
RATIONALE: All good
===END_STRUCTURED_OUTPUT===
"""

VALID_REVIEWER_CHANGES_REQUESTED_OUTPUT = """\
===STRUCTURED_OUTPUT===
VERDICT: CHANGES_REQUESTED
SUMMARY: Needs changes
OPEN_ISSUES: fix the thing
CHECKS_VERIFIED: lint=FAIL
NEXT_ACTION: reroute_builder
RATIONALE: See open issues
===END_STRUCTURED_OUTPUT===
"""


@pytest.fixture(scope="function")
def db_session():
    """Provide a fresh in-memory SQLite session for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def make_thread(db_session, **kwargs) -> Thread:
    """Create and persist a draft thread with sensible defaults."""
    defaults = dict(
        title="Test Thread",
        task_text="Build something.",
        plan_text="1. Do it.",
        builder_command="echo builder",
        reviewer_command="echo reviewer",
        max_rounds=3,
    )
    defaults.update(kwargs)
    thread = Thread(**defaults)
    db_session.add(thread)
    db_session.commit()
    db_session.refresh(thread)
    return thread


# ---------------------------------------------------------------------------
# Test: builder success routes to reviewer
# ---------------------------------------------------------------------------


def test_orchestrator_routes_builder_success_to_reviewer(db_session):
    """When builder returns READY_FOR_REVIEW, a reviewer Turn must be created."""
    thread = make_thread(db_session)

    builder_result = RunResult(stdout=VALID_BUILDER_OUTPUT, stderr="", exit_code=0)
    reviewer_result = RunResult(stdout=VALID_REVIEWER_APPROVE_OUTPUT, stderr="", exit_code=0)

    side_effects = [builder_result, reviewer_result]

    with patch("app.orchestrator.run_agent", side_effect=side_effects):
        start_thread(thread.id, db_session)

    turns = (
        db_session.query(Turn)
        .filter(Turn.thread_id == thread.id)
        .order_by(Turn.sequence_number)
        .all()
    )

    roles = [t.role for t in turns]
    assert "builder" in roles, "Expected a builder turn"
    assert "reviewer" in roles, "Expected a reviewer turn to be created after builder success"


# ---------------------------------------------------------------------------
# Test: full loop builder -> reviewer APPROVE -> done
# ---------------------------------------------------------------------------


def test_orchestrator_routes_reviewer_approve_to_done(db_session):
    """Full loop: builder READY_FOR_REVIEW, reviewer APPROVE => thread.status == 'done'."""
    thread = make_thread(db_session)

    builder_result = RunResult(stdout=VALID_BUILDER_OUTPUT, stderr="", exit_code=0)
    reviewer_result = RunResult(stdout=VALID_REVIEWER_APPROVE_OUTPUT, stderr="", exit_code=0)

    with patch("app.orchestrator.run_agent", side_effect=[builder_result, reviewer_result]):
        start_thread(thread.id, db_session)

    db_session.refresh(thread)
    assert thread.status == "done", f"Expected 'done', got '{thread.status}'"


# ---------------------------------------------------------------------------
# Test: reviewer CHANGES_REQUESTED increments round and creates new builder turn
# ---------------------------------------------------------------------------


def test_orchestrator_routes_reviewer_changes_requested_back_to_builder(db_session):
    """Reviewer CHANGES_REQUESTED with rounds remaining: round_count increments and a new builder Turn is created."""
    thread = make_thread(db_session, max_rounds=3)

    builder_result_1 = RunResult(stdout=VALID_BUILDER_OUTPUT, stderr="", exit_code=0)
    reviewer_result = RunResult(stdout=VALID_REVIEWER_CHANGES_REQUESTED_OUTPUT, stderr="", exit_code=0)
    # Second builder call after changes requested — approve on second reviewer pass
    builder_result_2 = RunResult(stdout=VALID_BUILDER_OUTPUT, stderr="", exit_code=0)
    reviewer_result_2 = RunResult(stdout=VALID_REVIEWER_APPROVE_OUTPUT, stderr="", exit_code=0)

    with patch(
        "app.orchestrator.run_agent",
        side_effect=[builder_result_1, reviewer_result, builder_result_2, reviewer_result_2],
    ):
        start_thread(thread.id, db_session)

    db_session.refresh(thread)

    # round_count should have been incremented at least once
    assert thread.round_count >= 1, f"Expected round_count >= 1, got {thread.round_count}"

    # There should be at least 2 builder turns
    builder_turns = (
        db_session.query(Turn)
        .filter(Turn.thread_id == thread.id, Turn.role == "builder")
        .all()
    )
    assert len(builder_turns) >= 2, f"Expected >=2 builder turns, got {len(builder_turns)}"


# ---------------------------------------------------------------------------
# Test: stops at max rounds
# ---------------------------------------------------------------------------


def test_orchestrator_stops_at_max_rounds(db_session):
    """With max_rounds=0, a single CHANGES_REQUESTED => waiting_for_user.

    round_count starts at 0. The check is round_count >= max_rounds before
    incrementing, so max_rounds=0 means no extra builder cycles allowed.
    """
    thread = make_thread(db_session, max_rounds=0)

    builder_result = RunResult(stdout=VALID_BUILDER_OUTPUT, stderr="", exit_code=0)
    reviewer_result = RunResult(stdout=VALID_REVIEWER_CHANGES_REQUESTED_OUTPUT, stderr="", exit_code=0)

    with patch("app.orchestrator.run_agent", side_effect=[builder_result, reviewer_result]):
        start_thread(thread.id, db_session)

    db_session.refresh(thread)
    assert thread.status == "waiting_for_user", (
        f"Expected 'waiting_for_user', got '{thread.status}'"
    )
    assert "Max review rounds reached" in (thread.last_error or ""), (
        f"Expected max rounds error, got: {thread.last_error}"
    )


# ---------------------------------------------------------------------------
# Test: subprocess failure moves thread to waiting_for_user
# ---------------------------------------------------------------------------


def test_subprocess_failure_moves_thread_to_non_running(db_session):
    """When run_agent returns exit_code != 0, thread should move to waiting_for_user."""
    thread = make_thread(db_session)

    failed_result = RunResult(
        stdout="",
        stderr="something went wrong",
        exit_code=1,
    )

    with patch("app.orchestrator.run_agent", return_value=failed_result):
        start_thread(thread.id, db_session)

    db_session.refresh(thread)
    assert thread.status == "waiting_for_user", (
        f"Expected 'waiting_for_user', got '{thread.status}'"
    )
    assert thread.last_error is not None, "Expected last_error to be set"


# ---------------------------------------------------------------------------
# Test: user note is consumed after first use (not re-injected)
# ---------------------------------------------------------------------------


def test_user_note_consumed_after_use(db_session):
    """get_latest_user_note returns the note text on first call and None on second call."""
    thread = make_thread(db_session)

    note = UserNote(thread_id=thread.id, note_text="Please focus on X")
    db_session.add(note)
    db_session.commit()

    # First call should return the note and mark it applied
    result1 = get_latest_user_note(thread.id, db_session)
    assert result1 == "Please focus on X", f"Expected note text, got: {result1}"

    # Second call should return None — note already consumed
    result2 = get_latest_user_note(thread.id, db_session)
    assert result2 is None, f"Expected None on second call, got: {result2}"


# ---------------------------------------------------------------------------
# Test: resume after pause between builder->reviewer handoff
# ---------------------------------------------------------------------------


def test_resume_after_pause_between_handoffs(db_session):
    """Resume a thread paused after builder finished (current_role already updated to reviewer).

    Simulates: builder finished READY_FOR_REVIEW, current_role was updated to 'reviewer'
    before the pause gate fired. resume_thread must dispatch to run_reviewer_turn,
    NOT re-run the builder.
    """
    # Create a thread that is paused with current_role="reviewer"
    # (builder already finished; pause gate fired before reviewer started)
    thread = make_thread(db_session, status="paused", current_role="reviewer")

    # Add a succeeded builder turn so the reviewer prompt can be built
    builder_turn = Turn(
        thread_id=thread.id,
        role="builder",
        sequence_number=1,
        prompt_text="build prompt",
        raw_output_text=VALID_BUILDER_OUTPUT,
        status="succeeded",
    )
    db_session.add(builder_turn)
    db_session.commit()

    reviewer_result = RunResult(stdout=VALID_REVIEWER_APPROVE_OUTPUT, stderr="", exit_code=0)

    with patch("app.orchestrator.run_agent", return_value=reviewer_result) as mock_agent:
        resume_thread(thread.id, db_session)

    # Exactly one agent call should have been made, and it must be for the reviewer command
    assert mock_agent.call_count == 1, f"Expected 1 agent call, got {mock_agent.call_count}"
    called_command = mock_agent.call_args[0][0]
    assert called_command == thread.reviewer_command, (
        f"Expected reviewer_command '{thread.reviewer_command}', got '{called_command}'"
    )

    # A reviewer Turn must have been created (sequence 2, since builder was 1)
    reviewer_turns = (
        db_session.query(Turn)
        .filter(Turn.thread_id == thread.id, Turn.role == "reviewer")
        .all()
    )
    assert len(reviewer_turns) == 1, f"Expected 1 reviewer turn, got {len(reviewer_turns)}"

    # No additional builder turn should have been created
    builder_turns = (
        db_session.query(Turn)
        .filter(Turn.thread_id == thread.id, Turn.role == "builder")
        .all()
    )
    assert len(builder_turns) == 1, (
        f"Expected 1 builder turn (pre-existing), got {len(builder_turns)}"
    )

    db_session.refresh(thread)
    assert thread.status == "done", f"Expected thread status 'done', got '{thread.status}'"


# ---------------------------------------------------------------------------
# Test: resume after pause between reviewer->builder handoff (CHANGES_REQUESTED)
# ---------------------------------------------------------------------------


def test_resume_after_reviewer_pause(db_session):
    """Resume a thread paused after reviewer returned CHANGES_REQUESTED (current_role updated to builder).

    Simulates: reviewer finished CHANGES_REQUESTED, round_count incremented,
    current_role updated to 'builder' before the pause gate fired.
    resume_thread must dispatch to run_builder_turn, NOT re-run the reviewer.
    """
    # Create a paused thread with current_role="builder" (reviewer already finished)
    thread = make_thread(
        db_session,
        status="paused",
        current_role="builder",
        round_count=1,
        max_rounds=3,
    )

    # Add a succeeded builder turn and a succeeded reviewer turn
    builder_turn = Turn(
        thread_id=thread.id,
        role="builder",
        sequence_number=1,
        prompt_text="build prompt",
        raw_output_text=VALID_BUILDER_OUTPUT,
        status="succeeded",
    )
    reviewer_turn = Turn(
        thread_id=thread.id,
        role="reviewer",
        sequence_number=2,
        prompt_text="review prompt",
        raw_output_text=VALID_REVIEWER_CHANGES_REQUESTED_OUTPUT,
        status="succeeded",
    )
    db_session.add(builder_turn)
    db_session.add(reviewer_turn)
    db_session.commit()

    # Mock: second builder call returns READY_FOR_REVIEW, then reviewer approves
    builder_result = RunResult(stdout=VALID_BUILDER_OUTPUT, stderr="", exit_code=0)
    reviewer_result = RunResult(stdout=VALID_REVIEWER_APPROVE_OUTPUT, stderr="", exit_code=0)

    with patch(
        "app.orchestrator.run_agent",
        side_effect=[builder_result, reviewer_result],
    ) as mock_agent:
        resume_thread(thread.id, db_session)

    # First call must be builder, second call must be reviewer
    assert mock_agent.call_count == 2, f"Expected 2 agent calls, got {mock_agent.call_count}"
    first_command = mock_agent.call_args_list[0][0][0]
    assert first_command == thread.builder_command, (
        f"Expected first call to be builder_command '{thread.builder_command}', got '{first_command}'"
    )
    second_command = mock_agent.call_args_list[1][0][0]
    assert second_command == thread.reviewer_command, (
        f"Expected second call to be reviewer_command '{thread.reviewer_command}', got '{second_command}'"
    )

    # A new builder turn (sequence 3) must have been created
    builder_turns = (
        db_session.query(Turn)
        .filter(Turn.thread_id == thread.id, Turn.role == "builder")
        .all()
    )
    assert len(builder_turns) == 2, f"Expected 2 builder turns total, got {len(builder_turns)}"

    db_session.refresh(thread)
    assert thread.status == "done", f"Expected thread status 'done', got '{thread.status}'"
