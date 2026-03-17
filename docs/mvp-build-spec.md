# ChatMasala MVP Build Spec

This document is the active source of truth for implementation.

Written for AI coding agents. Follow it literally. Do not expand scope unless this file is updated.

For the current implementation sequence, use `docs/build-plan.md`.

---

## 1. Product Goal

Build a local app that lets a user create a Run with a goal, assign CLI agents via AgentProfiles, select a workspace, and watch agents work in a chat-style relay view — with no manual copy-paste between agents.

---

## 2. Core Models

### Run

- `id`
- `goal` — user-supplied objective
- `workspace` — directory path for the run
- `workflow_preset` — `single_agent` or `builder_reviewer`
- `status` — `draft`, `running`, `waiting_for_user`, `paused`, `done`, `failed`
- `current_role` — nullable; `builder` or `reviewer`
- `round_count`
- `max_rounds`
- `last_error` — nullable
- `created_at`, `updated_at`

### Turn

- `id`
- `run_id`
- `role` — `builder`, `reviewer`, `user`, `system`
- `sequence_number`
- `prompt_text`
- `raw_output_text` — nullable
- `parsed_json` — nullable
- `status` — `pending`, `running`, `succeeded`, `parse_failed`, `process_failed`, `cancelled`
- `started_at`, `ended_at` — nullable

### UserNote

- `id`
- `run_id`
- `note_text`
- `created_at`

### AgentProfile

- `id`
- `name`
- `cli_command` — the shell command to invoke the agent
- `created_at`

No other tables are required for this pass.

---

## 3. Workflow Presets

Exactly two hard-coded presets. No general workflow engine.

### single_agent

1. User creates a Run with a goal, workspace, and one AgentProfile.
2. App sends the goal as a prompt to the agent.
3. Agent returns structured output.
4. Run moves to `done` on success, `waiting_for_user` on parse or process failure.

### builder_reviewer

1. User creates a Run with a goal, workspace, and two AgentProfiles (builder, reviewer).
2. App sends the initial prompt to the builder.
3. Builder returns structured output.
4. If parse fails or `STATUS=BLOCKED`: `waiting_for_user`.
5. If `STATUS=READY_FOR_REVIEW`: send reviewer prompt.
6. Reviewer returns structured output.
7. If `VERDICT=APPROVE`: `done`.
8. If `VERDICT=CHANGES_REQUESTED` and rounds remain: send feedback to builder, increment round count.
9. If `VERDICT=CHANGES_REQUESTED` and max rounds hit: `waiting_for_user`.
10. If parse fails or `VERDICT=BLOCKED`: `waiting_for_user`.

Do not invent alternate routing rules.

---

## 4. Structured Output Contracts

### Builder contract

```
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

```
===STRUCTURED_OUTPUT===
VERDICT: APPROVE|CHANGES_REQUESTED|BLOCKED
SUMMARY: <short text>
OPEN_ISSUES: <short text or none>
CHECKS_VERIFIED: <name>=PASS|FAIL|NOT_RUN ...
NEXT_ACTION: reroute_builder|wait_for_user|close_thread
RATIONALE: <short text>
===END_STRUCTURED_OUTPUT===
```

If parsing fails, move the Run to `waiting_for_user` and surface the error. Do not guess.

---

## 5. Routes

- `GET /` — Run list; create new Run button
- `GET /runs/new` — new Run form
- `POST /runs` — create Run
- `GET /runs/{id}` — Run detail with chat relay view
- `POST /runs/{id}/start` — start the Run
- `POST /runs/{id}/pause` — pause
- `POST /runs/{id}/resume` — resume
- `POST /runs/{id}/stop` — stop
- `POST /runs/{id}/notes` — inject a UserNote
- `GET /settings` — list AgentProfiles
- `POST /settings/profiles` — create AgentProfile
- `DELETE /settings/profiles/{id}` — delete AgentProfile

---

## 6. UI Requirements

- FastAPI + Jinja2 templates
- Vanilla JS only where needed
- Chat-style relay view on the Run detail page
- Polling via `<meta http-equiv="refresh">` — no streaming, no WebSocket
- No frontend framework

---

## 7. CLI Runner Rules

- One fresh subprocess per Turn
- Send full prompt via `stdin`
- Capture `stdout`, `stderr`, exit code
- Persist raw output even on parse failure
- No PTY management, no long-lived sessions

---

## 8. Out of Scope for This Pass

- DB migration framework — clean schema reset is acceptable
- Streaming transport
- MCP integration
- YAML/policy workflow engines
- More than two workflow presets
- Confidence scoring, plugin architecture, embedded terminal
- Cloud or multi-user features

---

## 9. Definition of Done

- User can create a Run and assign AgentProfiles in the UI
- User can start a Run and watch the chat relay view update
- Prompts are sent to CLI agents without manual copy-paste
- Outputs are persisted and visible in the transcript
- Structured output parsing drives deterministic routing
- User can pause, resume, stop, and inject a note
- Parse failures and process failures are visible and recoverable
- Tests cover parser and routing behavior
