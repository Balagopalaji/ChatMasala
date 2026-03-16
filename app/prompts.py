"""Prompt construction functions for builder and reviewer turns."""

from typing import Optional

# ---------------------------------------------------------------------------
# Output contracts (embedded verbatim in prompts)
# ---------------------------------------------------------------------------

BUILDER_OUTPUT_CONTRACT = """===STRUCTURED_OUTPUT===
STATUS: READY_FOR_REVIEW|BLOCKED
SUMMARY: <short text>
CHANGED_ARTIFACTS: <paths or none>
CHECKS_RUN: <name>=PASS|FAIL|NOT_RUN ...
BLOCKERS: <text or none>
HANDOFF_NOTE: <short reviewer-oriented note>
===END_STRUCTURED_OUTPUT==="""

REVIEWER_OUTPUT_CONTRACT = """===STRUCTURED_OUTPUT===
VERDICT: APPROVE|CHANGES_REQUESTED|BLOCKED
SUMMARY: <short text>
OPEN_ISSUES: <short text or none>
CHECKS_VERIFIED: <name>=PASS|FAIL|NOT_RUN ...
NEXT_ACTION: reroute_builder|wait_for_user|close_thread
RATIONALE: <short text>
===END_STRUCTURED_OUTPUT==="""


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def build_builder_prompt(
    task: str,
    plan: str,
    reviewer_feedback: Optional[str] = None,
    user_note: Optional[str] = None,
) -> str:
    """Build the full prompt text to send to the builder agent.

    Sections included (in order):
    1. Role statement
    2. Task
    3. Plan
    4. Latest reviewer feedback (if present)
    5. Latest user note (if present)
    6. Builder output contract
    """
    parts: list[str] = []

    parts.append("You are the builder.")
    parts.append("")

    parts.append("## Task")
    parts.append(task.strip())
    parts.append("")

    parts.append("## Plan")
    parts.append(plan.strip())
    parts.append("")

    if reviewer_feedback is not None:
        parts.append("## Reviewer Feedback")
        parts.append(reviewer_feedback.strip())
        parts.append("")

    if user_note is not None:
        parts.append("## User Note")
        parts.append(user_note.strip())
        parts.append("")

    parts.append("## Required Output Format")
    parts.append(
        "You MUST end your response with the following structured output block "
        "(fill in each field; do not omit any field):"
    )
    parts.append("")
    parts.append(BUILDER_OUTPUT_CONTRACT)

    return "\n".join(parts)


def build_reviewer_prompt(
    task: str,
    plan: str,
    builder_output: str,
    user_note: Optional[str] = None,
) -> str:
    """Build the full prompt text to send to the reviewer agent.

    Sections included (in order):
    1. Role statement
    2. Task
    3. Plan
    4. Latest builder output
    5. Latest user note (if present)
    6. Reviewer output contract
    """
    parts: list[str] = []

    parts.append("You are the reviewer.")
    parts.append("")

    parts.append("## Task")
    parts.append(task.strip())
    parts.append("")

    parts.append("## Plan")
    parts.append(plan.strip())
    parts.append("")

    parts.append("## Builder Output")
    parts.append(builder_output.strip())
    parts.append("")

    if user_note is not None:
        parts.append("## User Note")
        parts.append(user_note.strip())
        parts.append("")

    parts.append("## Required Output Format")
    parts.append(
        "You MUST end your response with the following structured output block "
        "(fill in each field; do not omit any field):"
    )
    parts.append("")
    parts.append(REVIEWER_OUTPUT_CONTRACT)

    return "\n".join(parts)
