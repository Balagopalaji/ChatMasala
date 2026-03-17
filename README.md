# ChatMasala

A workspace-first multi-chat routing app for local CLI-based AI agents.

## What It Does

ChatMasala lets you open a workspace and arrange multiple chat nodes inside it. Each node runs independently with its own agent and conversation context. Nodes can route output to other nodes automatically, or you can manually import messages from one node into another.

The top workflow view and the lower chat panels are two synchronized views of the same graph — switching between them shows you the same state from different angles.

## Workspaces And Nodes

- A **workspace** is the top-level session. It holds a set of chat nodes and an optional filesystem path for CLI execution.
- A **chat node** is a single chat conversation within a workspace. Each node has its own agent, transcript, and optional downstream route.
- A **chat message** is one turn in a node's transcript. Messages can be typed by the user, returned by an agent, imported from another node, or delivered by automatic routing.

## Agent Choices

Each node can use a different agent. Supported choices:

- **Claude Sonnet**
- **Claude Opus**
- **Codex CLI**
- **Gemini CLI**
- **Custom** — any CLI agent you configure in Settings

## Routing And Import

- **Automatic route** — when a node finishes, its output can be delivered automatically to one downstream node. Each node supports one downstream route in this pass.
- **Manual import** — you can explicitly import the latest assistant message from any other node in the workspace into the current node.

These two mechanisms are intentionally distinct. Automatic routing is a passive delivery. Manual import is a deliberate user action.

## Two Views, One Graph

The top of the workspace shows a workflow overview of all nodes and their connections. The bottom shows chat panels for each node. Both views reflect the same underlying state. Focusing a node in one view updates focus in the other.

## Tech

- FastAPI + SQLite + SQLAlchemy
- Jinja2 templates, vanilla JS only where needed
- Polling via meta-refresh (no streaming)
- Local SQLite database; clean-break schema reset is acceptable in this pass

## Local Setup

Requirements: Python 3.11+

```bash
cd /path/to/ChatMasala
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

## Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

## Implementation Reference

- Active execution checklist: `docs/build-plan.md`
- Secondary/legacy spec: `docs/mvp-build-spec.md`
- Archived prior design material: `docs/archive/2026-03-16/`
