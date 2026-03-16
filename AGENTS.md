# AGENTS.md

## Purpose

This repository is built primarily by AI coding agents.

The goal is to keep implementation deterministic, narrow, and aligned to the active MVP.

## Active Source of Truth

Use this file as the implementation authority:

- `docs/mvp-build-spec.md`

Treat archived material as background only:

- `docs/archive/2026-03-16/`

Do not pull requirements from the archive unless the active spec is explicitly updated to include them.

## Product Boundary

Build only the current MVP:

- one user
- local machine only
- two CLI agents only: `builder` and `reviewer`
- one fixed workflow: `builder -> reviewer -> builder`
- deterministic routing based on strict structured output parsing
- transcript plus basic controls

Do not add:

- more than two agents
- generalized workflow graphs
- policy-pack framework
- confidence scoring
- plugin architecture beyond the minimal CLI runner seam
- RepoPrompt integration
- embedded terminal emulator
- frontend framework unless clearly necessary
- cloud or multi-user features

## Implementation Priorities

Optimize for:

1. deterministic behavior
2. simple implementation
3. easy recovery from failures
4. AI-agent readability
5. low abstraction count

Do not optimize for extensibility before the MVP works.

## Required Stack

Unless the active spec changes, prefer:

- Python
- FastAPI
- Jinja templates
- vanilla JavaScript only where needed
- SQLite
- SQLAlchemy if persistence layer needs ORM support

If a simpler approach satisfies the active spec, prefer the simpler approach.

## Required Project Shape

Target these modules unless there is a strong reason to adjust:

- `app/main.py`
- `app/db.py`
- `app/models.py`
- `app/schemas.py`
- `app/parser.py`
- `app/prompts.py`
- `app/agents/cli_runner.py`
- `app/orchestrator.py`
- `app/routes/threads.py`
- `tests/`

## CLI Agent Assumptions

The MVP assumes:

- non-interactive CLI agents
- prompt passed through `stdin`
- final output read from `stdout`
- one fresh subprocess per turn

Do not introduce PTY management or long-lived interactive sessions in the MVP.

## Output Contract Rules

Routing must depend on strict structured outputs.

Agents implementing this repo must preserve and enforce the contracts defined in:

- `docs/mvp-build-spec.md`

If parsing fails, fail visibly and route to user attention rather than guessing.

## Archive Rule

Archived docs contain broader ideas that are intentionally out of scope for now.

They may be useful later for:

- richer recovery
- more workflows
- policy systems
- provider abstractions

They are not current requirements.

## Validation Rule

Do not claim the MVP is complete unless the following are covered:

- parser success/failure tests
- routing tests
- visible transcript persistence
- visible failure states
- pause/resume/stop/note controls

When making implementation changes, update tests or add tests when behavior changes.

## Decision Rule

When a choice exists between:

- a smaller deterministic implementation, and
- a more extensible generalized implementation

choose the smaller deterministic implementation.
