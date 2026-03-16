# Multi-Agent Handoff Runtime: Intent + Spec (MVP/V1)

## 1) Product Intent

### 1.1 Core Intent
Build a lightweight multi-agent handoff runtime that enables reliable agent-to-agent collaboration with minimal babysitting and always-available user override.

### 1.2 Completion Intent (Quality, not just flow)
`Done` means policy-verified closure against explicit acceptance criteria, not merely reaching the last step in a route.

### 1.3 Design Principles
1. Agents are black boxes; orchestrator manages handoffs, state, and policy checks.
2. Deterministic routing over autonomous routing in v1.
3. Human override is always available.
4. Logs/ledger are first-class and auditable.
5. Keep v1 small: avoid embedded terminals, social integrations, and complex AI-heavy routing.

### 1.4 Anti-Intent (What This Must Not Become)
1. Not an autonomous system that makes irreversible decisions without traceability.
2. Not a hidden-reasoning router where users cannot inspect why transitions happened.
3. Not a replacement for specialist agents; it is a coordination layer.

### 1.5 "Minimal Babysitting" Operational Definition
1. User can leave an active thread and return to deterministic progress or explicit escalation.
2. System does not require manual copy/paste between agent steps in normal operation.
3. System escalates only for true blocks: parse failures, max cycles, failed mandatory gates, or explicit user-required approvals.

## 2) Scope

### 2.1 MVP/V1 In Scope
1. Workflow templates:
   - `linear`: A -> B -> C
   - `ping_pong`: Builder <-> Reviewer until closure or cap reached
2. Per-thread setup:
   - task goal
   - acceptance criteria
   - role prompts (per agent role)
   - policy pack (global + role-specific constraints)
3. Deterministic routing based on parseable outputs and rule matches.
4. Execution states and recovery:
   - pause/resume
   - retry from last step
   - swap agent endpoint and continue
5. Ledger/timeline with route reason for every handoff.
6. Auto mode plus optional handoff preview/edit.
7. `max_cycles` configurable 1..5 (default 3).

### 2.2 Out of Scope (V2+)
1. Embedded terminal emulator UI.
2. WhatsApp/Telegram multi-user channels.
3. Autonomous policy-generation/routing via LLM.
4. Deep RepoPrompt context integration (add seam only in v1).
5. Full cost/token accounting (optional telemetry later).

## 3) User Stories

1. As a user, I can set up Builder/Reviewer ping-pong and leave it running.
2. As a user, I can require closure gates (tests/docs/evidence) before thread completion.
3. As a user, I can pause, resume, reroute, or inject notes at any point.
4. As a user, I can see exactly why a route occurred.
5. As a user, I can recover from crashes without restarting the entire thread.
6. As a user, I can save and reuse workflow profiles.

## 4) Intent Contract (Per Thread)

Each thread must include:
1. `goal`: intended outcome.
2. `acceptance_criteria`: conditions for successful closure.
3. `workflow_template`: `linear` or `ping_pong`.
4. `policy_pack`: closure rules, quality thresholds, guardrails.
5. `agents`: endpoints + role prompts.
6. `stop_conditions`: max cycles, escalation behavior, manual overrides.

Thread cannot start unless all six are present.

## 5) Data Model (Minimal)

## 5.1 AgentEndpoint
- `id`
- `name`
- `adapter_type` (cli initially)
- `launch_config` (command/env/cwd)
- `role_prompt_id`
- `status` (available, busy, offline)

## 5.2 PromptProfile
- `id`
- `role` (builder, reviewer, planner, critic, etc.)
- `system_prompt`
- `output_contract` (required fields/tags)

## 5.3 PolicyPack
- `id`
- `global_rules`
- `role_rules`
- `mandatory_gates`
- `closure_conditions`
- `confidence_threshold` (default 0.95 configurable)

## 5.4 Thread
- `id`
- `goal`
- `acceptance_criteria`
- `workflow_template`
- `agent_assignments` (role -> agent_endpoint_id)
- `status` (queued, running, waiting_for_agent, waiting_for_user, paused, failed, done)
- `current_step`
- `cycle_count`
- `max_cycles`
- `policy_pack_id`
- `created_at`, `updated_at`

## 5.5 Turn
- `id`
- `thread_id`
- `from_actor` (user/agent)
- `to_actor`
- `input_payload_ref`
- `output_ref`
- `parsed_contract`
- `verdict` (GO, NO-GO, INFO, BLOCKED)
- `route_reason`
- `started_at`, `ended_at`
- `status` (running, success, failed, timed_out, cancelled)

## 5.6 LedgerEvent
- `id`
- `thread_id`
- `event_type`
- `message`
- `metadata`
- `timestamp`

## 5.7 WorkflowProfile
- `id`
- `name`
- `workflow_template`
- `agent_assignments`
- `prompt_profile_bindings`
- `policy_pack_id`
- `default_stop_conditions`
- `created_at`, `updated_at`

## 6) State Machine

1. `queued` -> `running` on start.
2. `running` -> `waiting_for_agent` when a turn dispatches.
3. `waiting_for_agent` -> `running` when output received/parsed.
4. `running` -> `waiting_for_user` if policy requires manual decision or escalation.
5. `running` -> `paused` on user action.
6. `paused` -> `running` on resume.
7. `running` -> `done` only if closure conditions pass.
8. Any active state -> `failed` on unrecoverable adapter/system failure.

No terminal completion unless policy closure passes.

## 7) Routing Rules

## 7.0 Cycle Definition
For `ping_pong`, one cycle = one reviewer decision after a builder submission.
- Builder -> Reviewer -> Reviewer verdict completes one cycle.
- `max_cycles` applies to reviewer verdict count, not raw turn count.

## 7.1 Ping-Pong Default
1. Builder output -> Reviewer.
2. Reviewer `VERDICT=CHANGES_REQUESTED` and cycles < max -> Builder.
3. Reviewer `VERDICT=APPROVE` + gates pass + confidence threshold pass -> Close.
4. Cycles >= max and not approved -> Escalate to user (`waiting_for_user`).

## 7.2 Linear Default
1. Always route to next role.
2. If any mandatory gate fails at stage boundary, escalate to user.
3. Final stage requires closure checks before done.

## 7.3 Route Reason
Every transition writes deterministic reason:
- matched rule id
- parsed field values used
- gate/threshold results

## 8.1) Output Contract (Reviewer Minimum)

Reviewer prompt must require these parseable fields:
1. `VERDICT: APPROVE | CHANGES_REQUESTED | BLOCKED`
2. `CONFIDENCE: <0..1>`
3. `OPEN_FINDINGS: P0=<n> P1=<n> P2=<n> P3=<n>`
4. `SCOPE_OK: YES|NO`
5. `POLICY_COMPLIANCE: PASS|FAIL`
6. `GATES: <name>=PASS|FAIL ...`
7. `NEXT_ACTION: <reroute_builder|escalate_user|close_candidate>`
8. `RATIONALE: <short text>`

If parser fails, treat as `BLOCKED` and escalate to user.

## 8.2 Output Contract (Builder Minimum)
Builder prompt must require these parseable fields:
1. `STATUS: READY_FOR_REVIEW | BLOCKED`
2. `SUMMARY: <short text>`
3. `CHANGED_ARTIFACTS: <paths or none>`
4. `CHECKS_RUN: <name>=PASS|FAIL|NOT_RUN ...`
5. `BLOCKERS: <text or none>`
6. `HANDOFF_NOTE: <short reviewer-oriented note>`

If parser fails, mark turn as `BLOCKED` and escalate to user.

## 8.3 Parser Specification (V1)
1. Required fields must be emitted inside one fenced block:
   ```text
   ===STRUCTURED_OUTPUT===
   KEY: value
   ...
   ===END_STRUCTURED_OUTPUT===
   ```
2. Parser behavior:
   - strict key match for required fields
   - case-insensitive values where enumerated
   - numeric parse for confidence (`0 <= x <= 1`)
3. On partial parse, missing required field => parse failure.
4. Parse failure is always logged with exact missing/invalid keys.

## 9) Context/Handoff Payload

V1 payload:
1. role prompt (current recipient)
2. thread goal
3. acceptance criteria
4. compact thread summary
5. previous relevant output(s)
6. optional user note
7. policy snippet relevant to this role

`context_mode` in v1:
- `none`
- `basic` (default)

V2 seam:
- `repoprompt` mode for richer context pack integration.

### 9.1 Context Layering (V1)
1. Role layer: role prompt + role policy.
2. Thread layer: goal + acceptance criteria + closure bar.
3. Turn layer: last relevant outputs + latest structured fields.
4. Session layer: latest user override/injected note.

### 9.2 Relevance Rules (V1)
1. Always include immediately previous turn output.
2. Include latest failed-review turn (if exists).
3. Include latest user injection (if exists) with highest priority.
4. For linear flows, each role sees immediate predecessor output; optional `include_upstream=true` includes all prior stage summaries.

### 9.3 Budget/Truncation Rules (V1)
1. Max payload chars configurable per agent; default 30,000 chars.
2. Preserve in this order: policy fields, structured outputs, latest turn, latest user note.
3. Truncate oldest verbose narrative first.
4. If still over limit, include only structured summaries of older turns.

### 9.4 Checkpoint Serialization (Recovery)
Persist per dispatch:
1. prompt input refs (role/thread/turn/session refs)
2. prompt hash (`sha256` of fully rendered payload)
3. agent endpoint id and launch config hash
4. parser results
5. route decision and rule id
6. cycle count + retry count

Full rendered payload persistence is disabled by default in v1 and enabled only via debug flag.

### 9.5 Deterministic Summary Fallback (Basic Mode)
When no `SummaryProvider` model is configured, summary generation is deterministic:
1. include latest 2 structured-output blocks verbatim
2. include latest reviewer verdict block verbatim (if exists)
3. include latest user injection note verbatim (if exists)
4. append a fixed-format line:
   - `STATE: <status>; CYCLES: <n>/<max>; LAST_ROUTE: <rule_id>; OPEN_HIGH: P0=<n>,P1=<n>,P2=<n>`
5. max 1,200 chars; trim oldest narrative fragments first

## 10) Policy Pack (Inspired by Existing High-Discipline Prompts)

Use a layered policy model:
1. Global policy addendum: applies to all roles in thread.
2. Role closure policy: role-specific constraints (example: reviewer loop closure).
3. Mandatory gates: command checks and evidence/docs requirements.
4. Acceptance bar: thresholds, severity rules, and confidence floor.

Closure example:
1. No open P0/P1/P2.
2. All mandatory gates pass.
3. Evidence mapping complete (if required for thread).
4. Confidence >= threshold (default 0.95).
5. Docs sync obligations complete (if required for thread).

### 10.1 Policy Precedence
1. System safety rules
2. Global policy rules
3. Role policy rules
4. Thread custom overrides
5. Prompt stylistic instructions

Higher level always wins on conflict.

### 10.2 Mandatory Gates: Global vs Thread-Custom
Global defaults (v1 baseline):
1. Structured output parse pass.
2. Required verdict/status fields present.
3. No unresolved parser errors.

Thread-custom gates (optional):
1. Command gates (tests/lint/build).
2. Evidence mapping gates.
3. Docs sync gates.
4. Domain-specific contract checks.

### 10.3 Independent E2E Validation Gate (Dark Factory Requirement)
For coding/build threads that change runtime behavior, policy must define an independent E2E gate:
1. Spec must include an E2E behavior oracle (observable outcomes, not implementation details).
2. Builder agent must not author the final E2E test implementation used for closure.
3. E2E tests used for closure are authored by a separate test-writer role (agent or human).
4. Thread cannot close as `done` unless this independent E2E gate passes (or explicit user override is recorded in ledger).

Notes:
1. This requirement applies to execution governance in ChatMasala, not the FORGE canonical foundation docs.
2. If independent test-writer role is unavailable in v1, thread must surface `waiting_for_user` with explicit reason instead of silently downgrading the gate.

## 11) Reliability and Long-Running Tasks

1. No hard task timeout in v1.
2. `stuck_threshold_minutes` triggers warning/escalation if no output for too long.
3. Execution remains active for long-running coding/test tasks.
4. Crash/disconnect behavior:
   - keep thread state and last checkpoint
   - allow retry same endpoint
   - allow endpoint swap and continue

### 11.1 Liveness Detection (V1)
1. Agent process running + stdout/stderr stream open => live.
2. No output for `stuck_threshold_minutes` => warn/escalate, do not kill.
3. Process exit non-zero => failed turn (retry eligible).

### 11.2 Retry Policy (V1)
1. `turn_retry_limit` default 2 (separate from `max_cycles`).
2. Backoff: immediate, then 30s.
3. Retry does not increment cycle count until reviewer verdict is produced.
4. Idempotency warning shown before retry for side-effectful stages.

## 12) UI/UX (Lightweight)

1. Thread list with status badges.
2. Thread timeline (ledger view) with route reasons.
3. Setup panel:
   - workflow template
   - agent selection
   - role prompts
   - policy pack
   - max cycles
4. Run controls:
   - start
   - pause/resume
   - retry step
   - reroute
   - inject user note
5. Handoff preview toggle:
   - auto-send default
   - optional preview before dispatch
6. Save/load workflow profiles.
7. Basic metrics panel:
   - turn duration
   - parser success rate
   - gate pass/fail counts

Note: CLI windows remain external in v1; UI monitors and controls orchestration.

## 13) Plugin Strategy

Keep extension points from day one:
1. `AgentAdapter` interface (CLI now; others later).
2. `SummaryProvider` interface (enabled by default if configured; deterministic fallback if not).
3. `ContextProvider` interface (`basic` now, RepoPrompt later).

This enables user-selected providers (GLM/Gemini/Claude/etc.) without hard-coding one model.

## 13.1 Prompt Construction Pipeline (V1)
Prompt construction order is fixed and deterministic:
1. `[system_prompt]` (role layer)
2. `[global_policy]` (policy layer)
3. `[role_policy]` (policy layer)
4. `[thread_goal + acceptance_criteria]` (thread layer)
5. `[previous_outputs + structured_fields]` (turn layer)
6. `[user_note]` (session layer, highest runtime priority)

## 13.2 Prompt Engineering Scope in V1
V1 includes operational prompt engineering only:
1. fixed assembly order
2. strict structured output contract
3. deterministic parser compatibility

V1 does not include advanced prompt optimization research (few-shot tuning, automatic prompt rewriting, adaptive style transfer). Those are explicitly V2+ concerns.

## 14) Python Implementation Choice

Recommendation: use Python for v1.

Reasons:
1. Likely easiest integration with existing Python fleet from your brother.
2. Fast iteration for process orchestration, adapters, and parsing.
3. Strong ecosystem for simple API + web UI (FastAPI + lightweight frontend).
4. Easy plugin model via entry points/modules.

Suggested stack:
1. Backend: FastAPI + asyncio workers.
2. Storage: SQLite (threads/turns/ledger/profiles).
3. UI: small web app (React or minimal server-rendered pages).
4. Agent runtime: subprocess/pty adapter first.

## 15) One-Pass Delivery Plan (If Scope Is Frozen)

1. Build core backend:
   - models
   - state machine
   - rule engine
   - parser
   - ledger
2. Build CLI adapter and runner.
3. Build minimal UI screens (setup, run, timeline).
4. Add pause/resume/reroute/retry.
5. Add profile save/load.
6. Add policy pack + output contract validation.
7. Validate with 2 canonical flows:
   - builder<->reviewer
   - planner->builder->reviewer
8. Add spec tests:
   - parser conformance tests
   - routing rule tests
   - cycle counting tests
   - policy precedence tests
9. Add independent E2E validation path for coding/build threads:
   - require E2E behavior oracle in thread spec
   - ensure closure E2E is authored by non-builder role
   - block `done` on failed/missing independent E2E gate unless user override is logged

Acceptance for v1:
1. Deterministic replayable routes.
2. Policy-gated closure works.
3. Crash recovery works from checkpoint.
4. Minimal babysitting achieved in live trial.

## 16) Frozen Defaults for V1

1. Default confidence threshold: `0.95` (frozen).
2. Default stuck threshold minutes: `30` (frozen).
3. Reviewer required fields beyond minimum set:
   - `SCOPE_OK: YES|NO`
   - `POLICY_COMPLIANCE: PASS|FAIL`
4. Mandatory gate split:
   - Global defaults: parse + schema + parser-error-free
   - Per-thread custom: command/evidence/docs/domain gates
5. Summary sidecar behavior:
   - Default: enabled if provider configured
   - Fallback: deterministic non-LLM summarizer when provider is not configured.

## 17) Deferred (Deliberately Not in V1)
1. Multi-user auth/authorization model.
2. Embedded terminal UI.
3. External messaging channels.
4. Mid-thread prompt/policy version migration; v1 pins versions at thread start.
