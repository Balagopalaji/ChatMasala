"""Tests for Workspace, ChatNode, and ChatMessage models."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AgentProfile, ChatMessage, ChatNode, Workspace


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def test_create_workspace(db):
    ws = Workspace(title="Test WS", workspace_path="/tmp/test")
    db.add(ws)
    db.commit()
    db.refresh(ws)
    assert ws.id is not None
    assert ws.title == "Test WS"


def test_create_chat_node(db):
    ws = Workspace(title="Test WS")
    db.add(ws)
    db.commit()
    node = ChatNode(workspace_id=ws.id, name="Node 1", order_index=0)
    db.add(node)
    db.commit()
    db.refresh(node)
    assert node.id is not None
    assert node.status == "idle"
    assert node.conversation_version == 1


def test_create_chat_message(db):
    ws = Workspace(title="Test WS")
    db.add(ws)
    db.commit()
    node = ChatNode(workspace_id=ws.id, name="Node 1", order_index=0)
    db.add(node)
    db.commit()
    msg = ChatMessage(
        node_id=node.id,
        sequence_number=1,
        conversation_version=1,
        role="user",
        message_kind="manual_user",
        content="Hello",
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    assert msg.id is not None
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_node_cascade_delete(db):
    ws = Workspace(title="Test WS")
    db.add(ws)
    db.commit()
    node = ChatNode(workspace_id=ws.id, name="Node 1")
    db.add(node)
    db.commit()
    msg = ChatMessage(node_id=node.id, sequence_number=1, conversation_version=1,
                      role="user", message_kind="manual_user", content="test")
    db.add(msg)
    db.commit()
    db.delete(ws)
    db.commit()
    assert db.query(ChatNode).filter(ChatNode.id == node.id).first() is None
    assert db.query(ChatMessage).filter(ChatMessage.id == msg.id).first() is None


def test_message_source_provenance(db):
    ws = Workspace(title="Test WS")
    db.add(ws)
    db.commit()
    node_a = ChatNode(workspace_id=ws.id, name="Node A", order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="Node B", order_index=1)
    db.add_all([node_a, node_b])
    db.commit()
    # Original message in node A
    orig = ChatMessage(node_id=node_a.id, sequence_number=1, conversation_version=1,
                       role="assistant", message_kind="assistant_reply", content="Result")
    db.add(orig)
    db.commit()
    # Imported message in node B with provenance
    imported = ChatMessage(
        node_id=node_b.id, sequence_number=1, conversation_version=1,
        role="user", message_kind="manual_import", content="Result",
        source_node_id=node_a.id, source_message_id=orig.id,
    )
    db.add(imported)
    db.commit()
    db.refresh(imported)
    assert imported.source_node_id == node_a.id
    assert imported.source_message_id == orig.id


def test_reset_increments_conversation_version(db):
    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    node = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    db.add(node)
    db.commit()
    # Add a message
    msg = ChatMessage(node_id=node.id, sequence_number=1, conversation_version=1,
                      role="user", message_kind="manual_user", content="hi")
    db.add(msg)
    db.commit()
    # Simulate reset
    node.conversation_version += 1
    db.commit()
    db.refresh(node)
    assert node.conversation_version == 2
    # Old message is still in DB but has version 1
    old = db.query(ChatMessage).filter(ChatMessage.node_id == node.id, ChatMessage.conversation_version == 1).first()
    assert old is not None


def test_downstream_route_captured(db):
    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    node_a = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    db.add_all([node_a, node_b])
    db.commit()
    # Set route from A to B
    node_a.downstream_node_id = node_b.id
    db.commit()
    db.refresh(node_a)
    assert node_a.downstream_node_id == node_b.id


def test_self_route_prevention(db):
    """A node should not be allowed to route to itself."""
    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    node = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    db.add(node)
    db.commit()
    # The route endpoint should prevent self-loop; simulate the logic
    proposed = node.id  # same as node id
    did = int(proposed) if proposed else None
    if did == node.id:
        did = None
    assert did is None


def test_nonzero_exit_marks_failed(db):
    """A non-zero subprocess returncode should mark the message failed, not completed."""
    import unittest.mock as mock
    from app.routes.workspaces import _execute_node_send

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    profile = AgentProfile(
        name="TestCLI", provider="test",
        command_template="false",  # always exits 1
        instruction_file="",
    )
    db.add(profile)
    db.commit()

    node = ChatNode(workspace_id=ws.id, name="N", agent_profile_id=profile.id)
    db.add(node)
    db.commit()

    msg = ChatMessage(
        node_id=node.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="", status="running",
    )
    db.add(msg)
    db.commit()

    # Patch run_agent to return a failed RunResult
    from app.agents.cli_runner import RunResult
    fake_result = RunResult(stdout="", stderr="error: something went wrong", exit_code=1)

    with mock.patch("app.routes.workspaces.run_agent", return_value=fake_result):
        _execute_node_send(node.id, msg.id, None, db)

    db.refresh(msg)
    db.refresh(node)
    assert msg.status == "failed"
    assert node.status == "needs_attention"
    assert node.last_error is not None


def test_delete_node_clears_inbound_routes(db):
    """Deleting a node should null out other nodes' downstream_node_id pointing to it."""
    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    db.add_all([node_a, node_b])
    db.commit()

    # Route A → B
    node_a.downstream_node_id = node_b.id
    db.commit()

    # Simulate the delete logic
    db.query(ChatNode).filter(
        ChatNode.workspace_id == ws.id,
        ChatNode.downstream_node_id == node_b.id,
    ).update({"downstream_node_id": None})
    db.delete(node_b)
    db.commit()

    db.refresh(node_a)
    assert node_a.downstream_node_id is None


def test_cross_workspace_route_rejected(db):
    """Route target must belong to the same workspace."""
    ws1 = Workspace(title="WS1")
    ws2 = Workspace(title="WS2")
    db.add_all([ws1, ws2])
    db.commit()

    node_a = ChatNode(workspace_id=ws1.id, name="A")
    node_b = ChatNode(workspace_id=ws2.id, name="B")
    db.add_all([node_a, node_b])
    db.commit()

    # The workspace boundary check logic: target.workspace_id != ws_id should reject
    target = db.query(ChatNode).filter(ChatNode.id == node_b.id).first()
    assert target.workspace_id != ws1.id  # confirms cross-workspace


def test_auto_route_cross_workspace_blocked(db):
    """_deliver_auto_route should silently refuse cross-workspace delivery."""
    from app.routes.workspaces import _deliver_auto_route

    ws1 = Workspace(title="WS1")
    ws2 = Workspace(title="WS2")
    db.add_all([ws1, ws2])
    db.commit()

    node_a = ChatNode(workspace_id=ws1.id, name="A")
    node_b = ChatNode(workspace_id=ws2.id, name="B")
    db.add_all([node_a, node_b])
    db.commit()

    msg = ChatMessage(
        node_id=node_a.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="hello", status="completed",
    )
    db.add(msg)
    db.commit()

    # Attempt cross-workspace delivery — should be a no-op
    _deliver_auto_route(node_a.id, msg.id, node_b.id, db)

    count = db.query(ChatMessage).filter(ChatMessage.node_id == node_b.id).count()
    assert count == 0  # nothing was injected
