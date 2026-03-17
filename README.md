# ChatMasala

A minimal local orchestration tool for running CLI-based AI agents.

## What It Does

ChatMasala lets you create Runs with a goal, select a workspace, and watch CLI agents work through that goal in a chat-style relay view — no manual copy-paste between agents.

Agents are selected from saved AgentProfiles, each of which stores a CLI command and optional flags.

## Workflow Presets

Two presets are available. No other workflows exist in this version.

- **single_agent** — one agent receives the goal and runs to completion
- **builder_reviewer** — a builder agent works on the goal, a reviewer agent evaluates the output, and the loop continues until approval or max rounds

## User Flow

1. Open the app at http://127.0.0.1:8000
2. Go to Settings to create AgentProfiles (CLI command, name)
3. Create a Run: enter a goal, select a workspace, choose a preset, assign profile(s)
4. Start the Run and watch the chat-style relay view update via polling

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
- Full spec: `docs/mvp-build-spec.md`
- Archived prior design material: `docs/archive/2026-03-16/`
