# ChatMasala

A workspace-first multi-agent chat routing application. Arrange multiple AI agents as nodes in a workspace, wire them together with typed edges, and route messages through the graph automatically or via manual human checkpoints.

## Architecture / Key Features

### Workspace → Node → Edge model

- A **workspace** is the top-level session. It holds a set of chat nodes and an optional filesystem path for CLI agent execution.
- A **chat node** is a single conversation thread within a workspace. Each node has its own agent, transcript, and conversation version.
- A **node edge** connects one node's output to one or more target nodes. Multiple outbound edges per node are supported.

### Multi-output edges (fan-out routing)

Each node can have any number of outbound `NodeEdge` entries. Two trigger types:

- `on_complete` — delivered when the agent finishes successfully (or unconditionally if no `on_no_go` edges exist on the node)
- `on_no_go` — delivered when the agent's final output line is the `NO_GO` sentinel

When an agent responds, all matching edges receive the output simultaneously (fan-out). Delivered messages are appended to target node transcripts; target nodes never auto-run.

### GO / NO_GO sentinel detection

If a node has any `on_no_go` edges, the assistant output's final trimmed line is inspected:

- `GO` → fan-out to all `on_complete` edges
- `NO_GO` → fan-out to all `on_no_go` edges
- Neither → source node enters `needs_attention` status; no delivery

If no `on_no_go` edges exist, delivery to `on_complete` edges is unconditional.

### Human-gate routing mode

Each node has a `routing_mode` toggle:

- **Auto** (default) — routing fires immediately after the agent responds
- **Human gate** — after the agent responds, the node enters `awaiting_route` status. A panel appears in the UI where the user selects which outbound edges to activate, then manually confirms. Prevents new sends until routed or reset.

### Human-input node type

Each node has a `node_type` toggle:

- **Agent** (default) — sends the user's message to the configured CLI agent, waits for a reply, then routes
- **Human input** — skips the agent entirely. The user's own message is treated as the output and routed directly to downstream edges. Useful for human decision points in a workflow.

### Workflow view

The top of the workspace shows a visual workflow strip of all nodes and their edge connections. The bottom shows chat panels for each node. Both views reflect the same underlying state.

## Tech Stack

- **FastAPI** — async HTTP, background tasks, form-based routing
- **SQLAlchemy** + **SQLite** — ORM models, cascade deletes, constraint enforcement
- **Jinja2** — server-rendered templates, no frontend build step
- **Vanilla JS** — polling, auto-grow textarea, focus sync between views
- **pytest** — 96 tests, all passing

## Local Setup

Requirements: Python 3.11+

```bash
cd /path/to/ChatMasala
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open `http://localhost:8000` in your browser.

## Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

All 96 tests pass against an in-memory SQLite database.

## Implementation Reference

- Build plan and design decisions: `docs/build-plan.md`
- Archived prior design material: `docs/archive/`
