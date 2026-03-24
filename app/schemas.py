"""Pydantic v2 request/response schemas for AgentRole, AgentProfile, and workspace models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# AgentRole schemas
# ---------------------------------------------------------------------------


class AgentRoleResponse(BaseModel):
    id: int
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    is_builtin: bool = False
    sort_order: int = 0
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# AgentProfile schemas
# ---------------------------------------------------------------------------


class AgentProfileCreate(BaseModel):
    name: str
    provider: str = "claude"
    command_template: str


class AgentProfileResponse(BaseModel):
    id: int
    name: str
    provider: str
    command_template: str
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Workspace schemas
# ---------------------------------------------------------------------------


class WorkspaceBase(BaseModel):
    title: str
    workspace_path: Optional[str] = None


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceRead(WorkspaceBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# ChatNode schemas
# ---------------------------------------------------------------------------


class NodeEdgeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_node_id: int
    target_node_id: int
    trigger: str  # "on_complete" | "on_no_go"
    label: Optional[str] = None
    sort_order: int = 0


class ChatNodeBase(BaseModel):
    name: str
    agent_profile_id: Optional[int] = None
    agent_role_id: Optional[int] = None
    order_index: int = 0
    routing_mode: str = "auto"
    node_type: str = "agent"


class ChatNodeCreate(ChatNodeBase):
    workspace_id: int


class ChatNodeRead(ChatNodeBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    workspace_id: int
    status: str
    last_error: Optional[str] = None
    conversation_version: int
    created_at: datetime
    updated_at: datetime
    agent_role: Optional[AgentRoleResponse] = None
    agent_profile: Optional[AgentProfileResponse] = None
    outbound_edges: list[NodeEdgeRead] = []


# ---------------------------------------------------------------------------
# ChatMessage schemas
# ---------------------------------------------------------------------------


class ChatMessageBase(BaseModel):
    role: str
    message_kind: str = "manual_user"
    content: str = ""
    source_node_id: Optional[int] = None
    source_message_id: Optional[int] = None


class ChatMessageCreate(ChatMessageBase):
    node_id: int
    sequence_number: int
    conversation_version: int = 1


class ChatMessageRead(ChatMessageBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    node_id: int
    sequence_number: int
    conversation_version: int
    status: str
    error_text: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
