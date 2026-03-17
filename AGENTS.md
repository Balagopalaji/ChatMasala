# AGENTS.md

## Purpose

This repository is built primarily by AI coding agents.

The goal is to keep implementation deterministic, narrow, and aligned to the active spec.

## Active Source of Truth

- **Primary implementation plan: `docs/build-plan.md`** — this is the workspace-first direction. Follow it.
- Legacy spec (secondary, may conflict): `docs/mvp-build-spec.md`

`docs/build-plan.md` overrides `docs/mvp-build-spec.md` wherever they conflict. If `docs/mvp-build-spec.md` describes a run/preset product model that contradicts the workspace-first direction in `docs/build-plan.md`, follow `docs/build-plan.md`.

Archived material in `docs/archive/2026-03-16/` is background only — do not pull requirements from it.

## Core Terminology

This is a bounded rebuild of the product surface (not a full rewrite). The active implementation uses:

- **Workspace** — the top-level session containing one or more chat nodes (replaces Run as the primary user concept)
- **ChatNode** — a single chat/agent node within a workspace
- **ChatMessage** — one message in a node's transcript (replaces Turn/UserNote)
- **AgentProfile** — retained internally as CLI config storage; reframed in UX as user-facing "Agent" choices
- **workspace_path** — optional filesystem directory for CLI execution, selected per workspace

Do not use old Thread/Run/Turn/UserNote as the primary product vocabulary in new code or UI.

## Product Direction

ChatMasala is a **workspace-first multi-chat routing app**. This is a **bounded rebuild**, not a full rewrite.

The existing backend/runtime pieces that are still good are kept:

- FastAPI app structure
- SQLite / SQLAlchemy
- CLI runner seam
- background-task DB session pattern
- advanced instruction-file internals

What is being rebuilt:

- primary information architecture
- current run-first product model and UI surfaces
- agent selection UX
- workspace selection UX
- routing / import UX

The mockups in `tmp/Multi-Chat Workflow Builder/` communicate the intended product feel and structure. They are design intent, not production code. Do not copy prototype code from `tmp/` directly into the app.

## Workflow Presets Are Not The Product Model

The old `single_agent` and `builder_reviewer` preset model is not the product surface for this pass.

- Do not present presets as the primary workflow choice in new UI.
- Structured-output contracts (builder/reviewer parsing) may remain available internally for advanced flows, but are not the default execution model for workspace nodes.
- Normal chat nodes should behave like normal conversational CLI agents, not structured-output state machines.

## Out of Scope for This Pass

Do not implement:

- DB migration framework (clean schema reset is acceptable)
- Streaming transport (polling via meta-refresh is sufficient)
- MCP integration
- YAML/policy workflow engines
- Arbitrary graph engine or multi-output routing
- Drag/drop graph editing
- Orchestrator/scribe node types
- Confidence scoring, plugin architecture, embedded terminal
- Cloud or multi-user features
- Electron migration
- Provider-auth platform work beyond simple local CLI detection/config

## Required Stack

- Python, FastAPI, SQLite, SQLAlchemy
- Jinja2 templates
- Vanilla JavaScript only where needed
- Polling via meta-refresh for relay view updates

## Required Project Shape

- `app/main.py`
- `app/db.py`
- `app/models.py`
- `app/schemas.py`
- `app/parser.py`
- `app/prompts.py`
- `app/agents/cli_runner.py`
- `app/orchestrator.py`
- `app/routes/workspaces.py`
- `app/routes/settings.py`
- `tests/`

## CLI Agent Assumptions

- Non-interactive CLI agents only
- Prompt passed via `stdin`; output read from `stdout`
- One fresh subprocess per ChatMessage execution
- No PTY management or long-lived sessions

## Implementation Priorities

1. Deterministic behavior
2. Simple implementation
3. Easy failure recovery
4. AI-agent readability
5. Low abstraction count

Choose the smaller deterministic implementation over a more extensible generalized one.

## Validation Rule

Do not claim the implementation is complete unless:

- parser success/failure tests pass
- routing tests pass
- transcript is visible and persisted
- failure states are visible
- node reset/delete controls work
- manual import and automatic routing work and are visibly distinct

Update or add tests when behavior changes.
