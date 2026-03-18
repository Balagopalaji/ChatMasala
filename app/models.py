"""SQLAlchemy ORM models for Run, Turn, UserNote, Settings, and AgentProfile."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    goal = Column(Text, nullable=False)
    plan_text = Column(Text, nullable=True)
    workflow_type = Column(String, nullable=False, default="single_agent")
    primary_agent_profile_id = Column(Integer, ForeignKey("agent_profiles.id"), nullable=True)
    builder_agent_profile_id = Column(Integer, ForeignKey("agent_profiles.id"), nullable=True)
    reviewer_agent_profile_id = Column(Integer, ForeignKey("agent_profiles.id"), nullable=True)
    workspace = Column(String, nullable=True)
    loop_enabled = Column(Boolean, default=False)
    status = Column(String, nullable=False, default="draft")
    current_role = Column(String, nullable=True)
    round_count = Column(Integer, default=0)
    max_rounds = Column(Integer, default=3)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    turns = relationship("Turn", back_populates="run", cascade="all, delete-orphan")
    user_notes = relationship("UserNote", back_populates="run", cascade="all, delete-orphan")


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("runs.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    run: Mapped["Run"] = relationship("Run", back_populates="turns")


class UserNote(Base):
    __tablename__ = "user_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("runs.id"), nullable=False
    )
    note_text: Mapped[str] = mapped_column(Text, nullable=False)
    applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    run: Mapped["Run"] = relationship("Run", back_populates="user_notes")


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
    output_node_id = Column(Integer, ForeignKey("chat_nodes.id"), nullable=True)
    loop_node_id = Column(Integer, ForeignKey("chat_nodes.id"), nullable=True)
    max_loops = Column(Integer, default=3, nullable=False)
    loop_count = Column(Integer, default=0, nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    status = Column(String, nullable=False, default="idle")  # idle | running | needs_attention
    last_error = Column(Text, nullable=True)
    conversation_version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    workspace = relationship("Workspace", back_populates="nodes")
    agent_profile = relationship("AgentProfile", foreign_keys=[agent_profile_id])
    agent_role = relationship("AgentRole", foreign_keys=[agent_role_id])
    output_node = relationship("ChatNode", remote_side="ChatNode.id", foreign_keys="[ChatNode.output_node_id]")
    loop_node = relationship("ChatNode", remote_side="ChatNode.id", foreign_keys="[ChatNode.loop_node_id]")
    messages = relationship("ChatMessage", back_populates="node", cascade="all, delete-orphan", order_by="ChatMessage.sequence_number", foreign_keys="[ChatMessage.node_id]")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

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
