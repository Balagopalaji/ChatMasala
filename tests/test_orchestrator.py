"""Tests for app/orchestrator.py — deterministic routing logic."""

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.cli_runner import RunResult
from app.db import Base
from app.models import AgentProfile, Run, Turn, UserNote
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


def make_run(db_session, **kwargs) -> Run:
    """Create and persist a draft run with sensible defaults."""
    defaults = dict(
        title="Test Run",
        goal="Build something.",
        plan_text="1. Do it.",
        max_rounds=3,
        workflow_type="builder_reviewer",
    )
    defaults.update(kwargs)
    run = Run(**defaults)
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


def make_agent_profile(db_session, **kwargs) -> AgentProfile:
    """Create and persist an AgentProfile with sensible defaults."""
    defaults = dict(
        name="Test Agent",
        provider="test",
        command_template="echo hello",
        instruction_file="",
    )
    defaults.update(kwargs)
    profile = AgentProfile(**defaults)
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# Test: builder success routes to reviewer
# ---------------------------------------------------------------------------


def test_orchestrator_routes_builder_success_to_reviewer(db_session):
    """When builder returns READY_FOR_REVIEW, a reviewer Turn must be created."""
    run = make_run(db_session)

    builder_result = RunResult(stdout=VALID_BUILDER_OUTPUT, stderr="", exit_code=0)
    reviewer_result = RunResult(stdout=VALID_REVIEWER_APPROVE_OUTPUT, stderr="", exit_code=0)

    side_effects = [builder_result, reviewer_result]

    with patch("app.orchestrator.run_agent", side_effect=side_effects):
        start_thread(run.id, db_session)

    turns = (
        db_session.query(Turn)
        .filter(Turn.run_id == run.id)
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
    """Full loop: builder READY_FOR_REVIEW, reviewer APPROVE => run.status == 'done'."""
    run = make_run(db_session)

    builder_result = RunResult(stdout=VALID_BUILDER_OUTPUT, stderr="", exit_code=0)
    reviewer_result = RunResult(stdout=VALID_REVIEWER_APPROVE_OUTPUT, stderr="", exit_code=0)

    with patch("app.orchestrator.run_agent", side_effect=[builder_result, reviewer_result]):
        start_thread(run.id, db_session)

    db_session.refresh(run)
    assert run.status == "done", f"Expected 'done', got '{run.status}'"


# ---------------------------------------------------------------------------
# Test: reviewer CHANGES_REQUESTED increments round and creates new builder turn
# ---------------------------------------------------------------------------


def test_orchestrator_routes_reviewer_changes_requested_back_to_builder(db_session):
    """Reviewer CHANGES_REQUESTED with rounds remaining: round_count increments and a new builder Turn is created."""
    run = make_run(db_session, max_rounds=3, loop_enabled=True)

    builder_result_1 = RunResult(stdout=VALID_BUILDER_OUTPUT, stderr="", exit_code=0)
    reviewer_result = RunResult(stdout=VALID_REVIEWER_CHANGES_REQUESTED_OUTPUT, stderr="", exit_code=0)
    # Second builder call after changes requested — approve on second reviewer pass
    builder_result_2 = RunResult(stdout=VALID_BUILDER_OUTPUT, stderr="", exit_code=0)
    reviewer_result_2 = RunResult(stdout=VALID_REVIEWER_APPROVE_OUTPUT, stderr="", exit_code=0)

    with patch(
        "app.orchestrator.run_agent",
        side_effect=[builder_result_1, reviewer_result, builder_result_2, reviewer_result_2],
    ):
        start_thread(run.id, db_session)

    db_session.refresh(run)

    # round_count should have been incremented at least once
    assert run.round_count >= 1, f"Expected round_count >= 1, got {run.round_count}"

    # There should be at least 2 builder turns
    builder_turns = (
        db_session.query(Turn)
        .filter(Turn.run_id == run.id, Turn.role == "builder")
        .all()
    )
    assert len(builder_turns) >= 2, f"Expected >=2 builder turns, got {len(builder_turns)}"


# ---------------------------------------------------------------------------
# Test: stops at max rounds
# ---------------------------------------------------------------------------


def test_orchestrator_stops_at_max_rounds(db_session):
    """With max_rounds=0 and loop_enabled=True, a single CHANGES_REQUESTED => waiting_for_user.

    round_count starts at 0. The check is round_count >= max_rounds before
    incrementing, so max_rounds=0 means no extra builder cycles allowed.
    """
    run = make_run(db_session, max_rounds=0, loop_enabled=True)

    builder_result = RunResult(stdout=VALID_BUILDER_OUTPUT, stderr="", exit_code=0)
    reviewer_result = RunResult(stdout=VALID_REVIEWER_CHANGES_REQUESTED_OUTPUT, stderr="", exit_code=0)

    with patch("app.orchestrator.run_agent", side_effect=[builder_result, reviewer_result]):
        start_thread(run.id, db_session)

    db_session.refresh(run)
    assert run.status == "waiting_for_user", (
        f"Expected 'waiting_for_user', got '{run.status}'"
    )
    assert "Max review rounds reached" in (run.last_error or ""), (
        f"Expected max rounds error, got: {run.last_error}"
    )


# ---------------------------------------------------------------------------
# Test: subprocess failure moves run to waiting_for_user
# ---------------------------------------------------------------------------


def test_subprocess_failure_moves_run_to_non_running(db_session):
    """When run_agent returns exit_code != 0, run should move to waiting_for_user."""
    run = make_run(db_session)

    failed_result = RunResult(
        stdout="",
        stderr="something went wrong",
        exit_code=1,
    )

    with patch("app.orchestrator.run_agent", return_value=failed_result):
        start_thread(run.id, db_session)

    db_session.refresh(run)
    assert run.status == "waiting_for_user", (
        f"Expected 'waiting_for_user', got '{run.status}'"
    )
    assert run.last_error is not None, "Expected last_error to be set"


# ---------------------------------------------------------------------------
# Test: user note is consumed after first use (not re-injected)
# ---------------------------------------------------------------------------


def test_user_note_consumed_after_use(db_session):
    """get_latest_user_note returns the note text on first call and None on second call."""
    run = make_run(db_session)

    note = UserNote(run_id=run.id, note_text="Please focus on X")
    db_session.add(note)
    db_session.commit()

    # First call should return the note and mark it applied
    result1 = get_latest_user_note(run.id, db_session)
    assert result1 == "Please focus on X", f"Expected note text, got: {result1}"

    # Second call should return None — note already consumed
    result2 = get_latest_user_note(run.id, db_session)
    assert result2 is None, f"Expected None on second call, got: {result2}"


# ---------------------------------------------------------------------------
# Test: resume after pause between builder->reviewer handoff
# ---------------------------------------------------------------------------


def test_resume_after_pause_between_handoffs(db_session):
    """Resume a run paused after builder finished (current_role already updated to reviewer).

    Simulates: builder finished READY_FOR_REVIEW, current_role was updated to 'reviewer'
    before the pause gate fired. resume_thread must dispatch to run_reviewer_turn,
    NOT re-run the builder.
    """
    # Create a run that is paused with current_role="reviewer"
    # (builder already finished; pause gate fired before reviewer started)
    run = make_run(db_session, status="paused", current_role="reviewer")

    # Add a succeeded builder turn so the reviewer prompt can be built
    builder_turn = Turn(
        run_id=run.id,
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
        resume_thread(run.id, db_session)

    # Exactly one agent call should have been made (for reviewer)
    assert mock_agent.call_count == 1, f"Expected 1 agent call, got {mock_agent.call_count}"

    # A reviewer Turn must have been created (sequence 2, since builder was 1)
    reviewer_turns = (
        db_session.query(Turn)
        .filter(Turn.run_id == run.id, Turn.role == "reviewer")
        .all()
    )
    assert len(reviewer_turns) == 1, f"Expected 1 reviewer turn, got {len(reviewer_turns)}"

    # No additional builder turn should have been created
    builder_turns = (
        db_session.query(Turn)
        .filter(Turn.run_id == run.id, Turn.role == "builder")
        .all()
    )
    assert len(builder_turns) == 1, (
        f"Expected 1 builder turn (pre-existing), got {len(builder_turns)}"
    )

    db_session.refresh(run)
    assert run.status == "done", f"Expected run status 'done', got '{run.status}'"


# ---------------------------------------------------------------------------
# Test: resume after pause between reviewer->builder handoff (CHANGES_REQUESTED)
# ---------------------------------------------------------------------------


def test_resume_after_reviewer_pause(db_session):
    """Resume a run paused after reviewer returned CHANGES_REQUESTED (current_role updated to builder).

    Simulates: reviewer finished CHANGES_REQUESTED, round_count incremented,
    current_role updated to 'builder' before the pause gate fired.
    resume_thread must dispatch to run_builder_turn, NOT re-run the reviewer.
    """
    # Create a paused run with current_role="builder" (reviewer already finished)
    run = make_run(
        db_session,
        status="paused",
        current_role="builder",
        round_count=1,
        max_rounds=3,
    )

    # Add a succeeded builder turn and a succeeded reviewer turn
    builder_turn = Turn(
        run_id=run.id,
        role="builder",
        sequence_number=1,
        prompt_text="build prompt",
        raw_output_text=VALID_BUILDER_OUTPUT,
        status="succeeded",
    )
    reviewer_turn = Turn(
        run_id=run.id,
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
        resume_thread(run.id, db_session)

    # Two agent calls: builder then reviewer
    assert mock_agent.call_count == 2, f"Expected 2 agent calls, got {mock_agent.call_count}"

    # A new builder turn (sequence 3) must have been created
    builder_turns = (
        db_session.query(Turn)
        .filter(Turn.run_id == run.id, Turn.role == "builder")
        .all()
    )
    assert len(builder_turns) == 2, f"Expected 2 builder turns total, got {len(builder_turns)}"

    db_session.refresh(run)
    assert run.status == "done", f"Expected run status 'done', got '{run.status}'"


# ---------------------------------------------------------------------------
# Test: single_agent workflow success
# ---------------------------------------------------------------------------


def test_single_agent_run_success(db_session):
    """single_agent workflow: run completes with status 'done' after one agent turn."""
    profile = make_agent_profile(db_session, command_template="echo hello")
    run = Run(
        title="test",
        goal="Write hello world",
        workflow_type="single_agent",
        status="draft",
        primary_agent_profile_id=profile.id,
        max_rounds=3,
    )
    db_session.add(run)
    db_session.commit()

    success_result = RunResult(stdout=VALID_BUILDER_OUTPUT, stderr="", exit_code=0)

    with patch("app.orchestrator.run_agent", return_value=success_result):
        start_thread(run.id, db_session)

    db_session.refresh(run)
    assert run.status == "done", f"Expected 'done', got '{run.status}'"

    turns = db_session.query(Turn).filter(Turn.run_id == run.id).all()
    assert len(turns) == 1, f"Expected 1 turn, got {len(turns)}"
    assert turns[0].role == "agent"


def test_single_agent_run_no_profile_fails(db_session):
    """single_agent workflow with no profile: run fails with an error message."""
    run = Run(
        title="test",
        goal="Write hello world",
        workflow_type="single_agent",
        status="draft",
        max_rounds=3,
    )
    db_session.add(run)
    db_session.commit()

    start_thread(run.id, db_session)

    db_session.refresh(run)
    assert run.status == "failed", f"Expected 'failed', got '{run.status}'"
    assert run.last_error is not None


# ---------------------------------------------------------------------------
# Test: builder_reviewer loop_enabled=False stops at CHANGES_REQUESTED
# ---------------------------------------------------------------------------


def test_builder_reviewer_loop_disabled_stops_at_changes(db_session):
    """With loop_enabled=False and CHANGES_REQUESTED verdict, run waits for user."""
    run = make_run(
        db_session,
        goal="Build feature",
        workflow_type="builder_reviewer",
        loop_enabled=False,
        max_rounds=3,
        status="draft",
    )

    builder_result = RunResult(stdout=VALID_BUILDER_OUTPUT, stderr="", exit_code=0)
    reviewer_result = RunResult(stdout=VALID_REVIEWER_CHANGES_REQUESTED_OUTPUT, stderr="", exit_code=0)

    with patch("app.orchestrator.run_agent", side_effect=[builder_result, reviewer_result]):
        start_thread(run.id, db_session)

    db_session.refresh(run)
    assert run.status == "waiting_for_user", (
        f"Expected 'waiting_for_user', got '{run.status}'"
    )


def test_single_agent_nonzero_exit_marks_failed(db_session):
    """Non-zero exit code must mark run as failed, not done."""
    profile = make_agent_profile(db_session, command_template="echo hello")
    run = Run(title="t", goal="g", workflow_type="single_agent", status="draft", primary_agent_profile_id=profile.id)
    db_session.add(run)
    db_session.commit()

    mock_result = RunResult(stdout="", stderr="error", exit_code=1, timed_out=False, error=None)
    with patch("app.orchestrator.run_agent", return_value=mock_result):
        start_thread(run.id, db_session)

    db_session.refresh(run)
    assert run.status == "failed"
    assert "exit code 1" in run.last_error.lower()


def test_single_agent_parse_failure_sets_waiting_for_user(db_session):
    """Unparseable output must set status to waiting_for_user, not done."""
    profile = make_agent_profile(db_session, command_template="echo hello")
    run = Run(title="t", goal="g", workflow_type="single_agent", status="draft", primary_agent_profile_id=profile.id)
    db_session.add(run)
    db_session.commit()

    mock_result = RunResult(stdout="This is not structured output", stderr="", exit_code=0, timed_out=False, error=None)
    with patch("app.orchestrator.run_agent", return_value=mock_result):
        start_thread(run.id, db_session)

    db_session.refresh(run)
    assert run.status == "waiting_for_user"
    assert run.last_error is not None


def test_builder_prompt_includes_profile_instruction(db_session):
    """build_builder_prompt must receive and include profile instruction text."""
    from app.prompts import build_builder_prompt
    prompt = build_builder_prompt(
        goal="Fix the bug",
        instruction_text="# Custom Builder Instructions\nAlways write tests.",
    )
    assert "Custom Builder Instructions" in prompt
    assert "Fix the bug" in prompt


def test_reviewer_prompt_includes_profile_instruction(db_session):
    """build_reviewer_prompt must receive and include profile instruction text."""
    from app.prompts import build_reviewer_prompt
    prompt = build_reviewer_prompt(
        goal="Fix the bug",
        builder_output="Done",
        instruction_text="# Custom Reviewer Instructions\nBe strict.",
    )
    assert "Custom Reviewer Instructions" in prompt


def test_builder_reviewer_loop_enabled_loops_back(db_session):
    """With loop_enabled=True and rounds remaining, CHANGES_REQUESTED loops back to builder."""
    run = make_run(
        db_session,
        goal="Build feature",
        workflow_type="builder_reviewer",
        loop_enabled=True,
        max_rounds=3,
        status="draft",
    )

    builder_result_1 = RunResult(stdout=VALID_BUILDER_OUTPUT, stderr="", exit_code=0)
    reviewer_changes = RunResult(stdout=VALID_REVIEWER_CHANGES_REQUESTED_OUTPUT, stderr="", exit_code=0)
    builder_result_2 = RunResult(stdout=VALID_BUILDER_OUTPUT, stderr="", exit_code=0)
    reviewer_approve = RunResult(stdout=VALID_REVIEWER_APPROVE_OUTPUT, stderr="", exit_code=0)

    with patch(
        "app.orchestrator.run_agent",
        side_effect=[builder_result_1, reviewer_changes, builder_result_2, reviewer_approve],
    ):
        start_thread(run.id, db_session)

    db_session.refresh(run)
    assert run.status == "done", f"Expected 'done', got '{run.status}'"
    assert run.round_count >= 1


# ---------------------------------------------------------------------------
# Test: single_agent run with real single-agent.md contract output
# ---------------------------------------------------------------------------


def test_single_agent_run_with_real_contract_output(db_session):
    """Output matching the shipped single-agent.md contract must parse and complete the run."""
    valid_output = (
        "===STRUCTURED_OUTPUT===\n"
        "STATUS: READY_FOR_REVIEW\n"
        "SUMMARY: Completed the task\n"
        "CHANGED_ARTIFACTS: main.py\n"
        "CHECKS_RUN: pytest\n"
        "BLOCKERS: none\n"
        "HANDOFF_NOTE: All done\n"
        "===END_STRUCTURED_OUTPUT==="
    )
    profile = make_agent_profile(db_session, name="single-agent-contract-test", command_template="echo hello")
    run = Run(title="t", goal="g", workflow_type="single_agent", status="draft", primary_agent_profile_id=profile.id)
    db_session.add(run)
    db_session.commit()

    mock_result = RunResult(stdout=valid_output, stderr="", exit_code=0, timed_out=False, error=None)
    with patch("app.orchestrator.run_agent", return_value=mock_result):
        start_thread(run.id, db_session)

    db_session.refresh(run)
    assert run.status == "done", f"Expected done, got {run.status} (last_error: {run.last_error})"
