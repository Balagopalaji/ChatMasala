"""Pydantic v2 request/response schemas for Run, Turn, UserNote, and AgentProfile."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Run schemas
# ---------------------------------------------------------------------------


class RunCreate(BaseModel):
    title: str = ""
    goal: str
    plan_text: str = ""
    workflow_type: str = "single_agent"
    primary_agent_profile_id: Optional[int] = None
    builder_agent_profile_id: Optional[int] = None
    reviewer_agent_profile_id: Optional[int] = None
    workspace: str = ""
    loop_enabled: bool = False
    max_rounds: int = 3


class RunResponse(BaseModel):
    id: int
    title: str
    goal: str
    plan_text: Optional[str]
    workflow_type: str
    status: str
    current_role: Optional[str]
    round_count: int
    max_rounds: int
    last_error: Optional[str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Turn schemas
# ---------------------------------------------------------------------------


class TurnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    role: str
    sequence_number: int
    prompt_text: str
    raw_output_text: Optional[str]
    parsed_json: Optional[str]
    status: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]


# ---------------------------------------------------------------------------
# UserNote schemas
# ---------------------------------------------------------------------------


class UserNoteCreate(BaseModel):
    note_text: str


class UserNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    note_text: str
    applied: bool = False
    created_at: datetime


# ---------------------------------------------------------------------------
# AgentProfile schemas
# ---------------------------------------------------------------------------


class AgentProfileCreate(BaseModel):
    name: str
    provider: str = "claude"
    command_template: str
    instruction_file: str


class AgentProfileResponse(BaseModel):
    id: int
    name: str
    provider: str
    command_template: str
    instruction_file: str
    model_config = ConfigDict(from_attributes=True)
