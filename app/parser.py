"""Structured output parser for builder and reviewer agent contracts."""

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class BuilderOutput:
    status: str           # READY_FOR_REVIEW | BLOCKED
    summary: str
    changed_artifacts: str
    checks_run: str
    blockers: str
    handoff_note: str


@dataclass
class ReviewerOutput:
    verdict: str          # APPROVE | CHANGES_REQUESTED | BLOCKED
    summary: str
    open_issues: str
    checks_verified: str
    next_action: str      # reroute_builder | wait_for_user | close_thread
    rationale: str


@dataclass
class ParseResult:
    success: bool
    data: Optional[BuilderOutput | ReviewerOutput]
    error: Optional[str]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_START_MARKER = "===STRUCTURED_OUTPUT==="
_END_MARKER = "===END_STRUCTURED_OUTPUT==="

_BUILDER_REQUIRED_FIELDS = [
    "STATUS",
    "SUMMARY",
    "CHANGED_ARTIFACTS",
    "CHECKS_RUN",
    "BLOCKERS",
    "HANDOFF_NOTE",
]

_REVIEWER_REQUIRED_FIELDS = [
    "VERDICT",
    "SUMMARY",
    "OPEN_ISSUES",
    "CHECKS_VERIFIED",
    "NEXT_ACTION",
    "RATIONALE",
]

_VALID_BUILDER_STATUSES = {"READY_FOR_REVIEW", "BLOCKED"}
_VALID_REVIEWER_VERDICTS = {"APPROVE", "CHANGES_REQUESTED", "BLOCKED"}


def _extract_block(text: str) -> Optional[str]:
    """Return the text between the structured output markers, or None."""
    start = text.find(_START_MARKER)
    end = text.find(_END_MARKER)
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start + len(_START_MARKER):end]


def _parse_fields(block: str) -> dict[str, str]:
    """Parse KEY: value lines from the block. Values are stripped."""
    fields: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    return fields


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_builder_output(text: str) -> ParseResult:
    """Parse the structured output block from a builder agent response."""
    block = _extract_block(text)
    if block is None:
        return ParseResult(success=False, data=None, error="No structured output block found")

    fields = _parse_fields(block)

    for required in _BUILDER_REQUIRED_FIELDS:
        if required not in fields:
            return ParseResult(success=False, data=None, error=f"Missing field: {required}")

    status = fields["STATUS"]
    if status not in _VALID_BUILDER_STATUSES:
        return ParseResult(
            success=False,
            data=None,
            error=f"Invalid STATUS value: {status!r}. Must be one of {sorted(_VALID_BUILDER_STATUSES)}",
        )

    output = BuilderOutput(
        status=status,
        summary=fields["SUMMARY"],
        changed_artifacts=fields["CHANGED_ARTIFACTS"],
        checks_run=fields["CHECKS_RUN"],
        blockers=fields["BLOCKERS"],
        handoff_note=fields["HANDOFF_NOTE"],
    )
    return ParseResult(success=True, data=output, error=None)


def parse_reviewer_output(text: str) -> ParseResult:
    """Parse the structured output block from a reviewer agent response."""
    block = _extract_block(text)
    if block is None:
        return ParseResult(success=False, data=None, error="No structured output block found")

    fields = _parse_fields(block)

    for required in _REVIEWER_REQUIRED_FIELDS:
        if required not in fields:
            return ParseResult(success=False, data=None, error=f"Missing field: {required}")

    verdict = fields["VERDICT"]
    if verdict not in _VALID_REVIEWER_VERDICTS:
        return ParseResult(
            success=False,
            data=None,
            error=f"Invalid VERDICT value: {verdict!r}. Must be one of {sorted(_VALID_REVIEWER_VERDICTS)}",
        )

    output = ReviewerOutput(
        verdict=verdict,
        summary=fields["SUMMARY"],
        open_issues=fields["OPEN_ISSUES"],
        checks_verified=fields["CHECKS_VERIFIED"],
        next_action=fields["NEXT_ACTION"],
        rationale=fields["RATIONALE"],
    )
    return ParseResult(success=True, data=output, error=None)
