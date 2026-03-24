"""SQLAlchemy ORM models for Settings, AgentRole, AgentProfile, and workspace models."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Settings(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)


class AgentRole(Base):
    __tablename__ = "agent_roles"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    slug = Column(String, nullable=True, unique=True)        # stable machine key for built-ins
    description = Column(Text, nullable=True)
    instruction_file = Column(String, nullable=False)
    is_builtin = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AgentProfile(Base):
    __tablename__ = "agent_profiles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    provider = Column(String, nullable=False, default="claude")
    command_template = Column(String, nullable=False)
    # Phase 2 additions — clean schema reset acceptable per AGENTS.md
    is_builtin = Column(Boolean, default=False, nullable=False, server_default="0")
    builtin_key = Column(String, nullable=True)
    sort_order = Column(Integer, default=0, nullable=False, server_default="0")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Phase 4 — Workspace / Node / Message models
# ---------------------------------------------------------------------------


class Workspace(Base):
    __tablename__ = "workspaces"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    workspace_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    nodes = relationship("ChatNode", back_populates="workspace", cascade="all, delete-orphan", order_by="ChatNode.order_index")


class ChatNode(Base):
    __tablename__ = "chat_nodes"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=False)
    name = Column(String, nullable=False)
    agent_profile_id = Column(Integer, ForeignKey("agent_profiles.id"), nullable=True)
    agent_role_id = Column(Integer, ForeignKey("agent_roles.id"), nullable=True)
    order_index = Column(Integer, default=0, nullable=False)
    status = Column(String, nullable=False, default="idle")  # idle | running | needs_attention
    last_error = Column(Text, nullable=True)
    conversation_version = Column(Integer, default=1, nullable=False)
    routing_mode = Column(String, nullable=False, default="auto")
    # "auto" | "human_gate"
    node_type = Column(String, nullable=False, default="agent")
    # "agent" | "human"
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    workspace = relationship("Workspace", back_populates="nodes")
    agent_profile = relationship("AgentProfile", foreign_keys=[agent_profile_id])
    agent_role = relationship("AgentRole", foreign_keys=[agent_role_id])
    messages = relationship("ChatMessage", back_populates="node", cascade="all, delete-orphan", order_by="ChatMessage.sequence_number", foreign_keys="[ChatMessage.node_id]")
    outbound_edges = relationship("NodeEdge", foreign_keys="[NodeEdge.source_node_id]", back_populates="source_node", cascade="all, delete-orphan")
    inbound_edges = relationship("NodeEdge", foreign_keys="[NodeEdge.target_node_id]", back_populates="target_node", cascade="all, delete-orphan")


class NodeEdge(Base):
    __tablename__ = "node_edges"

    id = Column(Integer, primary_key=True, index=True)
    source_node_id = Column(Integer, ForeignKey("chat_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_node_id = Column(Integer, ForeignKey("chat_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    trigger = Column(String, nullable=False)  # "on_complete" | "on_no_go"
    label = Column(String, nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint("trigger IN ('on_complete', 'on_no_go')", name="ck_node_edge_trigger"),
    )

    source_node = relationship("ChatNode", foreign_keys=[source_node_id], back_populates="outbound_edges")
    target_node = relationship("ChatNode", foreign_keys=[target_node_id], back_populates="inbound_edges")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    __table_args__ = (
        UniqueConstraint("node_id", "conversation_version", "sequence_number", name="uq_chat_message_seq"),
    )

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(Integer, ForeignKey("chat_nodes.id"), nullable=False)
    sequence_number = Column(Integer, nullable=False)
    conversation_version = Column(Integer, nullable=False, default=1)
    role = Column(String, nullable=False)  # user | assistant | system
    message_kind = Column(String, nullable=False, default="manual_user")
    # manual_user | manual_import | auto_route | assistant_reply | reset_marker | error
    content = Column(Text, nullable=False, default="")
    source_node_id = Column(Integer, ForeignKey("chat_nodes.id"), nullable=True)
    source_message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=True)
    prompt_text = Column(Text, nullable=True)
    raw_output_text = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="completed")  # completed | running | failed
    error_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    node = relationship("ChatNode", back_populates="messages", foreign_keys=[node_id])
    source_node = relationship("ChatNode", foreign_keys=[source_node_id])
    source_message = relationship("ChatMessage", remote_side="ChatMessage.id", foreign_keys="[ChatMessage.source_message_id]")
