import os
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./chatmasala.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_default_profiles() -> None:
    """Create the 3 default AgentProfile rows if they don't already exist."""
    from app.models import AgentProfile  # local import to avoid circular deps

    defaults = [
        {
            "name": "Single Agent",
            "provider": "claude",
            "command_template": "claude --dangerously-skip-permissions",
            "instruction_file": "profiles/agents/single-agent.md",
        },
        {
            "name": "Builder",
            "provider": "claude",
            "command_template": "claude --dangerously-skip-permissions",
            "instruction_file": "profiles/agents/builder.md",
        },
        {
            "name": "Reviewer",
            "provider": "claude",
            "command_template": "claude --dangerously-skip-permissions",
            "instruction_file": "profiles/agents/reviewer.md",
        },
    ]
    db = SessionLocal()
    try:
        for profile_data in defaults:
            existing = db.query(AgentProfile).filter(AgentProfile.name == profile_data["name"]).first()
            if not existing:
                db.add(AgentProfile(**profile_data))
        db.commit()
    finally:
        db.close()


BUILTIN_AGENTS = [
    {
        "name": "Claude Sonnet",
        "provider": "claude",
        "command_template": "claude --model claude-sonnet-4-5",
        "instruction_file": "",
        "is_builtin": True,
        "builtin_key": "claude_sonnet",
        "sort_order": 1,
    },
    {
        "name": "Claude Opus",
        "provider": "claude",
        "command_template": "claude --model claude-opus-4-5",
        "instruction_file": "",
        "is_builtin": True,
        "builtin_key": "claude_opus",
        "sort_order": 2,
    },
    {
        "name": "Codex CLI",
        "provider": "codex",
        "command_template": "codex",
        "instruction_file": "",
        "is_builtin": True,
        "builtin_key": "codex_cli",
        "sort_order": 3,
    },
    {
        "name": "Gemini CLI",
        "provider": "gemini",
        "command_template": "gemini",
        "instruction_file": "",
        "is_builtin": True,
        "builtin_key": "gemini_cli",
        "sort_order": 4,
    },
]


def seed_builtin_agents() -> None:
    """Seed built-in agent presets (Claude Sonnet, Claude Opus, Codex CLI, Gemini CLI).

    Checks by builtin_key so re-runs are idempotent.  Custom agents are never
    seeded here — those are user-created entries.
    """
    from app.models import AgentProfile  # local import to avoid circular deps

    db = SessionLocal()
    try:
        for agent_data in BUILTIN_AGENTS:
            existing = db.query(AgentProfile).filter(
                AgentProfile.builtin_key == agent_data["builtin_key"]
            ).first()
            if not existing:
                db.add(AgentProfile(**agent_data))
        db.commit()
    finally:
        db.close()


def init_db():
    """Create all tables defined on Base.metadata."""
    Base.metadata.create_all(bind=engine)
    seed_default_profiles()
    seed_builtin_agents()


