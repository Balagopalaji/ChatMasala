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
        "builtin_key": "claude_default",
        "name": "Claude",
        "provider": "claude",
        "command_template": "claude --dangerously-skip-permissions",
        "instruction_file": "",
        "is_builtin": True,
        "sort_order": 0,
    },
    {
        "builtin_key": "codex_default",
        "name": "Codex",
        "provider": "codex",
        "command_template": "codex exec -",
        "instruction_file": "",
        "is_builtin": True,
        "sort_order": 1,
    },
    {
        "builtin_key": "gemini_default",
        "name": "Gemini CLI",
        "provider": "gemini",
        "command_template": "gemini",
        "instruction_file": "",
        "is_builtin": True,
        "sort_order": 2,
    },
]


def seed_builtin_agents() -> None:
    """Seed built-in agent presets using UPSERT semantics (by builtin_key).

    Updates existing rows if name/command_template/sort_order changed.
    Does not remove old builtins with different keys.
    Custom agents are never touched here.
    """
    from app.models import AgentProfile  # local import to avoid circular deps

    db = SessionLocal()
    try:
        for agent_data in BUILTIN_AGENTS:
            existing = db.query(AgentProfile).filter(
                AgentProfile.builtin_key == agent_data["builtin_key"]
            ).first()
            if existing:
                existing.name = agent_data["name"]
                existing.command_template = agent_data["command_template"]
                existing.sort_order = agent_data["sort_order"]
            else:
                db.add(AgentProfile(**agent_data))
        db.commit()
    finally:
        db.close()


def init_db():
    """Drop all tables and recreate them, then seed default data."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    seed_default_profiles()
    seed_builtin_agents()


