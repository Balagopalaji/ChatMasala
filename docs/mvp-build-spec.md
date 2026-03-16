# ChatMasala MVP Build Spec

This document is the active source of truth for implementation.

It is written for AI coding agents. Follow it literally. Do not expand scope unless this file is updated.

## 1. Product Goal

Build a local app that lets one user give a task and plan once, then have two CLI AI agents talk to each other without manual copy/paste.

The user should be able to:

- enter the task and plan
- configure one `builder` CLI command
- configure one `reviewer` CLI command
- start the loop
- watch the transcript
- pause, stop, or inject a note

## 2. Core Value

The value of the MVP is not "chat UI".

The value is:

- no manual relay between agents
- deterministic handoff rules
- complete transcript of what happened
- simple control when the loop gets stuck

If a feature does not improve one of those four things, it is probably out of scope.

## 3. Non-Goals

Do not build any of the following in the MVP:

- more than two agents
- arbitrary workflow graphs
- policy packs as a configurable framework
- confidence scoring
- generalized plugin system
- embedded terminal emulator
- RepoPrompt integration
- multi-user auth
- cloud deployment
- mobile UI
- autonomous planning or autonomous routing

## 4. User and Environment Assumptions

- Single user
- Local machine only
- CLI agents are already installed by the user
- CLI agents used by the MVP must support non-interactive execution
- MVP assumes prompts are sent through `stdin` and final output is read from `stdout`
- Interactive REPL-style agents are out of scope for the first version

This last constraint is important. It keeps the first version simple and buildable.

## 5. Frozen MVP Workflow

There is only one workflow in the MVP:

1. User creates a thread with:
   - title
   - task
   - plan
   - builder command
   - reviewer command
   - optional working directory
   - max review rounds, default `3`
2. App sends the initial prompt to the `builder`.
3. Builder returns structured output.
4. App parses the builder output.
5. If parsing fails, thread enters `waiting_for_user`.
6. If parse succeeds and builder says `READY_FOR_REVIEW`, app sends a reviewer prompt.
7. Reviewer returns structured output.
8. App parses the reviewer output.
9. If reviewer says `CHANGES_REQUESTED` and rounds remain, app sends the reviewer feedback back to the builder.
10. If reviewer says `APPROVE`, thread enters `done`.
11. If reviewer says `BLOCKED`, parsing fails, process exits unexpectedly, or max rounds are hit, thread enters `waiting_for_user`.

Do not invent alternate routing rules.

## 6. Required Structured Output Contracts

The MVP must use strict structured outputs so routing is reliable.

### Builder contract

```text
===STRUCTURED_OUTPUT===
STATUS: READY_FOR_REVIEW|BLOCKED
SUMMARY: <short text>
CHANGED_ARTIFACTS: <paths or none>
CHECKS_RUN: <name>=PASS|FAIL|NOT_RUN ...
BLOCKERS: <text or none>
HANDOFF_NOTE: <short reviewer-oriented note>
===END_STRUCTURED_OUTPUT===
```

### Reviewer contract

```text
===STRUCTURED_OUTPUT===
VERDICT: APPROVE|CHANGES_REQUESTED|BLOCKED
SUMMARY: <short text>
OPEN_ISSUES: <short text or none>
CHECKS_VERIFIED: <name>=PASS|FAIL|NOT_RUN ...
NEXT_ACTION: reroute_builder|wait_for_user|close_thread
RATIONALE: <short text>
===END_STRUCTURED_OUTPUT===
```

## 7. Prompt Construction Rules

Keep prompt construction deterministic and simple.

### Builder prompt must include

- role statement: "You are the builder"
- task
- plan
- latest reviewer feedback if present
- latest user note if present
- builder structured output contract

### Reviewer prompt must include

- role statement: "You are the reviewer"
- task
- plan
- latest builder output
- latest user note if present
- reviewer structured output contract

Do not add policy layering, confidence thresholds, or summary providers in the MVP.

## 8. States

Use only these thread states:

- `draft`
- `running`
- `waiting_for_agent`
- `waiting_for_user`
- `paused`
- `done`
- `failed`

Use only these turn states:

- `pending`
- `running`
- `succeeded`
- `parse_failed`
- `process_failed`
- `cancelled`

## 9. Minimal Data Model

Use SQLite. Keep the schema small.

### Thread

- `id`
- `title`
- `task_text`
- `plan_text`
- `builder_command`
- `reviewer_command`
- `working_directory` nullable
- `status`
- `current_role` nullable, values `builder|reviewer`
- `round_count`
- `max_rounds`
- `last_error` nullable
- `created_at`
- `updated_at`

### Turn

- `id`
- `thread_id`
- `role`, values `builder|reviewer|user|system`
- `sequence_number`
- `prompt_text`
- `raw_output_text` nullable
- `parsed_json` nullable
- `status`
- `started_at` nullable
- `ended_at` nullable

### UserNote

- `id`
- `thread_id`
- `note_text`
- `created_at`

No extra tables are required for the MVP.

## 10. Required Backend Components

Implement these modules:

- `app/main.py`
- `app/db.py`
- `app/models.py`
- `app/schemas.py`
- `app/parser.py`
- `app/prompts.py`
- `app/agents/cli_runner.py`
- `app/orchestrator.py`
- `app/routes/threads.py`

Suggested support files:

- `app/templates/`
- `app/static/`
- `tests/`

## 11. CLI Runner Rules

The CLI runner is the most important technical seam.

Required behavior:

- run one command for one turn
- send the full prompt over `stdin`
- capture `stdout`
- capture `stderr`
- collect exit code
- persist raw output even on parse failure

MVP simplification:

- treat each turn as a fresh subprocess invocation
- do not keep long-lived interactive sessions open
- do not build PTY support yet

This is intentional. Fresh process per turn is slower but much simpler and more reliable for version one.

## 12. Orchestrator Rules

The orchestrator must be deterministic.

### Start thread

- allowed only from `draft`
- creates first builder turn
- sets thread status to `waiting_for_agent`
- launches builder subprocess

### After builder success

- if parse fails: `waiting_for_user`
- if `STATUS=BLOCKED`: `waiting_for_user`
- if `STATUS=READY_FOR_REVIEW`: create reviewer turn and launch reviewer

### After reviewer success

- if parse fails: `waiting_for_user`
- if `VERDICT=BLOCKED`: `waiting_for_user`
- if `VERDICT=APPROVE`: `done`
- if `VERDICT=CHANGES_REQUESTED` and `round_count < max_rounds`: increment round count and send reviewer feedback to builder
- if `VERDICT=CHANGES_REQUESTED` and `round_count >= max_rounds`: `waiting_for_user`

### Pause

- allowed from `running` or `waiting_for_agent`
- prevents the next automatic handoff

### Resume

- allowed from `paused`
- continues from the last unresolved step

### Stop

- allowed from any non-terminal state
- sets thread to `failed`

### Inject note

- allowed from `waiting_for_user`, `paused`, or `running`
- note is stored and appended to the next prompt

## 13. UI Requirements

Use the simplest possible web UI.

Recommended approach:

- FastAPI server
- Jinja templates
- vanilla JavaScript only where necessary

Do not use a frontend framework for the MVP unless there is a concrete need.

### Required pages

#### Thread list page

- create new thread button
- thread rows with status, current role, updated time

#### New thread page

- title input
- task textarea
- plan textarea
- builder command input
- reviewer command input
- working directory input
- max rounds input

#### Thread detail page

- thread metadata
- current status
- transcript in chronological order
- latest parsed values for each agent turn
- buttons: `start`, `pause`, `resume`, `stop`
- inject note form

No dashboard, analytics, or advanced filtering.

## 14. Error Handling

The app must fail visibly, not silently.

Required error cases:

- subprocess command not found
- subprocess exits non-zero
- no stdout returned
- parse failure
- invalid working directory
- database write failure

For every error:

- persist the raw details
- update `thread.last_error`
- move thread to `waiting_for_user` or `failed`
- show the error clearly on the thread detail page

## 15. Testing Requirements

Write tests for the parts that control correctness.

Minimum required tests:

- parser accepts valid builder output
- parser rejects malformed builder output
- parser accepts valid reviewer output
- parser rejects malformed reviewer output
- orchestrator routes builder success to reviewer
- orchestrator routes reviewer approve to done
- orchestrator routes reviewer changes requested back to builder
- orchestrator stops at max rounds
- subprocess failure moves thread to non-running state

Do not skip parser and routing tests.

## 16. Definition of Done

The MVP is complete when all of the following are true:

- user can create a thread in the UI
- user can start a builder/reviewer loop from the UI
- prompts are sent to CLI agents without manual copy/paste
- outputs are persisted and visible in the transcript
- structured output parsing drives deterministic routing
- user can pause, resume, stop, and inject a note
- parse failures and process failures are visible and recoverable
- tests cover parser and routing behavior

## 17. Post-MVP Ideas

These are explicitly deferred:

- long-lived agent sessions
- interactive terminal support
- more than two roles
- reusable workflow profiles
- configurable policies
- confidence thresholds
- richer context providers
- archive replay tools
- metrics
- external integrations

If future work needs those ideas, consult `docs/archive/2026-03-16/`, but do not import them into active implementation by default.
