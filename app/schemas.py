"""Pydantic v2 request/response schemas for Thread, Turn, and UserNote."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Thread schemas
# ---------------------------------------------------------------------------


class ThreadCreate(BaseModel):
    title: str
    task_text: str
    plan_text: str
    builder_command: str
    reviewer_command: str
    working_directory: Optional[str] = None
    max_rounds: int = 3


class ThreadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    task_text: str
    plan_text: str
    builder_command: str
    reviewer_command: str
    working_directory: Optional[str]
    status: str
    current_role: Optional[str]
    round_count: int
    max_rounds: int
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Turn schemas
# ---------------------------------------------------------------------------


class TurnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    thread_id: int
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
    thread_id: int
    note_text: str
    applied: bool = False
    created_at: datetime


# ---------------------------------------------------------------------------
# Settings schemas
# ---------------------------------------------------------------------------


class SettingsData(BaseModel):
    builder_command: str = ""
    reviewer_command: str = ""
    default_working_directory: str = ""
    default_max_rounds: int = 3
