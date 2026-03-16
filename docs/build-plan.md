# ChatMasala Builder Pass Checklist

> Decision: keep this plan in `docs/build-plan.md` so there is one active execution checklist for builder agents.
>
> Source of truth: `README.md` and `docs/mvp-build-spec.md`
>
> Ignore for implementation decisions: `docs/archive/**` and `tmp/**`

## How to use this file
- Complete passes in order.
- Do not start the next pass until the current pass exit checklist is fully checked off.
- Check a box only when the work is implemented and verified.
- If `README.md` and `docs/mvp-build-spec.md` conflict, stop and resolve the conflict before building further.
- Keep scope to the MVP only.

## Pass Status Overview
- [ ] Pass 0 — Scope Lock and Build Contract
- [ ] Pass 1 — Repo Foundation and Local Setup
- [ ] Pass 2 — Data Model, Contracts, and Persistence
- [ ] Pass 3 — Core Backend and Service Flows
- [ ] Pass 4 — Frontend and End-to-End MVP Flows
- [ ] Pass 5 — Hardening, QA, and Documentation Sync

---

## Pass 0 — Scope Lock and Build Contract

**Goal:** turn the active docs into an unambiguous build contract before implementation starts.

### Builder checklist
- [ ] Read `README.md` fully.
- [ ] Read `docs/mvp-build-spec.md` fully.
- [ ] Confirm the product goal in one clear sentence.
- [ ] List the MVP user types or actors described in the active docs.
- [ ] List the required MVP flows described in the active docs.
- [ ] List explicit non-goals and out-of-scope items.
- [ ] Identify the required system parts from the active docs: frontend, backend, storage, integrations, worker jobs, or other runtime components.
- [ ] Identify any missing decisions that would block implementation.
- [ ] Resolve ambiguous requirements before code work begins.
- [ ] Convert the MVP into a concrete implementation checklist that builders can execute without referring to deprecated docs.

### Verification checklist
- [ ] Every MVP feature in `docs/mvp-build-spec.md` maps to at least one planned implementation task.
- [ ] Every out-of-scope item is clearly excluded from builder work.
- [ ] No implementation requirement is taken from `docs/archive/**`.
- [ ] The team has a shared definition of MVP done.

### Exit checklist
- [ ] Scope is locked.
- [ ] Open questions are resolved or explicitly deferred.
- [ ] Builders can proceed without using deprecated docs.

---

## Pass 1 — Repo Foundation and Local Setup

**Goal:** make the project runnable, buildable, and testable in a clean local environment.

### Builder checklist
- [ ] Confirm the intended project structure from the current repo and active docs.
- [ ] Set up or clean up the local development workflow.
- [ ] Ensure environment configuration is documented and reproducible.
- [ ] Add or fix example environment configuration if the app requires runtime variables.
- [ ] Add or fix root-level developer scripts for install, run, build, lint, and test if the stack supports them.
- [ ] Ensure the main app starts locally.
- [ ] Ensure any required backend or supporting service starts locally.
- [ ] Ensure frontend and backend can run together if both are part of the MVP.
- [ ] Document the exact local startup flow in `README.md` if it is missing or incorrect.
- [ ] Add minimal CI-friendly validation steps if the repo currently lacks them.

### Verification checklist
- [ ] A fresh developer can install dependencies using documented steps.
- [ ] A fresh developer can start the app using documented steps.
- [ ] The build completes successfully.
- [ ] Lint passes or known failures are explicitly documented and reduced to MVP-safe exceptions.
- [ ] Tests run successfully or the missing test areas are explicitly identified for later passes.

### Exit checklist
- [ ] Local setup is reliable.
- [ ] Build and test entry points are clear.
- [ ] The repo is ready for feature implementation.

---

## Pass 2 — Data Model, Contracts, and Persistence

**Goal:** define the canonical data model and interfaces before building feature logic.

### Builder checklist
- [ ] Identify the core domain entities required by the MVP.
- [ ] Define the canonical fields and validation rules for each entity.
- [ ] Define request and response contracts between client and server if the MVP is multi-tier.
- [ ] Define internal service contracts where one backend module depends on another.
- [ ] Decide which data must persist and which can remain transient.
- [ ] Define storage structure or schema for persisted data if persistence is required.
- [ ] Define identifiers, statuses, and lifecycle transitions for core entities.
- [ ] Handle invalid input, missing state, and duplicate operations in the contracts.
- [ ] Add model-level tests for validation, serialization, and invariants.
- [ ] Document any contract decisions that are required for frontend and backend parallel work.

### Verification checklist
- [ ] Core entities from the MVP spec are represented in code.
- [ ] Invalid payloads are rejected cleanly.
- [ ] Persisted data shape matches the needs of the MVP flows.
- [ ] Model tests cover expected and invalid cases.
- [ ] Frontend and backend can rely on the same contract definitions or equivalent documented schema.

### Exit checklist
- [ ] Canonical model and contract layer is stable.
- [ ] Persistence decisions are made.
- [ ] Builders can implement service and UI layers without guessing data shape.

---

## Pass 3 — Core Backend and Service Flows

**Goal:** implement the server-side or core application logic that powers the MVP.

### Builder checklist
- [ ] Implement the core service layer for the MVP workflows.
- [ ] Implement the required API routes, handlers, actions, or commands described by the active spec.
- [ ] Add validation and error handling at every boundary.
- [ ] Add authorization, access rules, or policy checks if the MVP requires them.
- [ ] Implement persistence reads and writes where needed.
- [ ] Implement background processing, async jobs, or event flows only if the MVP requires them.
- [ ] Add structured logging for important success and failure paths.
- [ ] Add integration tests for the main service flows.
- [ ] Add regression coverage for known edge cases discovered during implementation.
- [ ] Ensure backend behavior matches the active MVP spec and not archived concepts.

### Verification checklist
- [ ] Every required backend flow from the MVP spec works in isolation.
- [ ] Invalid requests fail predictably.
- [ ] Data writes and reads are correct.
- [ ] Integration tests cover the primary happy paths and major failure paths.
- [ ] No backend feature depends on deprecated archived behavior.

### Exit checklist
- [ ] Core services are functional.
- [ ] Contracts are enforced at runtime.
- [ ] Backend is ready for frontend integration.

---

## Pass 4 — Frontend and End-to-End MVP Flows

**Goal:** deliver the actual user-facing MVP experience and wire it to real data/services.

### Builder checklist
- [ ] Implement the required routes, screens, views, or components for the MVP.
- [ ] Implement all primary user interactions described in the active spec.
- [ ] Connect the UI to the real data contracts and backend flows.
- [ ] Handle loading, empty, success, and error states for every primary flow.
- [ ] Handle validation feedback in the UI.
- [ ] Ensure the app works for first-time use and repeat use where the MVP requires it.
- [ ] Ensure state updates are reflected correctly in the UI.
- [ ] Add component, integration, or end-to-end tests for the main user flows where the stack supports them.
- [ ] Verify responsive behavior if the MVP expects multiple screen sizes.
- [ ] Verify basic accessibility expectations for labels, focus, and keyboard use where applicable.

### Verification checklist
- [ ] Each MVP user flow can be completed manually from start to finish.
- [ ] UI behavior matches the active spec.
- [ ] Error states are visible and understandable.
- [ ] Frontend uses current contracts and does not depend on guessed payload shapes.
- [ ] Automated coverage exists for the most important user journeys supported by the stack.

### Exit checklist
- [ ] The MVP happy path works end to end.
- [ ] The UI is integrated with real services.
- [ ] Primary user journeys are testable and demonstrable.

---

## Pass 5 — Hardening, QA, and Documentation Sync

**Goal:** stabilize the MVP, close obvious gaps, and leave the active docs accurate.

### Builder checklist
- [ ] Run the full project build.
- [ ] Run lint across the changed code.
- [ ] Run automated tests across the changed code.
- [ ] Fix critical defects and regressions found during testing.
- [ ] Add regression tests for any bugs fixed in this pass.
- [ ] Review edge cases in the highest-risk flows from the MVP spec.
- [ ] Remove dead code, stale comments, and abandoned experiments from the implementation path.
- [ ] Update `README.md` if setup, usage, or architecture guidance changed.
- [ ] Update active docs in `docs/` if implementation details changed from the prior plan.
- [ ] Confirm that deprecated docs in `docs/archive/**` remain unused and untouched as source-of-truth inputs.

### Verification checklist
- [ ] Build passes.
- [ ] Lint passes.
- [ ] Tests pass.
- [ ] Main manual smoke flows succeed.
- [ ] Active docs match shipped behavior.
- [ ] No known critical blocker remains for MVP release.

### Exit checklist
- [ ] The MVP is stable enough to hand off, demo, or release.
- [ ] Documentation reflects reality.
- [ ] Builder work is complete for the current MVP scope.

---

## Recommended Builder-Agent Sequencing
- Builder Agent 1: Pass 0 and Pass 1
- Builder Agent 2: Pass 2
- Builder Agent 3: Pass 3
- Builder Agent 4: Pass 4
- Builder Agent 5: Pass 5

If fewer agents are available, keep the pass order the same and combine adjacent passes.

---

## Whole-Project Done Checklist
- [ ] The implementation follows `docs/mvp-build-spec.md`.
- [ ] The implementation does not rely on `docs/archive/**`.
- [ ] A clean local setup works from `README.md`.
- [ ] The MVP happy paths work end to end.
- [ ] Core failure states are handled safely.
- [ ] Automated validation passes.
- [ ] Active docs match the shipped MVP.