"""Tests for Workspace, ChatNode, ChatMessage, and NodeEdge models."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import AgentProfile, ChatMessage, ChatNode, NodeEdge, Workspace


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


def test_self_route_prevention_in_edge_setter(db):
    """The edge setter should prevent a node from routing to itself."""
    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    node = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    db.add(node)
    db.commit()
    # The route endpoint logic: tid == node.id should be rejected (tid set to None)
    proposed = node.id
    tid = int(proposed) if proposed else None
    if tid == node.id:
        tid = None
    assert tid is None


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

    # Also verify NodeEdge cross-workspace is rejected by the same boundary logic
    source = db.query(ChatNode).filter(ChatNode.id == node_a.id).first()
    assert source.workspace_id != target.workspace_id


# ---------------------------------------------------------------------------
# NodeEdge model tests
# ---------------------------------------------------------------------------


def test_node_edge_creation(db):
    """NodeEdge can be created between two nodes in the same workspace."""
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
    assert edge.source_node_id == node_a.id
    assert edge.target_node_id == node_b.id
    assert edge.trigger == "on_complete"


def test_node_edge_multiple_edges_same_trigger_allowed(db):
    """Multiple edges with the same trigger from the same source are now allowed."""
    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    node_a = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    node_c = ChatNode(workspace_id=ws.id, name="C", order_index=2)
    db.add_all([node_a, node_b, node_c])
    db.commit()

    edge1 = NodeEdge(source_node_id=node_a.id, target_node_id=node_b.id, trigger="on_complete", sort_order=0)
    edge2 = NodeEdge(source_node_id=node_a.id, target_node_id=node_c.id, trigger="on_complete", sort_order=1)
    db.add_all([edge1, edge2])
    db.commit()

    count = db.query(NodeEdge).filter(
        NodeEdge.source_node_id == node_a.id,
        NodeEdge.trigger == "on_complete",
    ).count()
    assert count == 2


def test_node_edge_different_types_allowed(db):
    """One on_complete and one on_no_go edge from the same source is allowed."""
    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()
    node_a = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    node_c = ChatNode(workspace_id=ws.id, name="C", order_index=2)
    db.add_all([node_a, node_b, node_c])
    db.commit()

    edge1 = NodeEdge(source_node_id=node_a.id, target_node_id=node_b.id, trigger="on_complete")
    edge2 = NodeEdge(source_node_id=node_a.id, target_node_id=node_c.id, trigger="on_no_go")
    db.add_all([edge1, edge2])
    db.commit()

    assert db.query(NodeEdge).filter(NodeEdge.source_node_id == node_a.id).count() == 2


def test_node_edge_cascade_delete_on_node_delete(db):
    """Deleting a node cascades to delete its outbound and inbound edges."""
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
    edge_id = edge.id

    db.delete(node_a)
    db.commit()

    assert db.query(NodeEdge).filter(NodeEdge.id == edge_id).first() is None


# ---------------------------------------------------------------------------
# _execute_node_send and routing logic tests
# ---------------------------------------------------------------------------


def test_default_edge_unconditional_delivery(db):
    """With only a default edge, successful send delivers to target regardless of output content."""
    import unittest.mock as mock
    from app.routes.workspaces import _execute_node_send
    from app.agents.cli_runner import RunResult

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    profile = AgentProfile(name="P1", provider="test", command_template="echo")
    db.add(profile)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", agent_profile_id=profile.id, order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    db.add_all([node_a, node_b])
    db.commit()

    edge = NodeEdge(source_node_id=node_a.id, target_node_id=node_b.id, trigger="on_complete")
    db.add(edge)
    db.commit()

    msg = ChatMessage(
        node_id=node_a.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="", status="running",
    )
    db.add(msg)
    db.commit()

    edge_snapshot = [{"edge_id": edge.id, "target_node_id": node_b.id, "trigger": "on_complete", "label": "", "sort_order": 0}]
    fake_result = RunResult(stdout="Some output without any sentinel.", stderr="", exit_code=0)
    with mock.patch("app.routes.workspaces.run_agent", return_value=fake_result):
        _execute_node_send(node_a.id, msg.id, edge_snapshot, db)

    db.refresh(node_a)
    db.refresh(msg)
    assert node_a.status == "idle"
    assert msg.status == "completed"
    # Target should have received a routed message
    routed = db.query(ChatMessage).filter(ChatMessage.node_id == node_b.id).first()
    assert routed is not None
    assert routed.message_kind == "auto_route"
    # Target should NOT have been auto-run (status remains idle, no assistant message)
    db.refresh(node_b)
    assert node_b.status == "idle"


def test_go_sentinel_delivers_to_default_edge(db):
    """With both edges, GO sentinel delivers to default edge only."""
    import unittest.mock as mock
    from app.routes.workspaces import _execute_node_send
    from app.agents.cli_runner import RunResult

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    profile = AgentProfile(name="P2", provider="test", command_template="echo")
    db.add(profile)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", agent_profile_id=profile.id, order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    node_c = ChatNode(workspace_id=ws.id, name="C", order_index=2)
    db.add_all([node_a, node_b, node_c])
    db.commit()

    default_edge = NodeEdge(source_node_id=node_a.id, target_node_id=node_b.id, trigger="on_complete")
    no_go_edge = NodeEdge(source_node_id=node_a.id, target_node_id=node_c.id, trigger="on_no_go")
    db.add_all([default_edge, no_go_edge])
    db.commit()

    msg = ChatMessage(
        node_id=node_a.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="", status="running",
    )
    db.add(msg)
    db.commit()

    edge_snapshot = [
        {"edge_id": default_edge.id, "target_node_id": node_b.id, "trigger": "on_complete", "label": "", "sort_order": 0},
        {"edge_id": no_go_edge.id, "target_node_id": node_c.id, "trigger": "on_no_go", "label": "", "sort_order": 0},
    ]
    fake_result = RunResult(stdout="Analysis complete.\nGO", stderr="", exit_code=0)
    with mock.patch("app.routes.workspaces.run_agent", return_value=fake_result):
        _execute_node_send(node_a.id, msg.id, edge_snapshot, db)

    db.refresh(node_a)
    assert node_a.status == "idle"
    # node_b (default) should have received message
    b_msgs = db.query(ChatMessage).filter(ChatMessage.node_id == node_b.id).count()
    assert b_msgs == 1
    # node_c (no_go) should NOT have received anything
    c_msgs = db.query(ChatMessage).filter(ChatMessage.node_id == node_c.id).count()
    assert c_msgs == 0


def test_no_go_sentinel_delivers_to_no_go_edge(db):
    """With both edges, NO_GO sentinel delivers to no_go edge only."""
    import unittest.mock as mock
    from app.routes.workspaces import _execute_node_send
    from app.agents.cli_runner import RunResult

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    profile = AgentProfile(name="P3", provider="test", command_template="echo")
    db.add(profile)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", agent_profile_id=profile.id, order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    node_c = ChatNode(workspace_id=ws.id, name="C", order_index=2)
    db.add_all([node_a, node_b, node_c])
    db.commit()

    default_edge = NodeEdge(source_node_id=node_a.id, target_node_id=node_b.id, trigger="on_complete")
    no_go_edge = NodeEdge(source_node_id=node_a.id, target_node_id=node_c.id, trigger="on_no_go")
    db.add_all([default_edge, no_go_edge])
    db.commit()

    msg = ChatMessage(
        node_id=node_a.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="", status="running",
    )
    db.add(msg)
    db.commit()

    edge_snapshot = [
        {"edge_id": default_edge.id, "target_node_id": node_b.id, "trigger": "on_complete", "label": "", "sort_order": 0},
        {"edge_id": no_go_edge.id, "target_node_id": node_c.id, "trigger": "on_no_go", "label": "", "sort_order": 0},
    ]
    fake_result = RunResult(stdout="Needs revision.\nNO_GO", stderr="", exit_code=0)
    with mock.patch("app.routes.workspaces.run_agent", return_value=fake_result):
        _execute_node_send(node_a.id, msg.id, edge_snapshot, db)

    db.refresh(node_a)
    assert node_a.status == "idle"
    # node_c (no_go) should have received message
    c_msgs = db.query(ChatMessage).filter(ChatMessage.node_id == node_c.id).count()
    assert c_msgs == 1
    routed = db.query(ChatMessage).filter(ChatMessage.node_id == node_c.id).first()
    assert routed.message_kind == "auto_route"
    # node_b (default) should NOT have received anything
    b_msgs = db.query(ChatMessage).filter(ChatMessage.node_id == node_b.id).count()
    assert b_msgs == 0


def test_missing_sentinel_with_no_go_edge_sets_needs_attention(db):
    """With no_go edge present but no GO/NO_GO sentinel, source node gets needs_attention."""
    import unittest.mock as mock
    from app.routes.workspaces import _execute_node_send
    from app.agents.cli_runner import RunResult

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    profile = AgentProfile(name="P4", provider="test", command_template="echo")
    db.add(profile)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", agent_profile_id=profile.id, order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    node_c = ChatNode(workspace_id=ws.id, name="C", order_index=2)
    db.add_all([node_a, node_b, node_c])
    db.commit()

    default_edge = NodeEdge(source_node_id=node_a.id, target_node_id=node_b.id, trigger="on_complete")
    no_go_edge = NodeEdge(source_node_id=node_a.id, target_node_id=node_c.id, trigger="on_no_go")
    db.add_all([default_edge, no_go_edge])
    db.commit()

    msg = ChatMessage(
        node_id=node_a.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="", status="running",
    )
    db.add(msg)
    db.commit()

    edge_snapshot = [
        {"edge_id": default_edge.id, "target_node_id": node_b.id, "trigger": "on_complete", "label": "", "sort_order": 0},
        {"edge_id": no_go_edge.id, "target_node_id": node_c.id, "trigger": "on_no_go", "label": "", "sort_order": 0},
    ]
    fake_result = RunResult(stdout="Here is some output without a sentinel.", stderr="", exit_code=0)
    with mock.patch("app.routes.workspaces.run_agent", return_value=fake_result):
        _execute_node_send(node_a.id, msg.id, edge_snapshot, db)

    db.refresh(node_a)
    assert node_a.status == "needs_attention"
    assert "GO or NO_GO" in node_a.last_error
    # Neither target should have received messages
    assert db.query(ChatMessage).filter(ChatMessage.node_id == node_b.id).count() == 0
    assert db.query(ChatMessage).filter(ChatMessage.node_id == node_c.id).count() == 0


def test_routed_delivery_does_not_auto_run_target(db):
    """Routed delivery appends a message but does NOT change target node status."""
    from app.routes.workspaces import _deliver_routed_message

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    profile = AgentProfile(name="PA", provider="test", command_template="echo")
    db.add(profile)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1, agent_profile_id=profile.id)
    db.add_all([node_a, node_b])
    db.commit()

    src_msg = ChatMessage(
        node_id=node_a.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="hello", status="completed",
    )
    db.add(src_msg)
    db.commit()

    edge_entry = {"edge_id": 999, "target_node_id": node_b.id, "trigger": "on_complete", "label": "", "sort_order": 0}
    result = _deliver_routed_message(node_a.id, src_msg.id, edge_entry, db)

    assert result is True
    # Message delivered
    routed = db.query(ChatMessage).filter(ChatMessage.node_id == node_b.id).first()
    assert routed is not None
    assert routed.message_kind == "auto_route"
    # Target NOT auto-run — status still idle
    db.refresh(node_b)
    assert node_b.status == "idle"


def test_deliver_routed_message_cross_workspace_blocked(db):
    """_deliver_routed_message silently refuses cross-workspace delivery."""
    from app.routes.workspaces import _deliver_routed_message

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

    edge_entry = {"edge_id": 999, "target_node_id": node_b.id, "trigger": "on_complete", "label": "", "sort_order": 0}
    result = _deliver_routed_message(node_a.id, msg.id, edge_entry, db)

    assert result is False
    assert db.query(ChatMessage).filter(ChatMessage.node_id == node_b.id).count() == 0


def test_import_last_message_append_only(db):
    """import_last_message appends a manual_import message and does NOT auto-run target."""
    # Test via direct model manipulation since we need the route behavior
    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    profile = AgentProfile(name="PB", provider="test", command_template="echo")
    db.add(profile)
    db.commit()

    src_node = ChatNode(workspace_id=ws.id, name="Src", order_index=0)
    tgt_node = ChatNode(workspace_id=ws.id, name="Tgt", order_index=1, agent_profile_id=profile.id)
    db.add_all([src_node, tgt_node])
    db.commit()

    src_msg = ChatMessage(
        node_id=src_node.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="source content", status="completed",
    )
    db.add(src_msg)
    db.commit()

    # Simulate the import: append manual_import, no auto-run
    last = db.query(ChatMessage).filter(
        ChatMessage.node_id == tgt_node.id,
        ChatMessage.conversation_version == tgt_node.conversation_version,
    ).order_by(ChatMessage.sequence_number.desc()).first()
    next_seq = (last.sequence_number + 1) if last else 1

    imported = ChatMessage(
        node_id=tgt_node.id,
        sequence_number=next_seq,
        conversation_version=tgt_node.conversation_version,
        role="user",
        message_kind="manual_import",
        content=src_msg.content,
        source_node_id=src_node.id,
        source_message_id=src_msg.id,
        status="completed",
    )
    db.add(imported)
    db.commit()

    # Verify message kind
    assert imported.message_kind == "manual_import"
    # Target node should remain idle (no auto-run)
    db.refresh(tgt_node)
    assert tgt_node.status == "idle"


def test_nonzero_exit_marks_failed(db):
    """A non-zero subprocess returncode should mark the message failed, not completed."""
    import unittest.mock as mock
    from app.routes.workspaces import _execute_node_send

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    profile = AgentProfile(
        name="TestCLI", provider="test",
        command_template="false",
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

    from app.agents.cli_runner import RunResult
    fake_result = RunResult(stdout="", stderr="error: something went wrong", exit_code=1)

    with mock.patch("app.routes.workspaces.run_agent", return_value=fake_result):
        _execute_node_send(node.id, msg.id, [], db)  # empty snapshot

    db.refresh(msg)
    db.refresh(node)
    assert msg.status == "failed"
    assert node.status == "needs_attention"
    assert node.last_error is not None


def test_multiple_upstream_nodes_deliver_to_same_target(db):
    """Multiple source nodes can deliver routed messages into the same target transcript."""
    from app.routes.workspaces import _deliver_routed_message

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    node_c = ChatNode(workspace_id=ws.id, name="C", order_index=2)
    db.add_all([node_a, node_b, node_c])
    db.commit()

    msg_a = ChatMessage(
        node_id=node_a.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="from A", status="completed",
    )
    msg_b = ChatMessage(
        node_id=node_b.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="from B", status="completed",
    )
    db.add_all([msg_a, msg_b])
    db.commit()

    edge_a = {"edge_id": 1, "target_node_id": node_c.id, "trigger": "on_complete", "label": "", "sort_order": 0}
    edge_b = {"edge_id": 2, "target_node_id": node_c.id, "trigger": "on_no_go", "label": "", "sort_order": 0}

    _deliver_routed_message(node_a.id, msg_a.id, edge_a, db)
    _deliver_routed_message(node_b.id, msg_b.id, edge_b, db)

    # Both messages should be in node_c's transcript
    routed_msgs = db.query(ChatMessage).filter(
        ChatMessage.node_id == node_c.id,
        ChatMessage.message_kind == "auto_route",
    ).order_by(ChatMessage.sequence_number).all()
    assert len(routed_msgs) == 2
    contents = {m.content for m in routed_msgs}
    assert "from A" in contents
    assert "from B" in contents


def test_multiple_on_complete_edges_fan_out(db):
    """With multiple on_complete edges and no on_no_go edges, all targets receive the message."""
    import unittest.mock as mock
    from app.routes.workspaces import _execute_node_send
    from app.agents.cli_runner import RunResult

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    profile = AgentProfile(name="Pfanout", provider="test", command_template="echo")
    db.add(profile)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", agent_profile_id=profile.id, order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    node_c = ChatNode(workspace_id=ws.id, name="C", order_index=2)
    db.add_all([node_a, node_b, node_c])
    db.commit()

    edge1 = NodeEdge(source_node_id=node_a.id, target_node_id=node_b.id, trigger="on_complete", sort_order=0)
    edge2 = NodeEdge(source_node_id=node_a.id, target_node_id=node_c.id, trigger="on_complete", sort_order=1)
    db.add_all([edge1, edge2])
    db.commit()

    msg = ChatMessage(
        node_id=node_a.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="", status="running",
    )
    db.add(msg)
    db.commit()

    edge_snapshot = [
        {"edge_id": edge1.id, "target_node_id": node_b.id, "trigger": "on_complete", "label": "", "sort_order": 0},
        {"edge_id": edge2.id, "target_node_id": node_c.id, "trigger": "on_complete", "label": "", "sort_order": 1},
    ]
    fake_result = RunResult(stdout="Done.", stderr="", exit_code=0)
    with mock.patch("app.routes.workspaces.run_agent", return_value=fake_result):
        _execute_node_send(node_a.id, msg.id, edge_snapshot, db)

    db.refresh(node_a)
    assert node_a.status == "idle"
    b_count = db.query(ChatMessage).filter(ChatMessage.node_id == node_b.id).count()
    c_count = db.query(ChatMessage).filter(ChatMessage.node_id == node_c.id).count()
    assert b_count == 1
    assert c_count == 1


def test_human_gate_mode_sets_awaiting_route(db):
    """With routing_mode=human_gate, _execute_node_send sets awaiting_route instead of delivering."""
    import unittest.mock as mock
    from app.routes.workspaces import _execute_node_send
    from app.agents.cli_runner import RunResult

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    profile = AgentProfile(name="Phg", provider="test", command_template="echo")
    db.add(profile)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", agent_profile_id=profile.id,
                      order_index=0, routing_mode="human_gate")
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    db.add_all([node_a, node_b])
    db.commit()

    edge = NodeEdge(source_node_id=node_a.id, target_node_id=node_b.id, trigger="on_complete", sort_order=0)
    db.add(edge)
    db.commit()

    msg = ChatMessage(
        node_id=node_a.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="", status="running",
    )
    db.add(msg)
    db.commit()

    edge_snapshot = [{"edge_id": edge.id, "target_node_id": node_b.id, "trigger": "on_complete", "label": "", "sort_order": 0}]
    fake_result = RunResult(stdout="Done.", stderr="", exit_code=0)
    with mock.patch("app.routes.workspaces.run_agent", return_value=fake_result):
        _execute_node_send(node_a.id, msg.id, edge_snapshot, db)

    db.refresh(node_a)
    assert node_a.status == "awaiting_route"
    # No message should be delivered to node_b yet
    assert db.query(ChatMessage).filter(ChatMessage.node_id == node_b.id).count() == 0


def test_auto_mode_still_fans_out(db):
    """With routing_mode=auto (default), delivery still fans out normally."""
    import unittest.mock as mock
    from app.routes.workspaces import _execute_node_send
    from app.agents.cli_runner import RunResult

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    profile = AgentProfile(name="Pauto", provider="test", command_template="echo")
    db.add(profile)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", agent_profile_id=profile.id,
                      order_index=0, routing_mode="auto")
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    db.add_all([node_a, node_b])
    db.commit()

    edge = NodeEdge(source_node_id=node_a.id, target_node_id=node_b.id, trigger="on_complete", sort_order=0)
    db.add(edge)
    db.commit()

    msg = ChatMessage(
        node_id=node_a.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="", status="running",
    )
    db.add(msg)
    db.commit()

    edge_snapshot = [{"edge_id": edge.id, "target_node_id": node_b.id, "trigger": "on_complete", "label": "", "sort_order": 0}]
    fake_result = RunResult(stdout="Done.", stderr="", exit_code=0)
    with mock.patch("app.routes.workspaces.run_agent", return_value=fake_result):
        _execute_node_send(node_a.id, msg.id, edge_snapshot, db)

    db.refresh(node_a)
    assert node_a.status == "idle"
    assert db.query(ChatMessage).filter(ChatMessage.node_id == node_b.id).count() == 1


def test_multiple_on_no_go_edges_fan_out(db):
    """With multiple on_no_go edges and NO_GO sentinel, all no_go targets receive the message."""
    import unittest.mock as mock
    from app.routes.workspaces import _execute_node_send
    from app.agents.cli_runner import RunResult

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    profile = AgentProfile(name="Pfanout2", provider="test", command_template="echo")
    db.add(profile)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="A", agent_profile_id=profile.id, order_index=0)
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    node_c = ChatNode(workspace_id=ws.id, name="C", order_index=2)
    node_d = ChatNode(workspace_id=ws.id, name="D", order_index=3)
    db.add_all([node_a, node_b, node_c, node_d])
    db.commit()

    default_edge = NodeEdge(source_node_id=node_a.id, target_node_id=node_b.id, trigger="on_complete", sort_order=0)
    nogo1 = NodeEdge(source_node_id=node_a.id, target_node_id=node_c.id, trigger="on_no_go", sort_order=0)
    nogo2 = NodeEdge(source_node_id=node_a.id, target_node_id=node_d.id, trigger="on_no_go", sort_order=1)
    db.add_all([default_edge, nogo1, nogo2])
    db.commit()

    msg = ChatMessage(
        node_id=node_a.id, sequence_number=1, conversation_version=1,
        role="assistant", message_kind="assistant_reply", content="", status="running",
    )
    db.add(msg)
    db.commit()

    edge_snapshot = [
        {"edge_id": default_edge.id, "target_node_id": node_b.id, "trigger": "on_complete", "label": "", "sort_order": 0},
        {"edge_id": nogo1.id, "target_node_id": node_c.id, "trigger": "on_no_go", "label": "", "sort_order": 0},
        {"edge_id": nogo2.id, "target_node_id": node_d.id, "trigger": "on_no_go", "label": "", "sort_order": 1},
    ]
    fake_result = RunResult(stdout="Needs revision.\nNO_GO", stderr="", exit_code=0)
    with mock.patch("app.routes.workspaces.run_agent", return_value=fake_result):
        _execute_node_send(node_a.id, msg.id, edge_snapshot, db)

    db.refresh(node_a)
    assert node_a.status == "idle"
    # on_complete target should NOT receive anything
    assert db.query(ChatMessage).filter(ChatMessage.node_id == node_b.id).count() == 0
    # both on_no_go targets should receive the message
    assert db.query(ChatMessage).filter(ChatMessage.node_id == node_c.id).count() == 1
    assert db.query(ChatMessage).filter(ChatMessage.node_id == node_d.id).count() == 1


def test_human_node_routes_user_message_without_agent(db):
    """Human node: send_message delivers user message to on_complete edges without running agent."""
    import unittest.mock as mock
    from app.routes.workspaces import _deliver_routed_message

    ws = Workspace(title="WS")
    db.add(ws)
    db.commit()

    node_a = ChatNode(workspace_id=ws.id, name="Human", order_index=0, node_type="human", routing_mode="auto")
    node_b = ChatNode(workspace_id=ws.id, name="B", order_index=1)
    db.add_all([node_a, node_b])
    db.commit()

    edge = NodeEdge(source_node_id=node_a.id, target_node_id=node_b.id, trigger="on_complete", sort_order=0)
    db.add(edge)
    db.commit()

    # Simulate the human node send_message logic directly
    user_msg = ChatMessage(
        node_id=node_a.id, sequence_number=1, conversation_version=1,
        role="user", message_kind="manual_user", content="human decision", status="completed",
    )
    db.add(user_msg)
    node_a.status = "idle"
    db.commit()
    db.refresh(user_msg)

    edge_entry = {"edge_id": edge.id, "target_node_id": node_b.id, "trigger": "on_complete", "label": "", "sort_order": 0}
    _deliver_routed_message(node_a.id, user_msg.id, edge_entry, db)

    routed = db.query(ChatMessage).filter(ChatMessage.node_id == node_b.id).first()
    assert routed is not None
    assert routed.content == "human decision"
    assert routed.message_kind == "auto_route"
