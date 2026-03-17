# ChatMasala Redesign Pass Checklist

> Decision: use this file as the execution checklist for the next redesign pass.
>
> Source of truth for this pass: the current non-archive repository implementation plus the redesign requirements in the active task.
>
> Ignore for implementation decisions: `docs/archive/**` and `tmp/**`

## 1. Redesign Summary

Redesign the current MVP from a thread/raw-command CRUD prototype into a simpler run-first product where the user:

- creates a `Run`, not a `Thread`
- enters a `goal`, not `task_text`
- selects a `workspace`, not `working_directory`
- chooses one of exactly two workflow presets:
  - `Single Agent`
  - `Builder -> Reviewer`
- selects saved `AgentProfile` records instead of entering raw commands per run
- views progress in a chat-style relay page with one or two lanes depending on workflow
- keeps the existing CLI-first, polling-based backend under the hood

This is a **clean-break dev-pass redesign**, not a migration-heavy compatibility exercise.

## 2. Simplifying Rules For This Pass

Keep the implementation intentionally narrow.

### Required simplifications
- Treat the local DB as disposable.
- Prefer a clean schema reset over migration code.
- Do **not** build a SQLite migration framework.
- Do **not** add DB backup logic.
- Do **not** add `agent_config_json` snapshots yet.
- Do **not** add a persisted event/system-turn model unless it becomes truly necessary.
- Keep workflow definitions hard-coded in a tiny constant list.
- Keep polling via the current HTML refresh approach; no streaming transport work.
- Keep the CLI seam under `app/agents/cli_runner.py`; users choose profiles, not raw commands per run.

### Safe rule of thumb
If a part of the plan exists mainly for future-proofing rather than the next visible UX, cut it.

## 3. Recommended Execution Order

1. Add `AgentProfile` support, shipped instruction files, and a profile-management settings page.
2. Rename the product and schema from `Thread` to `Run` with a clean DB break.
3. Redesign the new run form around workflow preset selection, profile dropdowns, workspace picking, and loop controls.
4. Update the orchestrator to use selected profiles and the two hard-coded workflows.
5. Redesign the run detail page into a workflow-aware chat relay view.
6. Update tests and active docs to match the redesign.

## 4. How To Use This File

- Complete phases in order.
- Do not widen scope beyond the checklist below.
- Check a box only when the work is implemented and verified.
- If the codebase and this plan diverge, update the plan before continuing.
- Prefer deleting old prototype assumptions over layering aliases everywhere.
- If a task is only for old thread/raw-command behavior, remove or replace it instead of preserving it for compatibility.

## 5. Pass Status Overview

- [x] Phase 0 — Scope Lock For The Redesign Pass
- [x] Phase 1 — Agent Profiles Foundation
- [x] Phase 2 — Clean-Break Run Schema And Naming
- [x] Phase 3 — Run Creation UX Redesign
- [x] Phase 4 — Orchestrator Update For Two Presets
- [x] Phase 5 — Run Detail Relay View Redesign
- [x] Phase 6 — Docs And Regression Hardening

---

## Phase 0 — Scope Lock For The Redesign Pass

**Purpose:** confirm the redesign target and explicitly cut future-facing persistence and workflow work before builders start changing code.

### Likely files/modules
- `README.md`
- `AGENTS.md`
- `docs/mvp-build-spec.md`
- `docs/build-plan.md`

### Data model decisions to lock
- `Thread` becomes `Run`
- `task_text` becomes `goal`
- `working_directory` becomes `workspace`
- Add `AgentProfile`
- `Run` stores direct profile IDs, not profile snapshots
- No migration framework; clean DB reset is acceptable

### Route/UI decisions to lock
- `/threads/*` becomes `/runs/*`
- New run form is goal-first
- Settings page becomes agent profile management
- Workflow preset list is exactly:
  - `single_agent`
  - `builder_reviewer`

### Test changes to plan for
- broad route test rewrite
- model test rewrite
- orchestrator behavior updates for single-agent and loop toggle
- docs sync checks at the end of the pass

### Risks/gotchas
- The repo currently mixes `Run` copy with `Thread` internals; builders must not mistake that for a completed rename.
- Current docs still describe the old MVP and must be treated as needing redesign updates, not as blockers against the requested clean break.
- Avoid inventing a generalized workflow engine while trying to support two presets.

### Builder checklist
- [x] Confirm the redesign goal in one sentence.
- [x] Confirm the pass is a clean-break dev prototype change, not a backward-compatible migration effort.
- [x] Confirm the only workflow presets in scope are `Single Agent` and `Builder -> Reviewer`.
- [x] Confirm polling remains sufficient.
- [x] Confirm raw per-run command entry is removed from the run creation UX.
- [x] Confirm no YAML engines, planner workflows, JSON APIs, MCP, browser extensions, inbox models, route-to actions, hosted routing, PTY embedding, or streaming transports will be added.
- [x] Add a minimal active-doc alignment update so `README.md`, `AGENTS.md`, and `docs/mvp-build-spec.md` no longer contradict this redesign pass.

### Verification checklist
- [x] All builders are working from the same narrow scope.
- [x] No persistence future-proofing work is planned beyond the next visible UX.
- [x] The redesign remains CLI-first under the hood.
- [x] Active docs point builders to this redesign checklist while the broader rewrite is still in progress.

### Exit checklist
- [x] Scope is locked.
- [x] Simplifying rules are accepted.
- [x] Builders can begin implementation without adding migration/framework work.

---

## Phase 1 — Agent Profiles Foundation

**Purpose:** introduce first-class agent profiles and shipped instruction files before changing run creation.

### Likely files/modules
- `app/models.py`
- `app/db.py`
- `app/schemas.py`
- `app/routes/settings.py`
- `app/templates/settings.html`
- `app/templates/base.html`
- `tests/test_models.py`
- `tests/test_routes.py`
- `README.md`
- `AGENTS.md`
- `docs/mvp-build-spec.md`

### Data model changes
Add `AgentProfile` with:
- `name`
- `provider`
- `command_template`
- `instruction_file`

Add only the minimal fields needed for profile selection and command resolution.

Do **not** add:
- profile snapshots
- profile versioning
- delete/archive history models
- provider-specific config tables

### File/assets changes
Ship default instruction markdown files under:
- `profiles/agents/single-agent.md`
- `profiles/agents/builder.md`
- `profiles/agents/reviewer.md`

Seed a minimal default set of `AgentProfile` rows that reference those files.

### Route/UI changes
Repurpose `/settings` into an agent profiles page.

Required UI outcomes:
- list existing profiles
- create a profile
- edit a profile
- validate that `instruction_file` exists and is readable

Keep scope narrow:
- create and edit only
- defer delete/archive actions

### Test changes
- add model coverage for `AgentProfile`
- add route coverage for listing, creating, and editing profiles
- add validation coverage for missing or unreadable `instruction_file`
- add seed behavior coverage if seeding is implemented

### Risks/gotchas
- Profile records should stay simple display/config records; do not turn them into a provider abstraction layer.
- If seed data is added, make it idempotent.
- Settings page should stop teaching users to think in raw commands per run.

### Builder checklist
- [x] Add `AgentProfile` to `app/models.py`.
- [x] Add any minimal schema/form helpers needed for profile create/edit validation.
- [x] Add shipped instruction markdown files under `profiles/agents/`.
- [x] Seed default profiles for single-agent, builder, and reviewer usage.
- [x] Replace the old global command settings UX with profile management UX.
- [x] Keep profile management limited to create/edit/list.

### Verification checklist
- [x] A fresh local DB includes default agent profiles.
- [x] `/settings` shows profiles instead of global builder/reviewer command strings.
- [x] A profile cannot be saved with a missing instruction file.
- [x] No per-run raw command UX remains on the settings page.

### Exit checklist
- [x] Agent profiles exist as first-class records.
- [x] Default instruction files are shipped.
- [x] Settings page now manages profiles.

---

## Phase 2 — Clean-Break Run Schema And Naming

**Purpose:** rename the core product model and strip out thread/raw-command terminology across implementation surfaces.

### Likely files/modules
- `app/models.py`
- `app/db.py`
- `app/schemas.py`
- `app/main.py`
- `app/routes/threads.py`
- `app/templates/thread_list.html`
- `app/templates/thread_new.html`
- `app/templates/thread_detail.html`
- `tests/test_models.py`
- `tests/test_routes.py`
- `tests/test_orchestrator.py`

### Data model changes
Replace `Thread` with `Run`.

Recommended `Run` fields for this pass:
- `id`
- `title`
- `goal`
- `plan_text`
- `workflow_type`
- `primary_agent_profile_id` nullable
- `builder_agent_profile_id` nullable
- `reviewer_agent_profile_id` nullable
- `workspace` nullable
- `loop_enabled`
- `status`
- `current_role` nullable
- `round_count`
- `max_rounds`
- `last_error`
- `created_at`
- `updated_at`

Update related models:
- `Turn.thread_id` -> `Turn.run_id`
- `UserNote.thread_id` -> `UserNote.run_id`

Remove old per-run raw command fields from the top-level model.

### DB strategy
Use a clean-break schema update appropriate for a disposable local prototype.

Implementation expectation:
- builders may delete the local DB and recreate it
- no migration framework
- no backup logic
- no legacy compatibility layer beyond what is truly needed during the code change

### Route/UI changes
- rename primary route surfaces from `/threads/*` to `/runs/*`
- rename route/module/template references from thread to run terminology
- keep the existing app structure simple; a renamed route module is fine
- remove stale thread labels and comments from templates

### Test changes
- rewrite model tests to use `Run`
- rewrite route tests to target `/runs/*`
- update any FK assertions to `run_id`
- update helper fixtures and factory names to run terminology

### Risks/gotchas
- Partial renames will create confusing mixed terminology across routes, models, and templates.
- This pass touches nearly every selected test file; do not attempt tiny patch edits while keeping old semantics.
- Avoid adding long-lived `/threads/*` aliases unless absolutely necessary for bootstrapping the branch.

### Builder checklist
- [x] Rename the top-level ORM model from `Thread` to `Run`.
- [x] Rename `task_text` to `goal`.
- [x] Rename `working_directory` to `workspace`.
- [x] Replace direct command fields on the top-level model with profile ID fields.
- [x] Rename `thread_id` FKs to `run_id` in related models.
- [x] Update route/module/template naming to run terminology.
- [x] Remove active code paths that still depend on old global command settings.

### Verification checklist
- [x] The app boots against a fresh clean DB.
- [x] No selected implementation file still uses `Thread` as the active product concept.
- [x] No selected implementation file still uses `task_text` or `working_directory` as the active user-facing field names.
- [x] Route tests can be updated against `/runs/*` without compatibility hacks.

### Exit checklist
- [x] `Run` is the canonical domain model.
- [x] Clean DB recreation works.
- [x] Old thread/raw-command persistence assumptions are removed.

---

## Phase 3 — Run Creation UX Redesign

**Purpose:** make run creation workflow-first, profile-based, and workspace-aware.

### Likely files/modules
- `app/routes/threads.py` or renamed run route module
- `app/templates/thread_new.html` or renamed run template
- `app/templates/base.html`
- `app/static/main.js`
- `app/static/main.css`
- `tests/test_routes.py`

### Data model changes
No new model beyond Phase 2.

Use the `Run` fields already defined:
- `goal`
- `workflow_type`
- `primary_agent_profile_id`
- `builder_agent_profile_id`
- `reviewer_agent_profile_id`
- `workspace`
- `loop_enabled`
- `max_rounds`

### Route/UI changes
Redesign the new run form so:
- `goal` is the primary field
- `Plan / Constraints` is secondary and optional
- `title` is auto-generated from `goal`
- workflow preset dropdown contains only:
  - `Single Agent`
  - `Builder -> Reviewer`
- agent dropdowns are populated from `AgentProfile`
- workspace input supports recent workspaces plus manual entry
- loop toggle and max rounds are only shown for loop-capable workflows
- for now, only `Builder -> Reviewer` is loop-capable

Recommended implementation choices:
- derive recent workspaces from recent `Run.workspace` values
- use a text input plus suggestions or chips; do not add a workspace table
- keep client-side JS minimal and server-rendered

### Test changes
- add route coverage for workflow dropdown options
- add route coverage for profile dropdown population
- add route coverage for workspace suggestions
- add route coverage for goal-required validation
- add route coverage for title auto-generation
- add route coverage for loop/max-round conditional behavior

### Risks/gotchas
- Do not reintroduce raw command fields in a hidden advanced section.
- Keep the workflow logic hard-coded; this is not the place to build a reusable engine.
- Make sure title generation is deterministic and editable later, rather than turning title into a large design problem.

### Builder checklist
- [x] Make `goal` the primary run creation field.
- [x] Make `Plan / Constraints` secondary and optional.
- [x] Remove the required create-time title field from the main UX.
- [x] Auto-generate the initial title from the goal.
- [x] Add the two-option workflow preset dropdown.
- [x] Add profile dropdowns populated from `AgentProfile`.
- [x] Add workspace picking with recent values plus manual path entry.
- [x] Show loop toggle and max rounds only for `Builder -> Reviewer`.
- [x] Remove raw command entry from the new run form.

### Verification checklist
- [x] A user can create a single-agent run without seeing reviewer-specific controls.
- [x] A user can create a builder-reviewer run with builder and reviewer profile selectors.
- [x] A user can enter a workspace manually or choose a recent one.
- [x] The generated title is reasonable and the run still persists if the user never typed a title.

### Exit checklist
- [x] Run creation is profile-based and workflow-first.
- [x] Goal is primary in the UX.
- [x] Workspace and loop controls behave as required.

---

## Phase 4 — Orchestrator Update For Two Presets

**Purpose:** keep the deterministic CLI-first backend, but route work based on selected profiles and the two supported workflow presets.

### Likely files/modules
- `app/orchestrator.py`
- `app/prompts.py`
- `app/parser.py`
- `app/agents/cli_runner.py`
- `app/db.py`
- `tests/test_orchestrator.py`
- `tests/test_parser.py`

### Data model changes
No new persistence types beyond `Run`, `Turn`, `UserNote`, and `AgentProfile`.

Keep workflow metadata minimal:
- hard-code the two preset IDs in code
- do not add a workflow table
- do not add a generalized workflow module beyond a tiny constant list if needed

### Orchestrator changes
Required behavior:
- `single_agent` runs one agent lane with one selected profile
- `builder_reviewer` preserves the deterministic relay loop
- selected profile records determine:
  - `command_template`
  - `instruction_file`
- `workspace` is passed through to the CLI runner
- background task entry points must own their own DB session rather than reusing the request session

Loop behavior:
- only `builder_reviewer` supports looping
- if loop is disabled and reviewer requests changes, route to user attention
- if max rounds are reached, route to user attention

Prompt/parser behavior:
- rename task language to goal language
- add single-agent prompt and parser contract
- keep structured-output parsing strict
- keep prompts deterministic and simple

System/routing cards:
- first try deriving routing cards in the UI from existing turns and run state
- do not persist a new system event model unless the UI truly cannot be implemented cleanly without it

### Test changes
- add single-agent parser coverage
- add single-agent orchestration coverage
- add loop-disabled builder-reviewer coverage
- add max-round coverage under the renamed run model
- add regression coverage for background-task-safe session handling
- update mocks and assertions from raw command fields to selected profiles

### Risks/gotchas
- The current background task pattern passes a request-scoped session into background work; that should be corrected in this phase.
- Avoid turning prompt construction into profile/policy layering.
- Avoid persisting extra routing artifacts unless the UI proves it is necessary.

### Builder checklist
- [x] Update the orchestrator to load selected profile records for each run.
- [x] Use profile `command_template` instead of raw per-run commands.
- [x] Load instruction text from `instruction_file`.
- [x] Add `single_agent` execution flow.
- [x] Keep `builder_reviewer` deterministic and simple.
- [x] Respect `loop_enabled` and `max_rounds` only for loop-capable workflows.
- [x] Rename runner usage from `working_directory` to `workspace`.
- [x] Fix background task/session handling so background work opens its own DB session.
- [x] Keep routing/event persistence out unless proven necessary.

### Verification checklist
- [x] A single-agent run can start and complete through the existing CLI seam.
- [x] A builder-reviewer run still routes deterministically.
- [x] Disabling loops causes reviewer change requests to stop for user attention.
- [x] Max rounds still cap builder-reviewer cycling.
- [x] Background tasks no longer rely on request-scoped DB sessions.

### Exit checklist
- [x] Both supported presets run end to end.
- [x] Profile selection drives command execution.
- [x] Orchestrator complexity remains bounded.

---

## Phase 5 — Run Detail Relay View Redesign

**Purpose:** redesign the detail page around the new product model while reusing as much of the current transcript UI foundation as possible.

### Likely files/modules
- `app/routes/threads.py` or renamed run route module
- `app/templates/thread_detail.html` or renamed run detail template
- `app/templates/base.html`
- `app/static/main.css`
- `app/static/main.js`
- `tests/test_routes.py`

### Data model changes
No required new persistence for this phase.

Prefer using existing `Turn` and `Run` data to render the view.

### Route/UI changes
Required outcomes:
- `Single Agent` renders one lane
- `Builder -> Reviewer` renders two lanes
- routing events appear as system cards in the UI
- raw prompt/output details stay collapsed by default
- title is editable later on the detail page
- metadata area shows workflow, workspace, chosen profiles, and current status
- polling remains sufficient via the existing meta refresh approach while active

Recommended approach:
- keep the transcript/chat visual language already present
- adapt the current detail page rather than rewriting the whole design system
- derive system cards from run/turn state where possible instead of persisting them

### Test changes
- add detail view coverage for single-agent layout
- add detail view coverage for builder-reviewer layout
- add title edit route coverage
- add route/template coverage for workflow metadata display
- add coverage that raw prompt/output sections remain collapsed by default

### Risks/gotchas
- The current detail page already has separate builder/reviewer columns; builders should reuse that visual base where possible.
- Deriving routing cards in the UI must stay understandable; if it becomes brittle, only then consider a minimal persisted alternative.
- Do not widen this into a full activity/event timeline subsystem.

### Builder checklist
- [x] Rename the detail view from thread to run terminology.
- [x] Keep polling via meta refresh for active states.
- [x] Render one lane for `Single Agent`.
- [x] Render two lanes for `Builder -> Reviewer`.
- [x] Show routing/system cards in the transcript UI.
- [x] Keep raw prompt/output details collapsed by default.
- [x] Add editable title support on the detail page.
- [x] Show workflow, workspace, and selected profile metadata.

### Verification checklist
- [x] Single-agent runs are easy to understand in one lane.
- [x] Builder-reviewer runs remain easy to scan in two lanes.
- [x] The detail view no longer feels like raw CRUD over backend fields.
- [x] Polling still keeps the active relay view usable without streaming.

### Exit checklist
- [x] Run detail matches the redesign target.
- [x] Chat-style relay view is in place.
- [x] No streaming/event-system scope creep was introduced.

---

## Phase 6 — Docs And Regression Hardening

**Purpose:** finish the pass by updating tests and rewriting active docs so future builders do not revert the redesign.

### Likely files/modules
- `README.md`
- `AGENTS.md`
- `docs/mvp-build-spec.md`
- `docs/build-plan.md`
- `tests/test_models.py`
- `tests/test_routes.py`
- `tests/test_orchestrator.py`
- `tests/test_parser.py`
- `tests/test_placeholder.py`

### Data model changes
None.

### Route/UI changes
None beyond final cleanup and doc accuracy.

### Test changes
Required update areas:
- model tests renamed to `Run`
- route tests renamed to `/runs/*`
- new form expectations for goal/workflow/profiles/workspace
- single-agent behavior coverage
- builder-reviewer loop toggle coverage
- detail page rendering coverage
- profile settings coverage
- any stale placeholder comments or old MVP language removed

### Docs changes
Update active docs to reflect:
- `Run` terminology
- `goal`
- `workspace`
- profile-based agent selection
- workflow presets limited to two hard-coded options
- chat-style relay view
- polling still sufficient
- clean-break dev prototype expectations where relevant

### Risks/gotchas
- If docs are left in the old thread/raw-command state, future agents will likely reintroduce removed behavior.
- This phase is not optional; documentation drift would create immediate confusion for later passes.

### Builder checklist
- [x] Rewrite tests to match the redesigned product model.
- [x] Remove old thread/raw-command assumptions from active tests.
- [x] Update `README.md` to describe the redesigned product.
- [x] Update `AGENTS.md` to describe the new active boundary.
- [x] Update `docs/mvp-build-spec.md` to reflect the redesign.
- [x] Remove stale comments and placeholder language that still describe the old MVP.

### Verification checklist
- [x] Active docs match shipped behavior.
- [x] Tests cover the two supported workflows.
- [x] No selected file still describes raw per-run command entry as the main UX.
- [x] No active doc points builders toward archived concepts.

### Exit checklist
- [x] Docs and tests match the redesign.
- [x] The pass is safe for the next builder to continue from.
- [x] The repo no longer presents the old MVP as current truth.

---

## 6. Explicit Deferred List

Do **not** add any of the following in this pass:

- YAML workflow engines
- planner workflows
- arbitrary multi-agent graphs
- JSON or public API expansion
- MCP integration
- browser extensions
- inbox/task models
- manual route-to actions
- hosted or cloud routing
- PTY embedding
- streaming transports
- websocket or SSE transport work
- profile snapshot persistence
- workflow definition frameworks
- migration frameworks
- DB backup/rollback systems
- workspace management tables
- filesystem picker dialogs
- provider-specific command templating systems
- profile delete/archive UX unless it becomes necessary for correctness

## 7. Final Recommendation

Yes, this redesign scope remains appropriately simple **if** builders hold the line on the trimmed plan:

- clean DB reset instead of migration work
- direct profile IDs on `Run`
- exactly two hard-coded workflow presets
- profile-based command selection
- chat-style relay redesign
- polling kept as sufficient
- no future-proofing layers unless they are required for the next visible UX

If the pass starts adding persistence indirection, generalized workflow abstractions, or transport changes, it has gone out of scope.
