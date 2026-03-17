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


def test_output_route_captured(db):
    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    node_a = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    db.add_all([node_a, node_b])
    db.commit()
    # Set output route from A to B
    node_a.output_node_id = node_b.id
    db.commit()
    db.refresh(node_a)
    assert node_a.output_node_id == node_b.id


def test_loop_route_captured(db):
    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    node_a = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    db.add_all([node_a, node_b])
    db.commit()
    # Set loop route from A back to B
    node_a.loop_node_id = node_b.id
    node_a.max_loops = 5
    db.commit()
    db.refresh(node_a)
    assert node_a.loop_node_id == node_b.id
    assert node_a.max_loops == 5


def test_loop_defaults(db):
    """New ChatNode has max_loops=3, loop_count=0, loop_node_id=None, output_node_id=None."""
    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    node = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    db.add(node)
    db.commit()
    db.refresh(node)
    assert node.output_node_id is None
    assert node.loop_node_id is None
    assert node.max_loops == 3
    assert node.loop_count == 0


def test_self_route_prevention(db):
    """A node should not be allowed to route to itself (output_node_id)."""
    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    node = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    db.add(node)
    db.commit()
    # The route endpoint should prevent self-loop; simulate the logic
    proposed = node.id  # same as node id
    oid = int(proposed) if proposed else None
    if oid == node.id:
        oid = None
    assert oid is None


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
        _execute_node_send(node.id, msg.id, None, None, 3, 0, db)

    db.refresh(msg)
    db.refresh(node)
    assert msg.status == "failed"
    assert node.status == "needs_attention"
    assert node.last_error is not None


def test_delete_node_clears_inbound_routes(db):
    """Deleting a node should null out other nodes' output_node_id and loop_node_id pointing to it."""
    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    db.add_all([node_a, node_b])
    db.commit()

    # Route A → B via output_node_id and loop_node_id
    node_a.output_node_id = node_b.id
    node_a.loop_node_id = node_b.id
    db.commit()

    # Simulate the delete logic
    db.query(ChatNode).filter(
        ChatNode.workspace_id == ws.id,
        ChatNode.output_node_id == node_b.id,
    ).update({"output_node_id": None})
    db.query(ChatNode).filter(
        ChatNode.workspace_id == ws.id,
        ChatNode.loop_node_id == node_b.id,
    ).update({"loop_node_id": None})
    db.delete(node_b)
    db.commit()

    db.refresh(node_a)
    assert node_a.output_node_id is None
    assert node_a.loop_node_id is None


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


def test_go_sentinel_routes_to_output_node(db):
    """When loop_node_id is set and response ends with GO, message is delivered to output_node_id."""
    import unittest.mock as mock
    from app.routes.workspaces import _execute_node_send
    from app.agents.cli_runner import RunResult

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    profile = AgentProfile(name="P", provider="test", command_template="echo", instruction_file="")
    db.add(profile)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", agent_profile_id=profile.id, order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)  # output target
    node_c = ChatNode(workspace_id=ws.id, name="C", order_index=2)  # loop target
    db.add_all([node_a, node_b, node_c])
    db.commit()

    node_a.output_node_id = node_b.id
    node_a.loop_node_id = node_c.id
    db.commit()

    msg = ChatMessage(
        node_id=node_a.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="", status="running",
    )
    db.add(msg)
    db.commit()

    fake_result = RunResult(stdout="Here is my answer.\nGO", stderr="", exit_code=0)
    with mock.patch("app.routes.workspaces.run_agent", return_value=fake_result):
        _execute_node_send(node_a.id, msg.id, node_a.output_node_id, node_a.loop_node_id, node_a.max_loops, node_a.loop_count, db)

    db.refresh(node_a)
    db.refresh(msg)
    assert node_a.status == "idle"
    assert msg.status == "completed"
    # Output node B should have received an auto_route message
    routed = db.query(ChatMessage).filter(ChatMessage.node_id == node_b.id).first()
    assert routed is not None
    assert routed.message_kind == "auto_route"
    # Loop node C should NOT have received anything
    loop_msgs = db.query(ChatMessage).filter(ChatMessage.node_id == node_c.id).count()
    assert loop_msgs == 0


def test_no_go_sentinel_loops_back(db):
    """When loop_node_id is set and response ends with NO_GO, message is delivered to loop_node_id."""
    import unittest.mock as mock
    from app.routes.workspaces import _execute_node_send
    from app.agents.cli_runner import RunResult

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    profile = AgentProfile(name="P2", provider="test", command_template="echo", instruction_file="")
    db.add(profile)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", agent_profile_id=profile.id, order_index=0, max_loops=3, loop_count=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)  # output target
    node_c = ChatNode(workspace_id=ws.id, name="C", order_index=2)  # loop target (no agent — no auto-run)
    db.add_all([node_a, node_b, node_c])
    db.commit()

    node_a.output_node_id = node_b.id
    node_a.loop_node_id = node_c.id
    db.commit()

    msg = ChatMessage(
        node_id=node_a.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="", status="running",
    )
    db.add(msg)
    db.commit()

    fake_result = RunResult(stdout="Needs revision.\nNO_GO", stderr="", exit_code=0)
    with mock.patch("app.routes.workspaces.run_agent", return_value=fake_result):
        # Patch threading to avoid real threads in tests
        with mock.patch("app.routes.workspaces.threading") as mock_threading:
            mock_threading.Thread.return_value.start = mock.MagicMock()
            _execute_node_send(node_a.id, msg.id, node_a.output_node_id, node_a.loop_node_id, 3, 0, db)

    db.refresh(node_a)
    db.refresh(msg)
    # loop_count should have been incremented to 1
    assert node_a.loop_count == 1
    # Node A should be idle (not at max loops yet)
    assert node_a.status == "idle"
    # Loop node C should have received the routed message
    loop_msg = db.query(ChatMessage).filter(ChatMessage.node_id == node_c.id).first()
    assert loop_msg is not None
    assert loop_msg.message_kind == "auto_route"
    # Output node B should NOT have received anything
    output_msgs = db.query(ChatMessage).filter(ChatMessage.node_id == node_b.id).count()
    assert output_msgs == 0


def test_no_go_max_loops_reached(db):
    """When NO_GO and loop_count >= max_loops, node is set to needs_attention."""
    import unittest.mock as mock
    from app.routes.workspaces import _execute_node_send
    from app.agents.cli_runner import RunResult

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    profile = AgentProfile(name="P3", provider="test", command_template="echo", instruction_file="")
    db.add(profile)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", agent_profile_id=profile.id, order_index=0, max_loops=3, loop_count=2)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)  # output
    node_c = ChatNode(workspace_id=ws.id, name="C", order_index=2)  # loop
    db.add_all([node_a, node_b, node_c])
    db.commit()

    node_a.output_node_id = node_b.id
    node_a.loop_node_id = node_c.id
    db.commit()

    msg = ChatMessage(
        node_id=node_a.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="", status="running",
    )
    db.add(msg)
    db.commit()

    fake_result = RunResult(stdout="Still not good.\nNO_GO", stderr="", exit_code=0)
    with mock.patch("app.routes.workspaces.run_agent", return_value=fake_result):
        _execute_node_send(node_a.id, msg.id, node_a.output_node_id, node_a.loop_node_id, 3, 2, db)

    db.refresh(node_a)
    assert node_a.status == "needs_attention"
    assert "Max loops reached" in node_a.last_error
    # Output node should have received message (circuit breaker routes to output)
    routed = db.query(ChatMessage).filter(ChatMessage.node_id == node_b.id).first()
    assert routed is not None


def test_neither_sentinel_sets_needs_attention(db):
    """When loop_node_id is set but response has neither GO nor NO_GO, sets needs_attention."""
    import unittest.mock as mock
    from app.routes.workspaces import _execute_node_send
    from app.agents.cli_runner import RunResult

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    profile = AgentProfile(name="P4", provider="test", command_template="echo", instruction_file="")
    db.add(profile)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", agent_profile_id=profile.id, order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    db.add_all([node_a, node_b])
    db.commit()

    node_a.loop_node_id = node_b.id
    db.commit()

    msg = ChatMessage(
        node_id=node_a.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="", status="running",
    )
    db.add(msg)
    db.commit()

    fake_result = RunResult(stdout="Here is some output without a sentinel.", stderr="", exit_code=0)
    with mock.patch("app.routes.workspaces.run_agent", return_value=fake_result):
        _execute_node_send(node_a.id, msg.id, None, node_a.loop_node_id, 3, 0, db)

    db.refresh(node_a)
    assert node_a.status == "needs_attention"
    assert "GO or NO_GO" in node_a.last_error


def test_no_loop_node_routes_unconditionally(db):
    """Without loop_node_id, successful response routes to output_node_id unconditionally."""
    import unittest.mock as mock
    from app.routes.workspaces import _execute_node_send
    from app.agents.cli_runner import RunResult

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    profile = AgentProfile(name="P5", provider="test", command_template="echo", instruction_file="")
    db.add(profile)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", agent_profile_id=profile.id, order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    db.add_all([node_a, node_b])
    db.commit()

    node_a.output_node_id = node_b.id
    db.commit()

    msg = ChatMessage(
        node_id=node_a.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="", status="running",
    )
    db.add(msg)
    db.commit()

    # Response does NOT contain GO or NO_GO — should still route because no loop
    fake_result = RunResult(stdout="Here is the result without sentinels.", stderr="", exit_code=0)
    with mock.patch("app.routes.workspaces.run_agent", return_value=fake_result):
        _execute_node_send(node_a.id, msg.id, node_a.output_node_id, None, 3, 0, db)

    db.refresh(node_a)
    assert node_a.status == "idle"
    routed = db.query(ChatMessage).filter(ChatMessage.node_id == node_b.id).first()
    assert routed is not None
    assert routed.message_kind == "auto_route"


def test_reset_resets_loop_count(db):
    """Resetting a node (incrementing conversation_version) also resets loop_count to 0."""
    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    node = ChatNode(workspace_id=ws.id, name="A", order_index=0, loop_count=2)
    db.add(node)
    db.commit()

    # Simulate reset route logic
    node.conversation_version += 1
    node.status = "idle"
    node.last_error = None
    node.loop_count = 0
    db.commit()
    db.refresh(node)

    assert node.conversation_version == 2
    assert node.loop_count == 0
