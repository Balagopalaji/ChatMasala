# FORGE Spec: ChatMasala Core Data Model and Session State Machine

## 0. Pre-Flight Decisions

**Risk Tier:** [ ] Low  [x] Medium  [ ] High

**Primary Cognitive Mode for this project:**
[ ] Deterministic  [ ] Exploratory  [ ] Adversarial  [x] Synthesis  [ ] Audit
[ ] Multi-phase — using Divergence → Convergence Loop

**Resource Governance:**
- Model tier (Planner): `GPT-5 class reasoning model`
- Model tier (Workers): `GPT-5 class coding model`
- Max runtime per sub-task: `90 minutes`
- Total compute / cost budget: `<= 200k prompt+completion tokens`
- Retry limit before escalation: `2`
- Cost threshold that triggers stop-and-report: `>= 300k cumulative tokens`

## 1. Specification Layer — The Blueprint

### 1.1 Final Deliverable

Deliverable: Markdown architecture + implementation spec defining SQLAlchemy models, SQLite schema, and deterministic session state machine transitions for multi-agent handoff.

Format: One self-contained markdown file including entity definitions, enums, transition table, invariants, API contract sketch, and test acceptance criteria.

Length / Size: 1,200-2,200 words plus compact tables.

Measurable quality bar: All required entities/enums/transitions are explicitly defined with no ambiguous transition path; every transition has guard conditions and side effects; schema supports referential integrity and query performance for current-owner lookup and session timeline retrieval.

### 1.2 Scope Boundaries

**In scope:**
- Session, Message, AgentSlot relational data model for FastAPI + SQLite + SQLAlchemy.
- Enum definitions for `session.status` and `message.sender_type`.
- Session lifecycle transition model: `open -> agent_assigned -> pending_handoff -> handed_off | closed`.
- Constraints, indexes, and invariants needed for deterministic handoff tracking.
- Minimal API/state-operation contract needed to mutate lifecycle safely.

**Out of scope (Must-Not):**
- UI/UX flows, frontend rendering, or websocket protocol specifics.
- LLM prompt design, policy-pack design, or reviewer workflow contracts beyond state transitions.
- Multi-tenant authN/authZ implementation details.
- Distributed database concerns beyond SQLite local consistency model.

### 1.2.1 Lifecycle Mapping (Conceptual -> Persisted Semantics)

This table is authoritative for resolving conceptual step names against persisted storage semantics.

| Conceptual lifecycle step | Persisted `Session.status` | Required side effects | Representation source of truth |
|---|---|---|---|
| `open` | `active` | Create `Session` row; initialize with no current owner (`AgentSlot.is_current=false` for historical rows, or no slot row yet) | Derived event/operation (`open_session`) + status |
| `agent_assigned` | `active` | Upsert `AgentSlot` for assigned agent; mark exactly one slot as current owner for session | Derived event/operation (`assign_agent`) + current `AgentSlot` |
| `pending_handoff` | `pending_handoff` | Record handoff request metadata; keep existing owner current until handoff completion | Primarily status; enriched by handoff event fields |
| `handed_off` | `active` | End previous current slot; create/mark new current `AgentSlot` for target agent; append handoff completion event | Derived event/operation (`complete_handoff`) + current `AgentSlot` + status reset to `active` |
| `closed` | `closed` | Mark session terminal; no further owner-changing transitions allowed | Status (terminal) |

Deterministic rule: `Session.status` captures coarse lifecycle (`active|pending_handoff|closed`), while `open`, `agent_assigned`, and `handed_off` are operational milestones derived from auditable transition events plus `AgentSlot` ownership state.

### 1.3 Task Decomposition

| # | Sub-task | Cognitive Mode | Risk Tier | Acceptance Criteria | Eval Method |
|---|---|---|---|---|---|
| 1 | Define canonical entities and enums | Deterministic | Medium | Session, Message, AgentSlot fields/types/nullability/FKs are fully specified; enum values exactly match request | Schema checklist review |
| 2 | Define lifecycle state machine and transition guards | Deterministic | Medium | Transition graph includes only allowed edges; invalid edges explicitly rejected with reason | Transition table review + invalid-edge matrix |
| 3 | Map model to SQLAlchemy + SQLite constraints/indexes | Synthesis | Medium | SQLAlchemy class design aligns with constraints; required unique/index/FK rules documented | ORM-to-DDL traceability check |
| 4 | Define mutation operations and transactional invariants | Deterministic | Medium | `open`, `assign_agent`, `request_handoff`, `complete_handoff`, `close_session` have pre/postconditions | Operation contract audit |
| 5 | Define validation and test acceptance criteria | Audit | Medium | Deterministic tests cover legal/illegal transitions and ownership consistency | Test matrix completeness review |

### 1.4 Acceptance Criteria — Master Definition of Done

The project is complete when ALL of the following are true:
- [ ] Session, Message, and AgentSlot are fully specified with field-level constraints and enum values required by the request.
- [ ] Session state machine and transition rules are deterministic and include both success and rejection paths.
- [ ] SQLAlchemy + SQLite mapping and indexing strategy are documented and implementable without unresolved decisions.

## 2. Intent Layer — The Compass

### 2.1 Agent Deployment Purpose

You are: a specification engineer defining a deterministic persistence and lifecycle model for a multi-agent handoff backend.

You are NOT responsible for: building production code, frontend UX, auth policies, or non-requested orchestration features.

Your output is consumed by: engineering implementers and reviewers.

Your output feeds into: FastAPI service implementation and migration/test work.

### 2.2 Trade-off Hierarchy

| Priority | Value |
|---|---|
| `1` | Accuracy / Correctness |
| `2` | Deterministic operability (domain-specific value) |
| `3` | Safety / Risk avoidance |
| `4` | Simplicity / Readability |
| `5` | Completeness |
| `6` | Speed / Efficiency |
| `7` | Cost / Token economy |
| `8` | Novelty / Creativity |

### 2.3 Constraint Architecture

**Must (non-negotiable requirements):**
- Use FastAPI + SQLite + SQLAlchemy assumptions and produce model definitions compatible with that stack.
- Include exactly requested enums: `Session.status = active|pending_handoff|closed`, `Message.sender_type = user|agent|system`.
- Include lifecycle transitions conceptually as `open -> agent_assigned -> pending_handoff -> handed_off/closed`, mapped to persistent state semantics.
- `AgentSlot` must represent current session owner and maintain handoff history capability.

**Must-Not (hard prohibitions):**
- Must not introduce autonomous routing logic beyond deterministic transition guards.
- Must not require non-SQLite-only capabilities for core correctness.
- Must not leave transition behavior implicit.

**Prefer (soft preferences when trade-offs arise):**
- Prefer append-only event/timeline compatibility for auditability.
- Prefer explicit operation-level idempotency guidance.
- Prefer naming aligned with existing repository language (`handoff`, `session`, `agent slot`).

**Escalate (stop and surface to human when):**
- Requested transition semantics conflict with mandatory enum values.
- Ownership requirements imply multi-owner concurrency not representable by single current owner without redesign.

### 2.4 Forbidden Approaches

- Ambiguous "magic" status derivation from message content without persisted state.
- Soft-delete-only closure semantics that keep sessions effectively active.
- Hidden state transitions without auditable side effects.

## 3. Context Layer — The Environment

### 3.1 Provided Context

| Source | Type | Authority Level | Notes |
|---|---|---|---|
| `docs/multi-agent-intent-and-spec-v1.md` | Product/runtime spec | AUTHORITATIVE | Defines deterministic routing and audit-first runtime intent |
| `docs/examples/thread-examples.yaml` | Workflow examples | REFERENCE | Confirms linear/ping-pong orchestration patterns |
| `docs/examples/policy-pack-baseline.yaml` | Policy baseline | REFERENCE | Establishes parseable and deterministic closure patterns |

### 3.2 Known State

Prior attempts: No prior data-model artifact specified for this exact request.

Known failures / dead ends: None provided.

Known constraints: SQLite storage, SQLAlchemy ORM, FastAPI service context, deterministic handoff state transitions.

Current blockers: None.

### 3.3 Context Freshness

[x] All provided context is current — use as ground truth
[ ] The following sources may be stale and should be verified: `none`
[ ] The agent must re-fetch live data for: `none`
[x] MCP connections available: `nimai-mcp and local repo context`

### 3.4 Domain Conventions

Terminology to use: session, handoff, current owner, transition guard, immutable message timeline.

Terminology to avoid: autonomous router brain, opaque state, implicit owner.

Style / format standards: explicit enum tables, FK/index detail, transition and invariant tables.

Domain-specific conventions: deterministic transitions, auditable state changes, conservative schema evolution.

### 3.5 Module Boundary Definition

- API layer (`app/api/*`): FastAPI route handlers validate request shape and call service-layer operations only.
- Domain/service layer (`app/services/session_lifecycle.py`): Owns transition guards, transaction boundaries, and invariant enforcement.
- Persistence layer (`app/models/*`, `app/db/*`): SQLAlchemy models (`Session`, `Message`, `AgentSlot`) and session factory/migrations.
- Boundary rule: API layer must not perform direct model mutation bypassing service-layer transition methods.

## 4. Prompt Layer — The Trigger

### 4.1 Opening System Instruction

You are a specification engineer for the ChatMasala multi-agent handoff backend.

Your task is to produce a complete technical spec for the core data model and session state machine, including SQLAlchemy entity definitions, SQLite constraints/indexes, transition guards, and validation criteria.

You are operating within constraints requiring FastAPI + SQLite + SQLAlchemy compatibility, explicit enums (`active/pending_handoff/closed` and `user/agent/system`), and deterministic lifecycle transitions from open through assignment, pending handoff, handoff completion, or closure.

Your trade-off priority order is accuracy first, then safety, then clarity, then completeness.

Use the repository context as authoritative for deterministic and auditable multi-agent orchestration principles.

Execute sub-tasks in order: entity+enum definition, lifecycle modeling, ORM/DDL mapping, mutation contracts, and validation matrix.

Completion criterion is strict: no unresolved schema or transition ambiguity.

### 4.2 Per-Sub-Task Prompt Template

Sub-task [1]: Define entities and enums
Cognitive mode: Deterministic
Your input: Request requirements + v1 runtime intent
Your output: Field-level entity and enum specification
Acceptance criteria: All required entities/enums present with clear constraints
Evaluation: Schema checklist
Resource cap: 45 minutes

Sub-task [2]: Define transition model
Cognitive mode: Deterministic
Your input: Lifecycle states and ownership requirements
Your output: Allowed/rejected transitions with guard + side effects
Acceptance criteria: No undefined edge cases
Evaluation: Transition matrix validation
Resource cap: 45 minutes

Sub-task [3]: SQLAlchemy/SQLite mapping
Cognitive mode: Synthesis
Your input: Entity and transition spec
Your output: ORM model mapping and index/constraint plan
Acceptance criteria: Implementable without hidden assumptions
Evaluation: ORM-to-schema traceability
Resource cap: 45 minutes

Sub-task [4]: Operation contracts
Cognitive mode: Deterministic
Your input: Transition matrix + ownership invariants
Your output: Operation preconditions, transaction steps, postconditions
Acceptance criteria: Every state mutation is deterministic and auditable
Evaluation: Contract walkthrough
Resource cap: 30 minutes

Sub-task [5]: Validation criteria
Cognitive mode: Audit
Your input: Full draft spec
Your output: Test matrix and pass/fail acceptance rules
Acceptance criteria: Covers legal/illegal transitions and ownership integrity
Evaluation: Coverage matrix check
Resource cap: 30 minutes

## 5. Governance & Validation

### 5.1 Escalation Contract

**Escalation triggers:**
- Transition or ownership requirements conflict with fixed enum design.
- Need for concurrent multi-owner semantics beyond `AgentSlot` current-owner model.

**Who reviews escalations:**
Name / Role: Product owner + backend lead
Contact: Repository issue tracker and engineering channel
Response SLA: 1 business day

**If no response arrives within SLA, the agent should:**
[x] Hold and wait
[ ] Attempt alternative path: `none`
[ ] Abort and report

### 5.2 Adversarial Reflection Trigger

[ ] Not required (Low risk)
[x] Required after sub-task(s): `2 and 4`
[x] Required before final delivery

The agent should critique: invalid transition leakage, ownership race windows, and mismatch between conceptual and persisted state.
The revision threshold is: any discovered ambiguity that permits two interpretations of next valid state.

### 5.3 Uncertainty Reporting

[ ] Not required
[x] Required — agent must report:
- Confidence estimate (0–100%) with justification
- Primary uncertainty drivers
- What data would most reduce uncertainty
- Alternative plausible interpretations

## 6. Brainstorming Mode (Divergence → Convergence)

Not applicable for this run; primary mode is single-pass synthesis with deterministic validation.

## 7. Domain-Specific Additions

### If Coding:
- Language / framework / version: `Python 3.11+, FastAPI, SQLAlchemy 2.x, SQLite 3`
- Performance targets: `p95 session timeline fetch under 100ms at 10k messages/session on local SQLite benchmarks`
- API / interface contracts: `Create/open session, append message, assign owner, request/complete handoff, close session`
- Security requirements: `No plaintext secret storage in entities; enforce server-side transition validation`
- Test coverage expectation: `Unit tests for all state transitions and ownership invariants; integration tests for transaction behavior; independent E2E validation gate for closure-critical flows`
- Independent E2E behavior oracle: `Verify open -> assign -> pending_handoff -> handed_off and open -> assign -> pending_handoff -> closed flows via API-visible outcomes; verify illegal transitions are rejected with deterministic errors; verify AgentSlot ownership changes are auditable in message/session timeline views`
- Independent validation ownership: `Builder must not author the final closure E2E tests used for sign-off; closure E2E is authored/run by a separate test-writer role (agent or human), or explicit override is recorded`

### If Science / Research:
- Null hypothesis: Not applicable.
- Falsification criteria: Not applicable.
- Authorized data sources: Not applicable.
- Forbidden data sources: Not applicable.
- Statistical significance threshold: Not applicable.
- Correction method: Not applicable.
- Reproducibility requirements: Not applicable.

### If Writing / Content:
- Audience: Backend engineers and technical reviewers.
- Purpose: Provide implementable model and lifecycle specification.
- Structure: Entity model -> state machine -> operation contracts -> tests.
- Word count / length: 1,200-2,200 words plus tables.
- Style reference: Clear technical RFC-like markdown.
- Mandatory inclusions: Exact enums and requested transition lifecycle.
- Mandatory exclusions: UI or product marketing content.

### If Business / Strategy:
- Decision-maker: Backend lead and product owner.
- Decision to be made: Approve model as implementation baseline.
- Options to evaluate: Single-owner slot model now vs future multi-owner extension.
- Recommendation format: GO/NO-GO with risks.
- Regulatory Must-Nots: No unsupported compliance claims.
- Stakeholder sensitivities: Deterministic auditability and low operational overhead.

## 8. Spec Validation (Red-Team Checklist)

**5 Primitives — does every sub-task have:**
- [x] A self-contained problem statement (zero questions needed to start)
- [x] A Constraint Architecture (Must / Must-Not / Prefer / Escalate)
- [x] A runtime under 2 hours
- [x] Binary acceptance criteria
- [x] A built-in evaluation method

**Failure Mode Taxonomy — does this spec prevent:**
- [x] Scope Creep — explicit Must-Not list and scope boundaries
- [x] Hallucinated Completion — binary acceptance criteria defined
- [x] Intent Drift — ranked trade-offs and deployment purpose explicit
- [x] Context Collapse — context curated; noise removed
- [x] Runaway Cost — resource caps set before decomposition
- [x] Overconfident Output — uncertainty reporting required

**Final gate:**
- [x] Risk tier and resource governance set before decomposition
- [x] Every agent has a deployment purpose statement
- [x] Escalation contract complete (who, when, SLA, no-response behavior)
- [x] Planner execution plan will be saved as artifact
