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


def init_db():
    """Create all tables defined on Base.metadata."""
    Base.metadata.create_all(bind=engine)
    seed_default_profiles()


