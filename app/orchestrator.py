"""Deterministic orchestrator for the ChatMasala builder/reviewer loop."""

import dataclasses
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.cli_runner import run_agent
from app.models import AgentProfile, Run, Turn, UserNote
from app.parser import parse_builder_output, parse_reviewer_output
from app.prompts import build_builder_prompt, build_reviewer_prompt, build_single_agent_prompt


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def get_next_sequence_number(run_id: int, db: Session) -> int:
    """Return the next sequence number for turns in the given run."""
    max_seq = db.query(func.max(Turn.sequence_number)).filter(
        Turn.run_id == run_id
    ).scalar()
    if max_seq is None:
        return 1
    return max_seq + 1


def get_latest_user_note(run_id: int, db: Session) -> Optional[str]:
    """Return the note_text of the most recently created unapplied UserNote, or None.

    Marks the note as applied so it is not re-injected on future turns.
    """
    note = (
        db.query(UserNote)
        .filter(UserNote.run_id == run_id, UserNote.applied == False)
        .order_by(UserNote.created_at.desc())
        .first()
    )
    if note:
        note.applied = True
        db.commit()
        return note.note_text
    return None


def _load_profile(db: Session, profile_id) -> Optional[AgentProfile]:
    """Load an AgentProfile by ID. Returns None if not found."""
    if not profile_id:
        return None
    return db.query(AgentProfile).filter(AgentProfile.id == profile_id).first()


def _get_command(profile: Optional[AgentProfile]) -> str:
    """Get the command template from a profile, or empty string."""
    if not profile:
        return ""
    return profile.command_template or ""


def _get_instruction_text(profile: Optional[AgentProfile]) -> str:
    """Read instruction file content from a profile. Returns empty string if unavailable."""
    if not profile or not profile.instruction_file:
        return ""
    try:
        with open(profile.instruction_file, "r") as f:
            return f.read()
    except (IOError, OSError):
        return ""


def _get_builder_command(run: Run, db: Session) -> str:
    """Resolve the builder command from the run's agent profile or return empty string."""
    profile = _load_profile(db, run.builder_agent_profile_id)
    if profile:
        return _get_command(profile)
    profile = _load_profile(db, run.primary_agent_profile_id)
    if profile:
        return _get_command(profile)
    return ""


def _get_reviewer_command(run: Run, db: Session) -> str:
    """Resolve the reviewer command from the run's agent profile or return empty string."""
    profile = _load_profile(db, run.reviewer_agent_profile_id)
    if profile:
        return _get_command(profile)
    return ""


# ---------------------------------------------------------------------------
# Core turn runners
# ---------------------------------------------------------------------------


def run_single_agent_turn(run_id: int, db: Session) -> None:
    """Execute one single-agent turn."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        return

    profile = _load_profile(db, run.primary_agent_profile_id)
    command = _get_command(profile)
    instruction_text = _get_instruction_text(profile)

    if not command:
        run.status = "failed"
        run.last_error = "No agent profile command configured."
        db.commit()
        return

    run.status = "running"
    run.current_role = "agent"
    db.commit()

    seq = get_next_sequence_number(run_id, db)
    prompt = build_single_agent_prompt(
        goal=run.goal,
        plan_text=run.plan_text,
        instruction_text=instruction_text,
    )

    turn = Turn(
        run_id=run_id,
        role="agent",
        sequence_number=seq,
        prompt_text=prompt,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(turn)
    db.commit()
    db.refresh(turn)

    result = run_agent(command=command, prompt=prompt, working_directory=run.workspace)

    turn.raw_output_text = result.stdout
    turn.ended_at = datetime.now(timezone.utc)

    if result.timed_out or result.error:
        turn.status = "failed"
        run.status = "failed"
        run.last_error = result.error or "Agent timed out."
        db.commit()
        return

    if result.exit_code != 0:
        turn.status = "failed"
        run.status = "failed"
        run.last_error = f"Agent exit code {result.exit_code}."
        db.commit()
        return

    parsed = parse_builder_output(result.stdout)
    if not parsed.success:
        turn.status = "done"
        run.status = "waiting_for_user"
        run.last_error = "Agent output could not be parsed. Check the structured output format."
        db.commit()
        return

    turn.parsed_json = json.dumps(dataclasses.asdict(parsed.data))
    turn.status = "done"
    run.status = "done"
    run.last_error = None
    run.current_role = None
    db.commit()


def run_builder_turn(run: Run, db: Session) -> None:
    """Execute one builder turn and route based on the result."""
    user_note = get_latest_user_note(run.id, db)

    # Get previous reviewer feedback (last succeeded reviewer turn)
    reviewer_turn = (
        db.query(Turn)
        .filter(
            Turn.run_id == run.id,
            Turn.role == "reviewer",
            Turn.status == "succeeded",
        )
        .order_by(Turn.sequence_number.desc())
        .first()
    )
    reviewer_feedback: Optional[str] = (
        reviewer_turn.raw_output_text if reviewer_turn else None
    )

    builder_profile = _load_profile(db, run.builder_agent_profile_id)
    builder_instruction = _get_instruction_text(builder_profile)

    prompt = build_builder_prompt(
        goal=run.goal,
        plan=run.plan_text or "",
        reviewer_feedback=reviewer_feedback,
        user_note=user_note,
        instruction_text=builder_instruction,
    )

    seq = get_next_sequence_number(run.id, db)
    turn = Turn(
        run_id=run.id,
        role="builder",
        sequence_number=seq,
        prompt_text=prompt,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(turn)
    db.commit()

    run.status = "waiting_for_agent"
    run.current_role = "builder"
    db.commit()

    builder_command = _get_builder_command(run, db)
    result = run_agent(builder_command, prompt, run.workspace)

    turn.raw_output_text = result.stdout
    turn.ended_at = datetime.now(timezone.utc)

    if result.error or result.exit_code != 0:
        turn.status = "process_failed"
        run.status = "waiting_for_user"
        run.last_error = result.error or f"Exit code {result.exit_code}: {result.stderr[:500]}"
        db.commit()
        return

    parse_result = parse_builder_output(result.stdout)

    if not parse_result.success:
        turn.status = "parse_failed"
        run.status = "waiting_for_user"
        run.last_error = parse_result.error
        db.commit()
        return

    turn.status = "succeeded"
    turn.parsed_json = json.dumps(dataclasses.asdict(parse_result.data))

    if parse_result.data.status == "BLOCKED":
        run.status = "waiting_for_user"
        run.last_error = f"Builder blocked: {parse_result.data.blockers}"
        db.commit()
        return

    # Update current_role to next role BEFORE the pause gate so that resume_thread
    # dispatches to the reviewer if we are paused here.
    run.current_role = "reviewer"
    db.commit()

    # Re-read run state before chaining — user may have paused while builder was running
    db.refresh(run)
    if run.status == "paused":
        return

    run_reviewer_turn(run, db)


def run_reviewer_turn(run: Run, db: Session) -> None:
    """Execute one reviewer turn and route based on the verdict."""
    # Get latest builder output from the last succeeded builder turn
    builder_turn = (
        db.query(Turn)
        .filter(
            Turn.run_id == run.id,
            Turn.role == "builder",
            Turn.status == "succeeded",
        )
        .order_by(Turn.sequence_number.desc())
        .first()
    )
    builder_output: str = builder_turn.raw_output_text if builder_turn else ""

    user_note = get_latest_user_note(run.id, db)

    reviewer_profile = _load_profile(db, run.reviewer_agent_profile_id)
    reviewer_instruction = _get_instruction_text(reviewer_profile)

    prompt = build_reviewer_prompt(
        goal=run.goal,
        plan=run.plan_text or "",
        builder_output=builder_output,
        user_note=user_note,
        instruction_text=reviewer_instruction,
    )

    seq = get_next_sequence_number(run.id, db)
    turn = Turn(
        run_id=run.id,
        role="reviewer",
        sequence_number=seq,
        prompt_text=prompt,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(turn)
    db.commit()

    run.status = "waiting_for_agent"
    run.current_role = "reviewer"
    db.commit()

    reviewer_command = _get_reviewer_command(run, db)
    result = run_agent(reviewer_command, prompt, run.workspace)

    turn.raw_output_text = result.stdout
    turn.ended_at = datetime.now(timezone.utc)

    if result.error or result.exit_code != 0:
        turn.status = "process_failed"
        run.status = "waiting_for_user"
        run.last_error = result.error or f"Exit code {result.exit_code}: {result.stderr[:500]}"
        db.commit()
        return

    parse_result = parse_reviewer_output(result.stdout)

    if not parse_result.success:
        turn.status = "parse_failed"
        run.status = "waiting_for_user"
        run.last_error = parse_result.error
        db.commit()
        return

    turn.status = "succeeded"
    turn.parsed_json = json.dumps(dataclasses.asdict(parse_result.data))

    verdict = parse_result.data.verdict

    if verdict == "APPROVE":
        run.status = "done"
        run.current_role = None
        db.commit()
        return

    if verdict == "BLOCKED":
        run.status = "waiting_for_user"
        run.last_error = f"Reviewer blocked: {parse_result.data.rationale}"
        db.commit()
        return

    # CHANGES_REQUESTED
    if not run.loop_enabled:
        # Loop disabled: always stop and wait for user input
        run.status = "waiting_for_user"
        run.last_error = "Changes requested. Loop disabled — waiting for user."
        db.commit()
        return

    if run.round_count >= run.max_rounds:
        run.status = "waiting_for_user"
        run.last_error = "Max review rounds reached"
        db.commit()
        return

    run.round_count += 1
    # Update current_role to next role BEFORE the pause gate so that resume_thread
    # dispatches to the builder if we are paused here.
    run.current_role = "builder"
    db.commit()

    # Re-read run state before chaining — user may have paused while reviewer was running
    db.refresh(run)
    if run.status == "paused":
        return

    run_builder_turn(run, db)


# ---------------------------------------------------------------------------
# Run lifecycle operations
# ---------------------------------------------------------------------------


def start_thread(run_id: int, db: Session) -> None:
    """Start a run from draft state. Runs synchronously (call via BackgroundTasks)."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if run is None:
        raise ValueError(f"Run {run_id} not found")
    if run.status != "draft":
        raise ValueError(f"Run is not in draft state (current status: {run.status})")

    if run.workflow_type == "single_agent":
        run_single_agent_turn(run_id, db)
    else:
        # builder_reviewer
        run.status = "running"
        run.current_role = "builder"
        db.commit()
        run_builder_turn(run, db)


def pause_thread(run_id: int, db: Session) -> Run:
    """Pause a running or waiting_for_agent run."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if run is None:
        raise ValueError(f"Run {run_id} not found")
    if run.status not in ("running", "waiting_for_agent"):
        raise ValueError(
            f"Cannot pause run in state '{run.status}'. "
            "Allowed from: running, waiting_for_agent"
        )

    run.status = "paused"
    db.commit()
    return run


def resume_thread(run_id: int, db: Session) -> Run:
    """Resume a paused run. Runs the appropriate next turn synchronously."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if run is None:
        raise ValueError(f"Run {run_id} not found")
    if run.status != "paused":
        raise ValueError(
            f"Cannot resume run in state '{run.status}'. Run must be paused."
        )

    run.status = "running"
    db.commit()

    # Determine what to run based on current_role
    if run.current_role == "reviewer":
        run_reviewer_turn(run, db)
    else:
        # current_role == "builder" or None: start with builder
        run_builder_turn(run, db)

    return run


def continue_thread(run_id: int, db: Session) -> None:
    """Continue a run that is waiting_for_user. Runs the appropriate next turn."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if run is None:
        raise ValueError(f"Run {run_id} not found")
    if run.status != "waiting_for_user":
        raise ValueError(
            f"Cannot continue run in state '{run.status}'. Run must be waiting_for_user."
        )

    run.status = "running"
    run.last_error = None
    db.commit()

    if run.current_role == "reviewer":
        run_reviewer_turn(run, db)
    else:
        run_builder_turn(run, db)


def stop_thread(run_id: int, db: Session) -> Run:
    """Stop a run and mark it as failed."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if run is None:
        raise ValueError(f"Run {run_id} not found")
    if run.status in ("done", "failed"):
        raise ValueError(
            f"Cannot stop run in terminal state '{run.status}'."
        )

    run.status = "failed"
    run.last_error = "Stopped by user"
    db.commit()
    return run


def add_user_note(run_id: int, note_text: str, db: Session) -> UserNote:
    """Add a user note to a run. Allowed from waiting_for_user, paused, or running."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if run is None:
        raise ValueError(f"Run {run_id} not found")

    allowed_states = ("waiting_for_user", "paused", "running")
    if run.status not in allowed_states:
        raise ValueError(
            f"Cannot add note to run in state '{run.status}'. "
            f"Allowed from: {', '.join(allowed_states)}"
        )

    note = UserNote(run_id=run_id, note_text=note_text)
    db.add(note)
    db.commit()
    return note
