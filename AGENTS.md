# AGENTS.md

## Purpose

This repository is built primarily by AI coding agents.

The goal is to keep implementation deterministic, narrow, and aligned to the active spec.

## Active Source of Truth

- Implementation spec: `docs/mvp-build-spec.md`
- Execution checklist for this pass: `docs/build-plan.md`

When in doubt, follow `docs/build-plan.md`. Archived material in `docs/archive/2026-03-16/` is background only — do not pull requirements from it.

## Core Terminology

This is a clean-break redesign. The active implementation uses:

- **Run** — the unit of work (replaces Thread)
- **goal** — the user-supplied objective for a Run
- **workspace** — directory selected per Run
- **AgentProfile** — saved CLI agent config (command, name)
- **Turn** — one agent invocation within a Run
- **UserNote** — user-injected note during a Run

Do not preserve old Thread/raw-command UX. This is a dev prototype; backward compatibility is out of scope.

## Workflow Presets

Exactly two hard-coded presets exist:

- `single_agent` — one agent, runs to completion
- `builder_reviewer` — builder works, reviewer evaluates, loop until approve or max rounds

No other presets. No generalized workflow graph engine. No YAML-driven workflow config.

## Out of Scope for This Pass

Do not implement:

- DB migration framework (clean schema reset is acceptable)
- Streaming transport (polling via meta-refresh is sufficient)
- MCP integration
- YAML/policy workflow engines
- More than two agents or presets
- Confidence scoring, plugin architecture, embedded terminal
- Cloud or multi-user features

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
- `app/routes/runs.py`
- `app/routes/settings.py`
- `tests/`

## CLI Agent Assumptions

- Non-interactive CLI agents only
- Prompt passed via `stdin`; output read from `stdout`
- One fresh subprocess per Turn
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
- pause/resume/stop/note controls work

Update or add tests when behavior changes.
