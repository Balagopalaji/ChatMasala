# OnTime Build Plan

> Note: Ignore all deprecated documentation under `docs/archive`. This plan uses only current source and active docs in `docs/`.

## Goal
Build the project in a low-risk sequence that establishes source-of-truth requirements first, then delivers core timer/session logic, real-time sync, frontend flows, recovery behavior, and final verification.

---

## Phase 1 — Source-of-Truth Alignment
**Goal:** Define what is current before implementation starts.

### Tasks
- Ignore all deprecated archive docs.
- Use current docs in `docs/` as the product and architecture contract.
- Identify:
  - product requirements
  - architecture references
  - frontend / backend / companion boundaries
  - test and smoke-check expectations
- Produce a short implementation checklist covering:
  - in-scope features
  - out-of-scope features
  - critical user flows
  - technical constraints

### Output
A clear build contract for implementation.

---

## Phase 2 — Repo and Environment Setup
**Goal:** Make the project runnable and verifiable locally.

### Tasks
- Standardize setup instructions.
- Confirm install and startup flows.
- Verify:
  - app boots locally
  - lint works
  - tests work
  - frontend and backend can run together
- Add or fix:
  - `.env.example`
  - root dev/build/test scripts
  - minimal CI validation if missing

### Output
A reliable local development baseline.

---

## Phase 3 — Core Domain Model
**Goal:** Lock core timer/session behavior before UI polish.

### Tasks
- Define canonical models for:
  - session
  - participant/device
  - timer state
  - control ownership/arbitration
  - reconnect state
- Implement explicit state transitions for:
  - idle
  - running
  - paused
  - completed/reset
  - reconnect/recovery
- Add unit tests for invariants and transition rules.

### Output
Stable, tested core logic.

---

## Phase 4 — Backend and Real-Time Sync Layer
**Goal:** Support authoritative multi-client behavior.

### Tasks
- Build or verify APIs for:
  - session create/join
  - state fetch
  - control actions
- Build or verify realtime behavior for:
  - handshake
  - join queue
  - state broadcast
  - ack/retry flows
- Handle failure modes:
  - disconnect/reconnect
  - stale controller state
  - duplicate events
  - race conditions

### Output
A resilient backend and sync layer.

---

## Phase 5 — Frontend Application
**Goal:** Deliver the main user experience.

### Tasks
- Build screens/components for:
  - session start/join
  - timer display
  - controls
  - participant/status indicators
  - reconnect/error banners
- Connect UI to backend state.
- Use optimistic UI only where safe.
- Surface sync and conflict states clearly.

### Output
A complete primary app flow.

---

## Phase 6 — Companion or Secondary Client Integration
**Goal:** Support additional control/display surfaces if required.

### Tasks
- Define companion responsibilities.
- Reuse backend contracts from the main app.
- Validate:
  - join flow
  - sync correctness
  - control ownership rules
  - degraded network handling

### Output
Consistent multi-surface behavior.

---

## Phase 7 — Persistence and Recovery
**Goal:** Make sessions survive interruptions safely.

### Tasks
- Persist essential timer/session state.
- Rehydrate state on restart or reconnect.
- Protect against:
  - clock drift
  - double-applied actions
  - orphaned control locks
  - invalid resume state

### Output
Robust recovery behavior.

---

## Phase 8 — QA and Verification
**Goal:** Prove correctness before release.

### Tasks
- Add or finish:
  - unit tests
  - integration tests
  - targeted smoke tests
- Verify:
  - timer correctness
  - arbitration correctness
  - reconnect behavior
  - frontend/backend contract alignment
- Run a bug/regression sweep before sign-off.

### Output
Release confidence.

---

## Phase 9 — Documentation Sync
**Goal:** Keep active documentation accurate.

### Tasks
- Update only active docs in `docs/`.
- Refresh:
  - setup instructions
  - architecture diagrams if needed
  - QA/smoke reports
  - changelog

### Output
Docs aligned with implementation.

---

## Recommended Build Order
1. Repo setup
2. Core timer/state model
3. Backend sync/realtime
4. Frontend happy path
5. Reconnect/conflict handling
6. Companion/client support
7. Persistence/recovery
8. Smoke tests and regression sweep
9. Docs and changelog

---

## Milestones

### Milestone 1
Local app runs, tests run, architecture is clear.

### Milestone 2
Single-user timer flow works end-to-end.

### Milestone 3
Multi-client real-time sync works.

### Milestone 4
Reconnect and arbitration edge cases are stable.

### Milestone 5
Docs, smoke checks, and release notes are complete.

---

## Key Risks to Address Early
- ambiguous source-of-truth docs
- timer state bugs
- reconnect race conditions
- control arbitration conflicts
- frontend/backend contract drift

---

## Immediate Next Step
Start with a repo audit and implementation checklist using only active docs outside `docs/archive`, then build in vertical slices:
- create/join session
- start/pause/reset timer
- live sync across clients
- reconnect recovery