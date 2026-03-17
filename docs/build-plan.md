# ChatMasala Workspace-First Build Plan

> Active execution plan for the next product pass.
>
> Source of truth for this pass: current non-archive repo code, the clarified product intent from the latest design discussion, and the visual direction shown by the mockups in `tmp/Multi-Chat Workflow Builder/`.
>
> Ignore for implementation decisions:
> - `docs/archive/**`
> - old run/thread assumptions that conflict with this plan
> - `tmp/**` as production code source

## 1. Product Summary

ChatMasala is no longer just a run form for a fixed builder/reviewer loop.

The intended product is a **workspace-first multi-chat routing app**:

- one workspace contains multiple chat nodes
- each chat is usable on its own
- chats can route output to other chats
- users can manually import message(s) from other chats
- the top workflow view and lower chat panels are two synchronized views of the same graph
- users choose recognizable agents/models, not internal profile jargon

This is **not** a full rewrite of the repo. It is a **bounded rebuild of the product surface** on top of the existing backend/runtime pieces that are still good:

- FastAPI app structure
- SQLite / SQLAlchemy
- CLI runner seam
- background-task session pattern
- advanced instruction-file internals

## 2. Build Strategy

### Decision

Do a **selective rebuild on top of the current repo**, not a total rewrite.

### Keep

- FastAPI app shell
- SQLite / SQLAlchemy persistence
- CLI execution seam under `app/agents/cli_runner.py`
- background-task DB session ownership pattern
- advanced prompt / instruction-file support for internal role behavior
- general settings/config plumbing where still useful

### Rebuild / Replace

- primary information architecture
- current run-first product model
- current main UI surfaces
- agent selection UX
- workspace selection UX
- routing / import UX

### Why

Trying to stretch the current `Run + workflow_type + builder/reviewer` product into the intended workspace product will create a brittle compatibility layer. But throwing away the runtime/backend pieces would waste good infrastructure.

## 3. Current-State Triage

### Keep

- CLI runner and non-interactive subprocess assumptions
- background task wrappers that open their own DB sessions
- existing DB/project structure
- useful test discipline and review loops
- collapsed raw output / prompt visibility as an advanced debugging concept

### Rework

- `Run` as the primary user concept
- `workflow_type` as the front door
- `AgentProfile` as the main user-facing abstraction
- current settings page
- current home/list/new/detail page flow
- workspace path entry
- current builder/reviewer-first vocabulary

### Drop / Retire

- stale `/threads/*` links and dead code
- current run creation form as the main product surface
- raw “agent profile” mental model in the main UX
- old thread templates/routes if still present but unused
- any assumption that ChatMasala is only a builder-reviewer runner

## 4. Product Interpretation

The clarified product model is:

- a **workspace**
- containing multiple **chat nodes**
- where each node has an agent choice
- where nodes can be standalone or connected
- where output routing can be automatic
- where message import can be manual

Important distinctions:

- **Automatic routing**
  - when node A finishes, its output may be delivered to node B
  - for the near-term pass, use only **one downstream automatic route**
  - do not auto-run chains yet

- **Manual import**
  - user explicitly imports the latest assistant message from another node
  - this is different from automatic routing
  - near-term scope: support **last assistant message only**

- **Role instructions**
  - builder/reviewer/single-agent prompt files stay internal
  - they may remain editable in advanced settings via `.md` files
  - they should not dominate the main UX

- **User-facing agent choice**
  - users should pick real agents/models, RepoPrompt-style
  - examples:
    - Claude Sonnet
    - Claude Opus
    - Codex CLI
    - Gemini CLI
    - Custom

## 5. Visual / Brand Direction

The mockups matter. They are incomplete, but they communicate the intended feel.

Preserve this direction:

- more like a product workspace than an admin tool
- airy, open, spatial layout
- top workflow canvas / overview
- lower chat panel area
- persistent left rail for history/navigation
- modular chat cards/panels
- minimal, calm chrome
- routing visible at a glance

Do **not** preserve the current feel where the app behaves like:

- a CRUD form
- a backend dashboard
- a dark settings-first admin tool

Visual direction is part of the product intent, even if the exact controls still need refinement.

## 6. Simplicity Rules

Keep this pass intentionally narrow.

### Build Now

- workspace-first shell
- top workflow representation + lower chat panels
- add/rename/delete node
- choose agent per node
- send messages in a node
- reset/refresh a node conversation
- one downstream automatic route per node
- manual import of the last assistant message from another node
- workspace browse/pick flow
- navigation cleanup
- RepoPrompt-style agent selection language

### Do Not Build Now

- arbitrary graph engine
- multi-output routing
- downstream auto-execution chains
- drag/drop graph editing
- rich arrow/canvas flowchart engine
- orchestrator node
- scribe node
- browser extension
- MCP intake
- inbox / idea revival
- hosted-browser chat routing
- PTY embedding
- Electron migration
- provider-auth platform work beyond simple local CLI detection/config

### Rule of thumb

If a feature mainly exists to future-proof the graph rather than improve the next visible UX, defer it.

## 7. Core UX Direction

### Main workspace screen

The main product surface should become:

- **left sidebar**
  - clickable logo/home
  - recent workspace history
  - new workspace action
  - settings

- **top workflow area**
  - simplified node overview / flow strip
  - node label
  - selected agent
  - route target
  - status
  - enough structure to see the system at a glance

- **lower chat area**
  - one panel per node
  - node name
  - agent dropdown
  - route target dropdown
  - import-last-message action
  - transcript
  - input box
  - reset/delete actions

### Settings / advanced surface

Settings should become:

- primarily about connected CLI providers / agent presets
- secondarily about advanced custom agents
- advanced prompt / `.md` file wiring should live here, not in the main workspace

Required near-term settings shape:

- a `CLI Providers` area
  - Claude CLI
  - Codex CLI
  - Gemini CLI
  - Custom
- each provider should show:
  - detected / not detected
  - connected / not connected
  - editable backing command
  - `Test Connection`
- agent presets shown in the main workspace should derive from these provider connections
- users should not have to think in terms of raw `AgentProfile` rows in the normal workflow

### Workspace selection

The workspace field must improve.

Near-term target:

- show current workspace path
- provide `Browse...`
- allow manual path entry as fallback

Browser-first acceptable implementation:

- simple server-backed directory picker / browser
- not a full tree editor
- not a full native desktop integration yet

## 8. Data Model Direction

### Near-term recommended model

This pass should move toward:

- `Workspace`
  - top-level saved workspace/session

- `ChatNode`
  - reusable chat/agent node within a workspace

- `ChatMessage`
  - visible transcript per node

- `AgentProfile`
  - retained internally as config storage, but reframed in UX as user-facing “Agent” choices

### Recommended schema shape

Keep this shape minimal and implementation-oriented.

#### `Workspace`

Recommended fields:

- `id`
- `title`
- `workspace_path` nullable
- `created_at`
- `updated_at`

Purpose:

- saved top-level workspace/session
- selected repo/directory for CLI execution

#### `ChatNode`

Recommended fields:

- `id`
- `workspace_id`
- `name`
- `agent_profile_id` nullable
- `downstream_node_id` nullable
- `order_index`
- `status`
  - `idle`
  - `running`
  - `needs_attention`
- `last_error` nullable
- `conversation_version`
- `created_at`
- `updated_at`

Important rules:

- one downstream automatic route only in this pass
- no edge table yet
- a node may exist with no downstream route
- a node may exist with no selected agent until configured

#### `ChatMessage`

Recommended fields:

- `id`
- `node_id`
- `sequence_number`
- `conversation_version`
- `role`
  - `user`
  - `assistant`
  - `system`
- `message_kind`
  - `manual_user`
  - `manual_import`
  - `auto_route`
  - `assistant_reply`
  - `reset_marker`
  - `error`
- `content`
- `source_node_id` nullable
- `source_message_id` nullable
- `prompt_text` nullable
- `raw_output_text` nullable
- `status`
  - `completed`
  - `running`
  - `failed`
- `error_text` nullable
- `created_at`
- `completed_at` nullable

Important invariants:

- only assistant messages should carry execution metadata like `prompt_text` / `raw_output_text`
- imported or auto-routed messages must preserve source provenance
- transcript reads should respect `conversation_version`

#### `AgentProfile`

Keep the existing table, but add enough metadata to support real built-in agent choices cleanly.

Recommended additions:

- `is_builtin`
- `builtin_key` nullable
- `sort_order`

Use this to distinguish seeded provider-backed agents from custom advanced entries.

### Normal node behavior

Standard chat nodes must behave like normal conversational CLI agents.

That means:

- user sends a normal message to a node
- the node receives conversational context plus any lightweight internal prompting
- the node returns a normal assistant reply

Do **not** make ordinary nodes depend on builder/reviewer-style structured-output parsing as their default behavior.

Structured-output contracts may remain available for specialized internal flows, but they are not the default execution model for the workspace product.

### Important guidance

Do not force users to think in terms of:

- role prompt files
- raw command templates
- builder/reviewer profiles

Instead:

- keep those as internal/advanced config
- expose recognizable agent choices in the main UI

### Future room without implementing it now

The model should not block later ideas such as:

- orchestrator node
- scribe node
- multi-output routing
- richer flow visualisation
- inbox / revived ideas

But those should **not** be implemented in this pass.

### Execution rules that must be preserved

- route target should be captured at send start for that execution
- changing agent or route affects future sends only
- delete/reset should be blocked while a node is `running`
- duplicate auto-route/import delivery should be prevented using source provenance

## 9. Keep / Rework / Drop Summary

### Keep

- backend/runtime stack
- CLI runner seam
- background-task DB session pattern
- advanced instruction-file mechanism
- deterministic execution mindset

### Rework

- `Run history` into `Workspace history`
- `Run detail` into multi-chat workspace
- `AgentProfile` into internal storage behind user-facing “Agent” presets
- settings into `Agents / Advanced`
- workspace field into browse-first UX
- current home screen into workspace shell

### Drop / retire

- stale `/threads/new`
- non-clickable logo
- run creation form as the front door
- builder/reviewer as the whole product identity
- old dead thread routes/templates

## 10. Proposed Phases

- [x] Phase 0 — Scope Lock And Active-Doc Alignment
- [x] Phase 1 — Navigation And Vocabulary Cleanup
- [x] Phase 2 — Agent UX Reframe
- [x] Phase 3 — Workspace Selection UX
- [x] Phase 4 — Workspace / Node / Message Foundation
- [x] Phase 5 — Workspace UI Cut-In
- [x] Phase 6 — Routing / Import / Reset Behavior
- [x] Phase 7 — Settings / Advanced Agent Cleanup
- [x] Phase 8 — Cutover And Legacy Retirement

---

## Phase 0 — Scope Lock And Active-Doc Alignment

**Purpose:** lock the clarified product intent before implementation drifts back into the old run-first model.

### Required outcomes

- [x] `README.md` no longer describes the app primarily as a run/preset tool.
- [x] `AGENTS.md` points builders to this workspace-first plan.
- [x] `docs/mvp-build-spec.md` is marked as outdated or secondary wherever it still contradicts this plan.
- [x] Active docs explicitly state:
  - workspace-first direction
  - bounded rebuild, not full rewrite
  - mockups are design intent, not production code

### Risks / gotchas

- If active docs still describe the wrong product, future agents will faithfully rebuild the wrong app.

---

## Phase 1 — Navigation And Vocabulary Cleanup

**Purpose:** remove stale run/thread leftovers and obvious UX contradictions immediately.

### Likely files

- `app/templates/base.html`
- current home/list templates
- current settings template labels
- route/template references still pointing at `/threads/*`

### Required outcomes

- [x] sidebar `+ New Run` no longer links to `/threads/new`
- [x] logo/home is clickable
- [x] stale thread wording is removed from active surfaces
- [x] “Agent Profile” wording is removed from the main workflow UI

### Risks / gotchas

- This is not enough by itself. Do not mistake vocabulary cleanup for product completion.

---

## Phase 2 — Agent UX Reframe

**Purpose:** make agent choice feel like selecting real tools/models, not configuring backend records.

### Likely files

- settings routes/templates
- run/workspace templates or new frontend UI
- DB seed logic
- `AgentProfile` usage points

### Required outcomes

- [x] main UI says `Agent`, not `Agent Profile`
- [x] seeded/default selectable agents look like real choices, e.g.:
  - Claude Sonnet
  - Claude Opus
  - Codex CLI
  - Gemini CLI
  - Custom
- [x] internal prompt/instruction-file details are hidden from normal workflow creation
- [x] advanced settings still allow power-user editing if needed

### Risks / gotchas

- Do not overbuild a provider auth platform in this pass.
- Do not make users configure command templates in the main workspace UI.

---

## Phase 3 — Workspace Selection UX

**Purpose:** make workspace choice usable for normal humans, not just people who know and paste repo paths.

### Likely files

- workspace/new entry UI
- settings if browse roots/config are needed
- backend directory browse endpoint(s)

### Required outcomes

- [x] workspace path can be selected through a `Browse...` flow
- [x] manual path entry remains available as fallback
- [x] selected workspace is clearly visible in the workspace shell
- [x] behavior is browser-first and simple; no Electron dependency

### Risks / gotchas

- Keep the directory picker lightweight.
- Do not sink the pass into a full file-tree UI.

---

## Phase 4 — Workspace / Node / Message Foundation

**Purpose:** establish the actual product model beneath the new UI.

### Likely files

- `app/models.py`
- `app/db.py`
- `app/schemas.py`
- tests for model behavior

### Required outcomes

- [x] a top-level workspace/session model exists
- [x] chat nodes are first-class persisted objects
- [x] node messages/transcripts are first-class persisted objects
- [x] current model choices do not force the app back into one/two-lane fixed workflows
- [x] the DB strategy is explicit and bounded

### Build guidance

- Prefer a clean pass with small, focused new entities over compatibility hacks.
- Do not add a generalized graph engine yet.
- Use a clean DB reset rather than a compatibility layer if the new model makes the old run schema awkward.

### Risks / gotchas

- Do not create two equal product models that compete (`Run` product and `Workspace` product at the same time).
- Do not keep both a real workspace product and a hidden run-first fallback alive for long.

---

## Phase 5 — Workspace UI Cut-In

**Purpose:** build the actual workspace shell and make the top workflow view + lower chat panels represent the same graph.

### Likely files

- main route shell
- new templates or a small frontend app
- UI components for workflow overview and chat panels
- sidebar/history UI

### Required outcomes

- [x] top workflow representation exists
- [x] lower chat panels exist
- [x] both reflect the same shared state/model
- [x] clicking/focusing a node in one view maps clearly to the other
- [x] each chat panel supports:
  - rename
  - delete
  - choose agent
  - send input

### Important note

The mockup in `tmp/**` is a reference for structure and feel. Do not ship it directly as production code.

Preferred implementation direction:

- if straightforward, use a small first-class frontend bundle for the synchronized workspace UI
- do not try to recreate the full shared graph/panel interaction model with ad hoc Jinja DOM patching alone
- do not copy prototype localStorage logic into production

### Risks / gotchas

- Avoid duplicating state between the diagram and the chat panels.
- Do not pull prototype over-scope features in by accident.
- Validate the frontend approach early; a quick spike is better than discovering too late that the chosen UI layer is too constrained.

---

## Phase 6 — Routing / Import / Reset Behavior

**Purpose:** make the workspace act like a routing app, not just a collection of adjacent chats.

### Required outcomes

- [x] each node can set one downstream automatic route
- [x] manual import of the latest assistant message from another node works
- [x] output routing and manual import are clearly distinct concepts in UI and code
- [x] imported or auto-routed messages visibly show their source node/message provenance
- [x] nodes can be reset/refreshed without deleting their configuration
- [x] standalone nodes still work normally with no route

### Explicit deferrals

- [ ] no multi-output routing
- [ ] no auto-run chains
- [ ] no import-last-N yet
- [ ] no orchestrator/scribe node types yet

### Risks / gotchas

- Route changes should affect future sends, not unpredictably mutate already-running work.
- Reset should preserve node identity/config while refreshing conversation context.
- Do not make imports/routed inputs invisible; the user should be able to tell where a message came from.
- Automatic routing in this pass should mean message delivery only, not downstream auto-execution.

---

## Phase 7 — Settings / Advanced Agent Cleanup

**Purpose:** keep power-user configuration available without making it the product’s main face.

### Required outcomes

- [x] settings are framed around agents/providers/advanced config
- [x] settings include a clear `CLI Providers` section, not just relabeled profile forms
- [x] users can see detected/connected state for supported CLIs
- [x] users can run `Test Connection` for supported CLIs
- [x] normal workspace agent selection is backed by provider presets, not raw profile records
- [x] advanced `.md` instruction file handling stays available, but not front-and-center
- [x] custom agents are easier to create than the current raw form
- [x] settings do not feel like the main entry point of the product

### Risks / gotchas

- This pass should improve usability, not just relabel technical fields.

---

## Phase 8 — Cutover And Legacy Retirement

**Purpose:** make the new workspace the actual app, not a side experiment.

### Required outcomes

- [x] `/` lands on the workspace-first experience
- [x] old run-first pages are removed or demoted
- [x] no active nav path leads users into the obsolete product flow
- [x] active docs/tests describe the workspace product, not the older run-first app

### Risks / gotchas

- Do not remove legacy pieces before the new workspace is actually usable.

## 11. Decision Log

### Drag-and-drop editing

**Later**

It is desirable, but not first priority. The synchronized workspace model matters more than canvas editing polish.

### Multi-output routing

**Later**

Important for the long-term “true routing app” idea, but too much for this pass.

### Chat reset / refresh

**Now**

It is part of the intended node behavior and helps conserve context/tokens.

### Orchestrator / scribe nodes

**Later, but important**

These are part of the long-term direction because they help preserve global context as the graph grows.

### Role instructions

**Keep internal**

They may remain editable in advanced settings via linked `.md` files, but they should not dominate the main UX.

### Agent presets / providers

**Now**

The workspace should offer real agent choices in a simple dropdown, RepoPrompt-style.

Settings must also include a RepoPrompt-style `CLI Providers` surface so provider connection/detection/testing is explicit, rather than hidden behind abstract profile management.

## 12. Final Simplicity Check

This scope is still appropriately simple **if** the pass stops at:

- one workspace model
- generic node/chat behavior
- one downstream route per node
- manual import of the latest assistant message only
- reset/refresh support
- no drag/drop
- no multi-output
- no orchestrator/scribe implementation yet
- no provider-auth platform explosion

Complexity spikes if this pass tries to combine any two of:

- drag/drop graph editing
- multi-output routing
- auto-run chains
- orchestrator/scribe implementation
- browser extension / MCP / inbox work
- keeping the old run-first product alive alongside the new workspace product
