import os
import sqlite3

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

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



BUILTIN_AGENTS = [
    {
        "builtin_key": "claude_default",
        "name": "Claude",
        "provider": "claude",
        "command_template": "claude --dangerously-skip-permissions",
        "is_builtin": True,
        "sort_order": 0,
    },
    {
        "builtin_key": "codex_default",
        "name": "Codex",
        "provider": "codex",
        "command_template": "codex exec -",
        "is_builtin": True,
        "sort_order": 1,
    },
    {
        "builtin_key": "gemini_default",
        "name": "Gemini CLI",
        "provider": "gemini",
        "command_template": "gemini",
        "is_builtin": True,
        "sort_order": 2,
    },
]

BUILTIN_ROLES = [
    {"slug": "brainstorm-a",  "name": "Brainstorm A",  "sort_order": 0, "description": "First-pass ideation: options, angles, tradeoffs.",        "instruction_file": "profiles/agents/brainstorm-a.md"},
    {"slug": "brainstorm-b",  "name": "Brainstorm B",  "sort_order": 1, "description": "Second-pass ideation: distinct direction from Brainstorm A.", "instruction_file": "profiles/agents/brainstorm-b.md"},
    {"slug": "critic",        "name": "Critic",         "sort_order": 2, "description": "Stress-tests proposals and finds weak assumptions.",         "instruction_file": "profiles/agents/critic.md"},
    {"slug": "decider",       "name": "Decider",        "sort_order": 3, "description": "Decides GO/NO_GO after brainstorm and critique.",            "instruction_file": "profiles/agents/decider.md"},
    {"slug": "planner",       "name": "Planner",        "sort_order": 4, "description": "Turns accepted ideas into a phased implementation plan.",    "instruction_file": "profiles/agents/planner.md"},
    {"slug": "builder",       "name": "Builder",        "sort_order": 5, "description": "Implements approved work. Writes code and edits files.",      "instruction_file": "profiles/agents/builder-v2.md"},
    {"slug": "reviewer",      "name": "Reviewer",       "sort_order": 6, "description": "Reviews implementation for bugs and correctness.",           "instruction_file": "profiles/agents/reviewer-v2.md"},
    {"slug": "human-gate",    "name": "Human Gate",     "sort_order": 7, "description": "Pauses the workflow and waits for human direction.",         "instruction_file": "profiles/agents/human-gate.md"},
    {"slug": "repo-context",  "name": "Repo Context",   "sort_order": 8, "description": "Inspects the repository and explains the architecture.",     "instruction_file": "profiles/agents/repo-context.md"},
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
                existing.provider = agent_data["provider"]
                existing.command_template = agent_data["command_template"]
                existing.is_builtin = agent_data["is_builtin"]
                existing.sort_order = agent_data["sort_order"]
            else:
                db.add(AgentProfile(**agent_data))
        db.commit()
    finally:
        db.close()


def seed_builtin_roles(db: Session) -> None:
    from app.models import AgentRole  # local import to avoid circular deps

    for role_data in BUILTIN_ROLES:
        existing = db.query(AgentRole).filter(AgentRole.slug == role_data["slug"]).first()
        if existing:
            existing.name = role_data["name"]
            existing.description = role_data["description"]
            existing.instruction_file = role_data["instruction_file"]
            existing.sort_order = role_data["sort_order"]
            existing.is_builtin = True
        else:
            role = AgentRole(
                slug=role_data["slug"],
                name=role_data["name"],
                description=role_data["description"],
                instruction_file=role_data["instruction_file"],
                is_builtin=True,
                sort_order=role_data["sort_order"],
            )
            db.add(role)
    db.commit()


def ensure_db() -> None:
    """Create missing tables and seed built-in data without destroying user data."""
    Base.metadata.create_all(bind=engine)
    seed_builtin_agents()
    db = SessionLocal()
    try:
        seed_builtin_roles(db)
    finally:
        db.close()


def init_db() -> None:
    """Drop all tables and recreate them, then seed default data."""
    Base.metadata.drop_all(bind=engine)
    ensure_db()


def bootstrap_db(reset: bool = False) -> None:
    """Initialize the database for app startup.

    By default startup is non-destructive and only ensures schema + built-ins.
    Set reset=True for explicit destructive local resets.
    """
    if reset:
        init_db()
    else:
        ensure_db()

