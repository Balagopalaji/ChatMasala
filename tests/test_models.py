"""Tests for app/models.py — SQLAlchemy ORM models using in-memory SQLite."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AgentProfile, AgentRole, ChatNode, Workspace


@pytest.fixture(scope="function")
def db_session():
    """Provide a fresh in-memory SQLite session for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_fk(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


# ---------------------------------------------------------------------------
# AgentProfile tests
# ---------------------------------------------------------------------------


def test_agent_profile_creation(db_session):
    profile = AgentProfile(
        name="Test Builder",
        provider="claude",
        command_template="claude --dangerously-skip-permissions",
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    assert profile.id is not None
    assert profile.name == "Test Builder"
    assert profile.provider == "claude"


def test_agent_profile_name_unique(db_session):
    p1 = AgentProfile(name="Unique", provider="claude", command_template="cmd")
    p2 = AgentProfile(name="Unique", provider="claude", command_template="cmd2")
    db_session.add(p1)
    db_session.commit()
    db_session.add(p2)
    import pytest
    with pytest.raises(Exception):
        db_session.commit()


# ---------------------------------------------------------------------------
# AgentRole tests
# ---------------------------------------------------------------------------


def test_agent_role_create(db_session):
    """AgentRole can be created and loaded back from the database."""
    role = AgentRole(
        slug="builder",
        name="Builder",
        description="Implements approved work.",
        instruction_file="profiles/agents/builder-v2.md",
        is_builtin=True,
        sort_order=5,
    )
    db_session.add(role)
    db_session.commit()
    db_session.refresh(role)

    queried = db_session.query(AgentRole).filter_by(slug="builder").one()
    assert queried.id is not None
    assert queried.slug == "builder"
    assert queried.name == "Builder"
    assert queried.description == "Implements approved work."
    assert queried.instruction_file == "profiles/agents/builder-v2.md"
    assert queried.is_builtin is True
    assert queried.sort_order == 5


def test_agent_role_slug_unique(db_session):
    """Two AgentRole rows with the same slug should raise an IntegrityError."""
    r1 = AgentRole(slug="critic", name="Critic A", instruction_file="f.md")
    r2 = AgentRole(slug="critic", name="Critic B", instruction_file="f.md")
    db_session.add(r1)
    db_session.commit()
    db_session.add(r2)
    with pytest.raises(Exception):
        db_session.commit()


def test_chat_node_agent_role_id(db_session):
    """A ChatNode can have an agent_role_id assigned and the relationship loads."""
    ws = Workspace(title="Role Test WS")
    db_session.add(ws)
    db_session.flush()

    role = AgentRole(
        slug="planner",
        name="Planner",
        instruction_file="profiles/agents/planner.md",
    )
    db_session.add(role)
    db_session.flush()

    node = ChatNode(workspace_id=ws.id, name="Planning Node", agent_role_id=role.id)
    db_session.add(node)
    db_session.commit()
    db_session.refresh(node)

    assert node.agent_role_id == role.id
    assert node.agent_role is not None
    assert node.agent_role.slug == "planner"


def test_node_edge_model_basic(tmp_path):
    """NodeEdge ORM model creates and queries correctly."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.db import Base
    from app.models import NodeEdge, ChatNode, Workspace

    engine = create_engine(f"sqlite:///{tmp_path}/ne.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    db.add_all([node_a, node_b])
    db.commit()

    edge = NodeEdge(source_node_id=node_a.id, target_node_id=node_b.id, trigger="on_complete")
    db.add(edge)
    db.commit()
    db.refresh(edge)

    assert edge.id is not None
    assert edge.trigger == "on_complete"
    assert edge.created_at is not None

    db.close()
    engine.dispose()
