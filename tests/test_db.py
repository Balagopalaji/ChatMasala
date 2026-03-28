"""Tests for database bootstrap behavior."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_ensure_db_preserves_existing_rows_and_seeds_builtins(tmp_path, monkeypatch):
    from app import db as db_module
    from app.models import AgentProfile, AgentRole, Workspace

    db_path = tmp_path / "bootstrap.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(db_module, "SessionLocal", Session)

    db_module.Base.metadata.create_all(bind=engine)

    db = Session()
    db.add(Workspace(title="Keep Me"))
    db.commit()
    db.close()

    db_module.ensure_db()

    db = Session()
    try:
        assert db.query(Workspace).count() == 1
        assert db.query(Workspace).first().title == "Keep Me"
        assert db.query(AgentProfile).filter(AgentProfile.is_builtin == True).count() == len(db_module.BUILTIN_AGENTS)  # noqa: E712
        assert db.query(AgentRole).filter(AgentRole.is_builtin == True).count() == len(db_module.BUILTIN_ROLES)  # noqa: E712
    finally:
        db.close()
        engine.dispose()


def test_init_db_is_still_explicitly_destructive(tmp_path, monkeypatch):
    from app import db as db_module
    from app.models import Workspace

    db_path = tmp_path / "reset.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    monkeypatch.setattr(db_module, "engine", engine)
    monkeypatch.setattr(db_module, "SessionLocal", Session)

    db_module.Base.metadata.create_all(bind=engine)

    db = Session()
    db.add(Workspace(title="Disposable"))
    db.commit()
    db.close()

    db_module.init_db()

    db = Session()
    try:
        assert db.query(Workspace).count() == 0
    finally:
        db.close()
        engine.dispose()
