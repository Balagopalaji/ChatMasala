"""Deterministic orchestrator for the ChatMasala builder/reviewer loop."""

import dataclasses
import json
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.cli_runner import run_agent
from app.models import Thread, Turn, UserNote
from app.parser import parse_builder_output, parse_reviewer_output
from app.prompts import build_builder_prompt, build_reviewer_prompt


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def get_next_sequence_number(thread_id: int, db: Session) -> int:
    """Return the next sequence number for turns in the given thread."""
    max_seq = db.query(func.max(Turn.sequence_number)).filter(
        Turn.thread_id == thread_id
    ).scalar()
    if max_seq is None:
        return 1
    return max_seq + 1


def get_latest_user_note(thread_id: int, db: Session) -> Optional[str]:
    """Return the note_text of the most recently created unapplied UserNote, or None.

    Marks the note as applied so it is not re-injected on future turns.
    """
    note = (
        db.query(UserNote)
        .filter(UserNote.thread_id == thread_id, UserNote.applied == False)
        .order_by(UserNote.created_at.desc())
        .first()
    )
    if note:
        note.applied = True
        db.commit()
        return note.note_text
    return None


# ---------------------------------------------------------------------------
# Core turn runners
# ---------------------------------------------------------------------------


def run_builder_turn(thread: Thread, db: Session) -> None:
    """Execute one builder turn and route based on the result."""
    user_note = get_latest_user_note(thread.id, db)

    # Get previous reviewer feedback (last succeeded reviewer turn)
    reviewer_turn = (
        db.query(Turn)
        .filter(
            Turn.thread_id == thread.id,
            Turn.role == "reviewer",
            Turn.status == "succeeded",
        )
        .order_by(Turn.sequence_number.desc())
        .first()
    )
    reviewer_feedback: Optional[str] = (
        reviewer_turn.raw_output_text if reviewer_turn else None
    )

    prompt = build_builder_prompt(
        thread.task_text, thread.plan_text, reviewer_feedback, user_note
    )

    seq = get_next_sequence_number(thread.id, db)
    turn = Turn(
        thread_id=thread.id,
        role="builder",
        sequence_number=seq,
        prompt_text=prompt,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(turn)
    db.commit()

    thread.status = "waiting_for_agent"
    thread.current_role = "builder"
    db.commit()

    result = run_agent(thread.builder_command, prompt, thread.working_directory)

    turn.raw_output_text = result.stdout
    turn.ended_at = datetime.now(timezone.utc)

    if result.error or result.exit_code != 0:
        turn.status = "process_failed"
        thread.status = "waiting_for_user"
        thread.last_error = result.error or f"Exit code {result.exit_code}: {result.stderr[:500]}"
        db.commit()
        return

    parse_result = parse_builder_output(result.stdout)

    if not parse_result.success:
        turn.status = "parse_failed"
        thread.status = "waiting_for_user"
        thread.last_error = parse_result.error
        db.commit()
        return

    turn.status = "succeeded"
    turn.parsed_json = json.dumps(dataclasses.asdict(parse_result.data))

    if parse_result.data.status == "BLOCKED":
        thread.status = "waiting_for_user"
        thread.last_error = f"Builder blocked: {parse_result.data.blockers}"
        db.commit()
        return

    # Update current_role to next role BEFORE the pause gate so that resume_thread
    # dispatches to the reviewer if we are paused here.
    thread.current_role = "reviewer"
    db.commit()

    # Re-read thread state before chaining — user may have paused while builder was running
    db.refresh(thread)
    if thread.status == "paused":
        return

    run_reviewer_turn(thread, db)


def run_reviewer_turn(thread: Thread, db: Session) -> None:
    """Execute one reviewer turn and route based on the verdict."""
    # Get latest builder output from the last succeeded builder turn
    builder_turn = (
        db.query(Turn)
        .filter(
            Turn.thread_id == thread.id,
            Turn.role == "builder",
            Turn.status == "succeeded",
        )
        .order_by(Turn.sequence_number.desc())
        .first()
    )
    builder_output: str = builder_turn.raw_output_text if builder_turn else ""

    user_note = get_latest_user_note(thread.id, db)

    prompt = build_reviewer_prompt(
        thread.task_text, thread.plan_text, builder_output, user_note
    )

    seq = get_next_sequence_number(thread.id, db)
    turn = Turn(
        thread_id=thread.id,
        role="reviewer",
        sequence_number=seq,
        prompt_text=prompt,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(turn)
    db.commit()

    thread.status = "waiting_for_agent"
    thread.current_role = "reviewer"
    db.commit()

    result = run_agent(thread.reviewer_command, prompt, thread.working_directory)

    turn.raw_output_text = result.stdout
    turn.ended_at = datetime.now(timezone.utc)

    if result.error or result.exit_code != 0:
        turn.status = "process_failed"
        thread.status = "waiting_for_user"
        thread.last_error = result.error or f"Exit code {result.exit_code}: {result.stderr[:500]}"
        db.commit()
        return

    parse_result = parse_reviewer_output(result.stdout)

    if not parse_result.success:
        turn.status = "parse_failed"
        thread.status = "waiting_for_user"
        thread.last_error = parse_result.error
        db.commit()
        return

    turn.status = "succeeded"
    turn.parsed_json = json.dumps(dataclasses.asdict(parse_result.data))

    verdict = parse_result.data.verdict

    if verdict == "APPROVE":
        thread.status = "done"
        thread.current_role = None
        db.commit()
        return

    if verdict == "BLOCKED":
        thread.status = "waiting_for_user"
        thread.last_error = f"Reviewer blocked: {parse_result.data.rationale}"
        db.commit()
        return

    # CHANGES_REQUESTED
    if thread.round_count >= thread.max_rounds:
        thread.status = "waiting_for_user"
        thread.last_error = "Max review rounds reached"
        db.commit()
        return

    thread.round_count += 1
    # Update current_role to next role BEFORE the pause gate so that resume_thread
    # dispatches to the builder if we are paused here.
    thread.current_role = "builder"
    db.commit()

    # Re-read thread state before chaining — user may have paused while reviewer was running
    db.refresh(thread)
    if thread.status == "paused":
        return

    run_builder_turn(thread, db)


# ---------------------------------------------------------------------------
# Thread lifecycle operations
# ---------------------------------------------------------------------------


def start_thread(thread_id: int, db: Session) -> None:
    """Start a thread from draft state. Runs synchronously (call via BackgroundTasks)."""
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if thread is None:
        raise ValueError(f"Thread {thread_id} not found")
    if thread.status != "draft":
        raise ValueError(f"Thread is not in draft state (current status: {thread.status})")

    thread.status = "running"
    db.commit()

    run_builder_turn(thread, db)


def pause_thread(thread_id: int, db: Session) -> Thread:
    """Pause a running or waiting_for_agent thread."""
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if thread is None:
        raise ValueError(f"Thread {thread_id} not found")
    if thread.status not in ("running", "waiting_for_agent"):
        raise ValueError(
            f"Cannot pause thread in state '{thread.status}'. "
            "Allowed from: running, waiting_for_agent"
        )

    thread.status = "paused"
    db.commit()
    return thread


def resume_thread(thread_id: int, db: Session) -> Thread:
    """Resume a paused thread. Runs the appropriate next turn synchronously."""
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if thread is None:
        raise ValueError(f"Thread {thread_id} not found")
    if thread.status != "paused":
        raise ValueError(
            f"Cannot resume thread in state '{thread.status}'. Thread must be paused."
        )

    thread.status = "running"
    db.commit()

    # Determine what to run based on current_role
    if thread.current_role == "reviewer":
        run_reviewer_turn(thread, db)
    else:
        # current_role == "builder" or None: start with builder
        run_builder_turn(thread, db)

    return thread


def continue_thread(thread_id: int, db: Session) -> None:
    """Continue a thread that is waiting_for_user. Runs the appropriate next turn."""
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if thread is None:
        raise ValueError(f"Thread {thread_id} not found")
    if thread.status != "waiting_for_user":
        raise ValueError(
            f"Cannot continue thread in state '{thread.status}'. Thread must be waiting_for_user."
        )

    thread.status = "running"
    thread.last_error = None
    db.commit()

    if thread.current_role == "reviewer":
        run_reviewer_turn(thread, db)
    else:
        run_builder_turn(thread, db)


def stop_thread(thread_id: int, db: Session) -> Thread:
    """Stop a thread and mark it as failed."""
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if thread is None:
        raise ValueError(f"Thread {thread_id} not found")
    if thread.status in ("done", "failed"):
        raise ValueError(
            f"Cannot stop thread in terminal state '{thread.status}'."
        )

    thread.status = "failed"
    thread.last_error = "Stopped by user"
    db.commit()
    return thread


def add_user_note(thread_id: int, note_text: str, db: Session) -> UserNote:
    """Add a user note to a thread. Allowed from waiting_for_user, paused, or running."""
    thread = db.query(Thread).filter(Thread.id == thread_id).first()
    if thread is None:
        raise ValueError(f"Thread {thread_id} not found")

    allowed_states = ("waiting_for_user", "paused", "running")
    if thread.status not in allowed_states:
        raise ValueError(
            f"Cannot add note to thread in state '{thread.status}'. "
            f"Allowed from: {', '.join(allowed_states)}"
        )

    note = UserNote(thread_id=thread_id, note_text=note_text)
    db.add(note)
    db.commit()
    return note
