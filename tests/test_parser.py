"""Tests for app/parser.py — structured output parsing."""

from app.parser import (
    BuilderOutput,
    ReviewerOutput,
    parse_builder_output,
    parse_reviewer_output,
)
from app.prompts import build_single_agent_prompt

# ---------------------------------------------------------------------------
# Fixtures: valid structured output strings
# ---------------------------------------------------------------------------

VALID_BUILDER_TEXT = """\
Some preamble text from the builder.

===STRUCTURED_OUTPUT===
STATUS: READY_FOR_REVIEW
SUMMARY: Implemented the feature as described.
CHANGED_ARTIFACTS: app/models.py, app/schemas.py
CHECKS_RUN: pytest=PASS, mypy=PASS
BLOCKERS: none
HANDOFF_NOTE: All changes are ready for review.
===END_STRUCTURED_OUTPUT===
"""

VALID_REVIEWER_TEXT = """\
Some preamble from the reviewer.

===STRUCTURED_OUTPUT===
VERDICT: APPROVE
SUMMARY: Changes look correct and complete.
OPEN_ISSUES: none
CHECKS_VERIFIED: pytest=PASS, mypy=PASS
NEXT_ACTION: close_thread
RATIONALE: All acceptance criteria are met.
===END_STRUCTURED_OUTPUT===
"""


# ---------------------------------------------------------------------------
# Builder output tests
# ---------------------------------------------------------------------------


def test_parse_builder_output_valid():
    result = parse_builder_output(VALID_BUILDER_TEXT)
    assert result.success is True
    assert result.error is None
    assert isinstance(result.data, BuilderOutput)
    assert result.data.status == "READY_FOR_REVIEW"
    assert result.data.summary == "Implemented the feature as described."
    assert result.data.handoff_note == "All changes are ready for review."


def test_parse_builder_output_missing_block():
    result = parse_builder_output("This text has no structured output block at all.")
    assert result.success is False
    assert result.data is None
    assert "No structured output block found" in result.error


def test_parse_builder_output_invalid_status():
    text = """\
===STRUCTURED_OUTPUT===
STATUS: GARBAGE
SUMMARY: Something happened.
CHANGED_ARTIFACTS: none
CHECKS_RUN: pytest=PASS
BLOCKERS: none
HANDOFF_NOTE: Nothing to say.
===END_STRUCTURED_OUTPUT===
"""
    result = parse_builder_output(text)
    assert result.success is False
    assert result.data is None
    assert "GARBAGE" in result.error or "Invalid STATUS" in result.error


def test_parse_builder_output_missing_field():
    # Omit HANDOFF_NOTE
    text = """\
===STRUCTURED_OUTPUT===
STATUS: READY_FOR_REVIEW
SUMMARY: Done.
CHANGED_ARTIFACTS: none
CHECKS_RUN: pytest=PASS
BLOCKERS: none
===END_STRUCTURED_OUTPUT===
"""
    result = parse_builder_output(text)
    assert result.success is False
    assert result.data is None
    assert "HANDOFF_NOTE" in result.error


def test_parse_builder_output_blocked_status():
    text = """\
===STRUCTURED_OUTPUT===
STATUS: BLOCKED
SUMMARY: Cannot proceed.
CHANGED_ARTIFACTS: none
CHECKS_RUN: NOT_RUN
BLOCKERS: Missing dependency.
HANDOFF_NOTE: Needs human intervention.
===END_STRUCTURED_OUTPUT===
"""
    result = parse_builder_output(text)
    assert result.success is True
    assert result.data.status == "BLOCKED"


# ---------------------------------------------------------------------------
# Reviewer output tests
# ---------------------------------------------------------------------------


def test_parse_reviewer_output_valid():
    result = parse_reviewer_output(VALID_REVIEWER_TEXT)
    assert result.success is True
    assert result.error is None
    assert isinstance(result.data, ReviewerOutput)
    assert result.data.verdict == "APPROVE"
    assert result.data.next_action == "close_thread"
    assert result.data.rationale == "All acceptance criteria are met."


def test_parse_reviewer_output_missing_block():
    result = parse_reviewer_output("No markers here, just plain text.")
    assert result.success is False
    assert result.data is None
    assert "No structured output block found" in result.error


def test_parse_reviewer_output_invalid_verdict():
    text = """\
===STRUCTURED_OUTPUT===
VERDICT: INVALID_VALUE
SUMMARY: Something.
OPEN_ISSUES: none
CHECKS_VERIFIED: pytest=PASS
NEXT_ACTION: reroute_builder
RATIONALE: Just testing.
===END_STRUCTURED_OUTPUT===
"""
    result = parse_reviewer_output(text)
    assert result.success is False
    assert result.data is None
    assert "INVALID_VALUE" in result.error or "Invalid VERDICT" in result.error


def test_parse_reviewer_output_changes_requested():
    text = """\
===STRUCTURED_OUTPUT===
VERDICT: CHANGES_REQUESTED
SUMMARY: There are issues.
OPEN_ISSUES: Function X lacks error handling.
CHECKS_VERIFIED: pytest=FAIL
NEXT_ACTION: reroute_builder
RATIONALE: Needs fixes before approval.
===END_STRUCTURED_OUTPUT===
"""
    result = parse_reviewer_output(text)
    assert result.success is True
    assert result.data.verdict == "CHANGES_REQUESTED"
    assert result.data.next_action == "reroute_builder"


def test_parse_reviewer_output_missing_field():
    # Omit RATIONALE
    text = """\
===STRUCTURED_OUTPUT===
VERDICT: APPROVE
SUMMARY: Good.
OPEN_ISSUES: none
CHECKS_VERIFIED: pytest=PASS
NEXT_ACTION: close_thread
===END_STRUCTURED_OUTPUT===
"""
    result = parse_reviewer_output(text)
    assert result.success is False
    assert result.data is None
    assert "RATIONALE" in result.error


# ---------------------------------------------------------------------------
# build_single_agent_prompt tests
# ---------------------------------------------------------------------------


def test_build_single_agent_prompt_includes_goal():
    prompt = build_single_agent_prompt(goal="Fix the bug")
    assert "Fix the bug" in prompt


def test_build_single_agent_prompt_includes_plan_text():
    prompt = build_single_agent_prompt(goal="Fix the bug", plan_text="Step 1: reproduce it.")
    assert "Fix the bug" in prompt
    assert "Step 1: reproduce it." in prompt


def test_build_single_agent_prompt_includes_instruction_text():
    prompt = build_single_agent_prompt(
        goal="Write tests",
        instruction_text="You are a senior QA engineer.",
    )
    assert "You are a senior QA engineer." in prompt
    assert "Write tests" in prompt


def test_build_single_agent_prompt_no_plan_omits_plan_section():
    prompt = build_single_agent_prompt(goal="Do something")
    assert "Plan / Constraints" not in prompt


def test_build_single_agent_prompt_no_instruction_omits_instruction():
    prompt = build_single_agent_prompt(goal="Do something")
    # Prompt should start with the Goal section, not empty instruction content
    assert prompt.startswith("## Goal")


def test_parse_builder_output_single_agent_contract():
    """Output matching the shipped single-agent.md contract must parse successfully."""
    output = (
        "===STRUCTURED_OUTPUT===\n"
        "STATUS: READY_FOR_REVIEW\n"
        "SUMMARY: Completed the task\n"
        "CHANGED_ARTIFACTS: main.py\n"
        "CHECKS_RUN: pytest\n"
        "BLOCKERS: none\n"
        "HANDOFF_NOTE: All done\n"
        "===END_STRUCTURED_OUTPUT==="
    )
    result = parse_builder_output(output)
    assert result is not None
    assert result.success is True
    assert result.data.status == "READY_FOR_REVIEW"
