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


def init_db():
    """Create all tables defined on Base.metadata."""
    Base.metadata.create_all(bind=engine)


def get_settings(db) -> "SettingsData":  # type: ignore[name-defined]
    """Read all settings keys from DB, return SettingsData with defaults."""
    from app.models import Settings  # local import to avoid circular deps
    from app.schemas import SettingsData

    rows = db.query(Settings).all()
    data: dict = {}
    for row in rows:
        data[row.key] = row.value

    return SettingsData(
        builder_command=data.get("builder_command", ""),
        reviewer_command=data.get("reviewer_command", ""),
        default_working_directory=data.get("default_working_directory", ""),
        default_max_rounds=int(data.get("default_max_rounds", 3) or 3),
    )


def save_settings(db, data: "SettingsData") -> None:  # type: ignore[name-defined]
    """Upsert settings keys into DB."""
    from app.models import Settings  # local import to avoid circular deps

    for key, value in data.model_dump().items():
        row = db.query(Settings).filter(Settings.key == key).first()
        if row is None:
            row = Settings(key=key, value=str(value))
            db.add(row)
        else:
            row.value = str(value)
    db.commit()
