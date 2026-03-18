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

---

---

# Pass 2 — Workspace UX, Loop Routing, and Visual Direction

> Pass 1 (Phases 0–8) established the workspace-first foundation. Pass 2 corrects usability gaps found during live testing, introduces proper loop routing semantics, cleans up the provider/agent surface, and moves toward the visual direction shown in the mockups.
>
> Active execution source of truth for this pass: this document and the mockup screenshots in `tmp/Multi-Chat Workflow Builder/screeenshots/`.
>
> Implementation order: usability first → routing/loop model → provider/agent defaults → visual polish. Do not start visual restyling before structural changes are complete.
>
> Important override: where Pass 2 conflicts with earlier Pass 1 routing/model guidance in this document, Pass 2 wins. In particular:
> - `downstream_node_id` is superseded by `output_node_id` and `loop_node_id`
> - output routes remain message-delivery-only
> - loop-back routes are the one allowed auto-execution path in this pass

## Pass 2 — Decision Log

### Auto-execution semantics: resolved

Output routes and loop-back routes have different auto-execution rules:

- **Output route** (`output_node_id`): message delivery only. When a node completes and routes output to another node, the output is delivered as a new message in the target node. The target node does **not** auto-run. The user triggers the next send manually.
- **Loop route** (`loop_node_id`): auto-execute. When a node detects `NO_GO`, the loop target is automatically run with the routed message as input. This is the one permitted auto-execution in this pass. Without it, the build→review→build cycle requires manual intervention at every step, which defeats the purpose.

This resolves the conflict with the earlier "message delivery only" scope: that rule applies to output routes. Loop-back is a narrow, deliberate exception.

### GO / NO_GO strict sentinel

When a node has a `loop_node_id` set, the system checks the final non-empty line of the assistant response after trimming whitespace:

- If the final line is exactly `GO` (case-insensitive): route to `output_node_id` (message delivery, no auto-run of target)
- If the final line is exactly `NO_GO` (case-insensitive): route to `loop_node_id` and auto-run target
- If neither sentinel is present: stop auto-routing, set node status to `needs_attention`, and record an error note like "Looped node did not end with GO or NO_GO"
- If `loop_count >= max_loops`: stop looping regardless of sentinel, route to `output_node_id`, set node status to `needs_attention`

The instruction file or system prompt for any looped node **must** tell the agent to always end its response with `GO` or `NO_GO`. This is the agent's contract with the routing system. It is not inferred, guessed, or parsed from prose.

### Input / Output / Loop are three separate concepts

Each chat node has three distinct relationships to other nodes:

| Relationship | Storage | Meaning | Trigger |
|---|---|---|---|
| Input from | Derived in UI/state, not a single persisted FK | Informational: which upstream node(s) feed this one | Derived from output/loop relationships and recent provenance |
| Output to | `output_node_id` | Where to deliver output when GO or no loop is set | Message delivery; target does not auto-run |
| Loop to | `loop_node_id` | Where to send back on NO_GO | Message delivery + auto-run of loop target |

These are shown as three separate visible elements in the UI, not one combined "route" dropdown.

`Input from` should be derived for display, not stored as a single FK on `ChatNode`. A node may have more than one inbound relationship over time, so the UI should render the current upstream source(s) from:
- configured output/loop relationships pointing at this node
- recent imported/auto-routed message provenance

For Pass 2, it is acceptable to show:
- a single "Input from" label when there is one clear upstream source
- multiple compact source chips when more than one node currently feeds this node

### Codex CLI is not a PTY-only defer

`codex exec -` is the correct non-interactive invocation. The prompt is read from stdin when `-` is passed. The seeded Codex CLI agent command must be changed from `codex` to `codex exec -`.

### Built-in agent commands should not pin model versions

The default seeded agent should not hardcode a model version because:
- Model IDs go stale as new versions are released
- The CLI default tracks the recommended model as the CLI is updated
- Pinning requires a DB migration every time a new model is released

Required rule:
- always seed one default unpinned Claude agent that follows the CLI default

Permitted optional rule:
- add pinned variants only if you intentionally want explicit model presets exposed in the UI

Minimum builtins:
- Claude: `claude --dangerously-skip-permissions` (no `--model` flag)
- Codex: `codex exec -`
- Gemini: `gemini` (subject to env config)

If pinned variants are kept, they must be treated as optional named presets, not as the only Claude options. Power users can also create a custom agent with an explicit `--model` flag.

### Gemini CLI needs environment configuration, not API key entry

The `gemini` CLI requires `GEMINI_API_KEY` to be set in the shell environment. This is not something ChatMasala manages. The settings page should:
- Detect whether `GEMINI_API_KEY` is present in `os.environ`
- Show "CLI detected — not configured. Set GEMINI_API_KEY in your shell environment." if missing
- Show "CLI detected — configured." if present
- Not prompt users to paste keys into the app

### New workspace: immediate-entry flow

Clicking "+ New Workspace" should immediately create an untitled workspace with one default node and redirect the user to it. No form-first interruption. Title defaults to "New Workspace" and is editable inline on the workspace page. Workspace path is optional — nodes without a path run the CLI without a working directory.

### Visual direction: light theme

The mockup uses a white/near-white background with dark text and clean spacing. The current dark theme does not match the intended product feel. The light theme switch is a Pass 2 goal but should happen after structural changes are complete (Phase 12).

---

## Pass 2 — Proposed Phases

- [x] Phase 9 — Core Workspace Usability
- [x] Phase 10 — Loop / Routing Model
- [x] Phase 11 — Provider, Agent, and Settings Cleanup
- [x] Phase 12 — Visual Polish and Light Theme

---

## Phase 9 — Core Workspace Usability

**Purpose:** fix the usability gaps that make the current workspace difficult to use, regardless of routing or visual direction.

### Likely files

- `app/templates/workspace_detail.html`
- `app/templates/workspace_new.html`
- `app/templates/base.html`
- `app/routes/workspaces.py`
- `app/static/main.css`

### Required outcomes

#### Workflow strip

- [x] Workflow strip never wraps to a second line. It stays on one horizontal row and scrolls horizontally when nodes overflow. Apply `flex-wrap: nowrap; overflow-x: auto` on the strip container.
- [x] Workflow node chips show a numbered circle (①②③④ etc.) as the primary visual identifier, not just the node name.

#### Chat panels

- [x] Chat panels have a fixed `min-width` of approximately 380px and `flex-shrink: 0`. They do not compress when there are many nodes.
- [x] The panel container scrolls horizontally. Only 2–3 panels are visible at once on a standard screen; the rest are reachable by scrolling.
- [x] Panel layout order top to bottom: node name → Input from (if set) → Output to dropdown → Loop to dropdown (if loop is configured) → message transcript → composer input → Agent picker → action buttons (Reset, Import, Delete).

#### Composer / input

- [x] The message textarea auto-grows as the user types. It starts at approximately 2 lines tall and expands up to a reasonable max (e.g. 8 lines) before scrolling internally.
- [x] Cmd+Enter / Ctrl+Enter submits the message. Enter alone inserts a newline.

#### Running state

- [x] When a node's status is `running`, the panel shows a clearly visible animated indicator in the transcript area (e.g. a pulsing "Thinking…" row or a spinner). The user must be able to tell immediately that the node is active without waiting for polling to return.
- [x] The workflow node chip for a running node shows a distinct visual state (e.g. pulsing border or animated dot).

#### Status labels

- [x] Status values are displayed as human-readable labels everywhere in the UI:
  - `idle` → "Ready"
  - `running` → "Running…"
  - `needs_attention` → "Needs attention"

#### New workspace flow

- [x] Clicking "+ New Workspace" in the sidebar does **not** show a form page. It immediately creates a new workspace (title: "New Workspace", no path, one default node with the default agent) and redirects to the workspace detail page.
- [x] The workspace title is editable inline on the workspace detail page (click to edit, Enter to save).
- [x] The workspace path is editable inline or via a Browse button on the workspace detail page. It is not required.

#### Default node behavior

- [x] When a new node is added to a workspace, it automatically gets the first available builtin agent (Claude). It should never be created without an agent if any builtins exist.
- [x] When a new node is added and the workspace already has at least one other node, the previous node's `output_node_id` is automatically set to point to the new node. This can be changed but should be the default.

#### Sidebar persistence

- [x] The workspace sidebar (list of recent workspaces) is visible on all pages: workspace list, workspace detail, workspace new (if kept), and settings.
- [x] The settings page has a visible "Back to Workspace" button or link in the header when navigated to from a workspace.

### Risks / gotchas

- Do not break the existing send/route/reset functionality while refactoring the layout.
- The auto-grow textarea must not conflict with Cmd+Enter submit.
- Running state feedback relies on polling. The current meta-refresh approach may need a shorter poll interval (e.g. 3–5 seconds) on the workspace detail page while any node is `running`.

---

## Phase 10 — Loop / Routing Model

**Purpose:** replace the single `downstream_node_id` with three separate relationships (input, output, loop), implement GO/NO_GO sentinel detection, and wire up loop auto-execution.

### Likely files

- `app/models.py` (ChatNode schema change)
- `app/routes/workspaces.py` (`_execute_node_send`, `_deliver_auto_route`, new `_execute_loop_send`)
- `app/templates/workspace_detail.html` (three separate relationship controls)
- `tests/test_workspace_models.py`

### Data model changes

Replace `downstream_node_id` on `ChatNode` with:

```
output_node_id    Integer FK(chat_nodes.id) nullable   -- where to route on GO or unconditionally
loop_node_id      Integer FK(chat_nodes.id) nullable   -- where to loop back on NO_GO
max_loops         Integer default 3                    -- circuit breaker
loop_count        Integer default 0                    -- current loop iteration for this conversation_version
```

Rules:
- `output_node_id` and `loop_node_id` may be the same node or different nodes.
- `loop_count` resets to 0 when `conversation_version` increments (i.e. on reset).
- A node with no `loop_node_id` behaves exactly as before — no sentinel detection, output is delivered to `output_node_id` on completion (message delivery only, no auto-run of target).
- A node with `loop_node_id` set enables sentinel detection and loop auto-execution.
- `Input from` is a derived display concept and should not be stored as a single `input_node_id` field on `ChatNode`.

A clean DB reset is acceptable to apply this schema change. Do not add a migration framework.

### Required outcomes

#### Data model

- [x] `ChatNode` has `output_node_id`, `loop_node_id`, `max_loops`, and `loop_count` fields.
- [x] `downstream_node_id` is removed.
- [x] Workspace isolation checks are updated to use the new field names.
- [x] Inbound route cleanup on node deletion covers all new route FKs.
- [x] Tests cover the new schema.

#### GO / NO_GO detection

- [x] After a node with `loop_node_id` set completes a send, the final non-empty trimmed line of the assistant response is checked.
- [x] Exact match `GO` (case-insensitive) → route output to `output_node_id` as a delivered message (no auto-run of target).
- [x] Exact match `NO_GO` (case-insensitive) → increment `loop_count`; if `loop_count >= max_loops`, route to `output_node_id` and set node to `needs_attention` with an error note "Max loops reached"; otherwise deliver to `loop_node_id` and auto-run the loop target.
- [x] Neither sentinel present and `loop_node_id` is set → do not auto-route; set node to `needs_attention` with an error note like "Looped node did not end with GO or NO_GO".
- [x] Node with no `loop_node_id` → no sentinel detection; route output to `output_node_id` unconditionally (message delivery, no auto-run).

#### Loop auto-execution

- [x] When the loop target receives the routed message, the loop target node is automatically run (as if the user pressed Send with the routed content as the new user message). This is the only permitted auto-execution in this pass.
- [x] Loop auto-execution respects the same guards as manual sends: node must not already be `running`, must have an agent assigned.
- [x] If the loop target has no agent, delivery still happens but auto-run does not; node status is set to `needs_attention`.

#### UI

- [x] Each chat panel shows three separate relationship controls:
  - **Input from:** read-only label or chips showing which node(s) currently feed this one (or "—" if none)
  - **Output to:** dropdown to select `output_node_id` (options: No output, [other nodes])
  - **Loop to:** dropdown to select `loop_node_id` (options: No loop, [other nodes]) + a `Max loops` number input (only shown when a loop target is selected)
- [x] The workflow strip shows a visual loop indicator around nodes that form a loop (orange dashed border enclosing all nodes between `loop_node_id` source and target, with a "Loop max: N" badge).
- [x] When `loop_count > 0` on a running loop, the badge updates to show "Loop N/max".

### Risks / gotchas

- Loop auto-execution must use its own DB session (background task pattern), same as manual sends.
- DO NOT auto-run the output target. Only the loop target auto-runs.
- Changing `loop_node_id` or `output_node_id` affects future sends only. It does not retroactively affect a currently running send.
- Prevent infinite loops: the `max_loops` circuit breaker is mandatory and must be checked before each loop-back.
- Workspace isolation checks must cover all three new FK fields (`output_node_id`, `loop_node_id`) in `set_node_route` equivalents and `_deliver_auto_route` equivalents.

#### Edge case: GO with no output_node_id

- If a node ends with `GO` and `output_node_id` is `None`: do not error. Stop on the current node, set status to `idle`, do not deliver any message. The workflow simply ends at this node.
- If `loop_count >= max_loops` (circuit breaker fires) and `output_node_id` is `None`: same — set status to `needs_attention` with error note "Max loops reached — no output node configured", do not deliver any message. The user must manually inspect the node and configure an output or reset.

#### Edge case: loop target already running

- Before auto-executing the loop target, check `target_node.status == "running"`.
- If the loop target is already running: deliver the message to its transcript (so it appears in context) but do **not** trigger auto-run.
- Set the **source** node's status to `needs_attention` with error note: "Loop target is already running — manual retry required once it finishes."
- Do not silently drop the message or silently skip the auto-run without a visible error state.

---

## Phase 11 — Provider, Agent, and Settings Cleanup

**Purpose:** fix provider commands, agent defaults, and the settings navigation so the app works correctly for real users out of the box.

### Likely files

- `app/db.py` (seed data)
- `app/routes/settings.py`
- `app/templates/settings.html`
- `app/templates/base.html`
- `app/routes/workspaces.py` (default agent on new node)

### Required outcomes

#### Seeded builtin agents

- [x] Seeded builtins are updated to follow one consistent rule:
  - **Required defaults:**
    - **Claude** (default): command `claude --dangerously-skip-permissions` — no `--model` flag. Name: "Claude".
    - **Codex**: command `codex exec -`. Name: "Codex".
    - **Gemini**: command `gemini`. Name: "Gemini CLI".
  - **Optional pinned variants:** only include explicit Sonnet / Opus / Haiku presets if you intentionally want them exposed as separate choices in the UI. If included, they are additional presets, not replacements for the default unpinned Claude agent.
- [x] The default agent for new nodes is "Claude" (the no-model-pinned builtin).

#### Provider status

- [x] The CLI Providers section in settings detects:
  - Binary presence on PATH (`shutil.which`)
  - For Gemini CLI specifically: whether `GEMINI_API_KEY` is set in `os.environ`
- [x] Provider status labels:
  - Binary on PATH + (Gemini: env var set or non-Gemini): show "Connected ✓" in green
  - Binary on PATH + Gemini env var missing: show "CLI detected — not configured. Set GEMINI_API_KEY in your shell environment." in amber
  - Binary not on PATH: show "Not detected" in grey
- [x] After a successful "Test Connection" (exit code 0), the provider card updates to show "Connected ✓".
- [x] After a failed "Test Connection" (non-zero exit or error), the card shows "Error — see output below" in red.

#### Settings navigation

- [x] The settings page always shows the workspace sidebar (list of recent workspaces).
- [x] If the user navigated to settings from a workspace, a "← Back to [workspace name]" link or button is shown in the settings header.
- [x] The settings page layout uses a tab structure: `CLI Providers` | `Built-in Agents` | `Custom Agents`.

#### Custom agent creation

- [x] The "New Custom Agent" flow uses a modal or inline form (not a separate page navigation), consistent with the mockup in `tmp/Multi-Chat Workflow Builder/screeenshots/`.
- [x] The modal asks for: Agent Name (required) + Description/purpose (optional). Advanced fields (command template, instruction file) are collapsed behind an "Advanced" disclosure by default.
- [x] The modal also asks for a provider preset (Claude / Codex / Gemini / Custom). Choosing a provider preset auto-fills the command template in Advanced.
- [x] If no provider preset is chosen and no advanced command is supplied, save is blocked with a clear validation error.

#### Codex non-interactive mode

- [x] The seeded Codex command is `codex exec -` (not `codex`). This uses Codex's built-in non-interactive mode where the prompt is read from stdin.
- [x] A note is visible in the Codex provider card: "Uses `codex exec -` for non-interactive execution."

### Risks / gotchas

- If the DB already has old seeded builtins, the seed function must update existing rows by `builtin_key`, not just skip if they exist.
- Do not prompt users to paste API keys into the app. Env var detection only.
- The "Back to workspace" button requires passing the referring workspace ID through the settings navigation (e.g. via a `?from=ws_id` query param or by reading the referrer).

---

## Phase 12 — Visual Polish and Light Theme

**Purpose:** move the visual direction from dark dev-tool toward the airy, calm workspace shown in the mockups.

> Do this phase last. Structural and routing changes in Phases 9–11 will modify the same templates. Restyling before structure is finalised wastes effort.

### Likely files

- `app/static/main.css`
- `app/templates/base.html`
- `app/templates/workspace_detail.html`
- `app/templates/workspace_list.html`
- `app/templates/settings.html`

### Required outcomes

#### Light theme

- [x] The app uses a light background (white or very light grey, e.g. `#f9fafb`) with dark text (`#111827` or similar) as the default.
- [x] The current dark theme CSS variables are replaced or overridden with light theme values.
- [x] The sidebar uses a slightly darker panel (e.g. `#f3f4f6`) to distinguish it from the main content area.
- [x] Chat panels use a white card background with a subtle border and shadow.
- [x] User messages use the accent colour (indigo/violet, matching the mockup) as bubble background.
- [x] Assistant messages use a light grey bubble.

#### Workflow strip

- [x] Node chips in the workflow strip use the clean card style from the mockup: white background, 1px border, rounded corners, bold numbered circle, node name, agent name, status badge.
- [x] Route arrows (`→`) between chips are simple, not heavy.
- [x] Loop group is enclosed in an orange dashed border with a "Loop Max: N" orange pill badge at the top of the group.

#### Chat panels

- [x] Panel headers are clean: node name (large, editable on click) + status badge aligned right.
- [x] The "Input from", "Output to", and "Loop to" controls are clearly labelled and visually grouped below the header.
- [x] The transcript area is well-padded and readable.
- [x] The composer area at the bottom is clearly delineated: input grows with text, send button is prominent, agent picker is below or alongside the input.

#### Settings

- [x] Settings page feels minimal and information-dense in a good way. Tabs are clean pill-style toggles as in the mockup.
- [x] CLI provider cards are clean rows: provider name, status badge (Connected ✓ / Not detected), command input, Test Connection button.
- [x] Agent list items are clean rows: agent name, ID/key, no raw internals visible at first glance.

#### Typography and spacing

- [x] Use Inter for UI chrome and JetBrains Mono for code/command/path values (already linked in base.html — verify it is being applied).
- [x] Consistent spacing scale throughout: 4px base unit, sections at 16–24px gap.
- [x] No hard-coded pixel colours — use CSS custom properties throughout so future theme changes are a single-variable edit.

### Risks / gotchas

- Keep a dark-mode fallback in CSS custom property structure so dark theme can be re-enabled with a media query in future. Do not hard-delete the dark design tokens; replace them.
- Test on a standard 1440px wide screen and a 1280px wide screen. Panels should scroll, not compress.

---

## Pass 2 — Deferred Backlog

These items were explicitly agreed as out of scope for Pass 2. They must be reviewed at the start of Pass 3 planning and promoted or re-deferred.

### Routing / Graph

- **Multi-output routing** — each node routes to more than one downstream node simultaneously. Important for the long-term routing app model but too much structural change for now.
- **Auto-run chains** — when output is routed, the target node auto-executes without a user trigger. Only loop-back auto-runs in this pass.
- **Import last N messages** — currently only the last assistant message can be imported. Import of a selectable range is deferred.
- **Richer flow arrows / canvas routing** — visual connectors between nodes on a canvas. The current chip+arrow strip is the interim solution.
- **Drag-and-drop node reordering** — desirable but not first priority.

### Node types

- **Orchestrator node** — a node that manages routing decisions for other nodes.
- **Scribe node** — a node that accumulates global context across the workspace.

### Platform

- **Codex TTY / persistent sessions** — if Codex requires a live session rather than per-send invocation, a PTY wrapper would be needed. `codex exec -` should work for now; revisit if it still fails.
- **Browser extension / MCP intake**
- **Inbox / idea revival**
- **Electron migration**
- **Cloud or multi-user features**

### Settings / Agents

- **AI-assisted custom agent creation** — user describes the agent they want in natural language; a helper agent generates the instruction file and config draft; user edits only if needed. Agreed as a future phase by the user on 2026-03-17.
- **Saved workflow templates** — save and reload a node configuration as a reusable template (mockup shows this as a "Saved Workflows" tab in settings).

### Visual / UX

- **Loop boundary animation** — animated dashed border or flowing arrows between looped nodes.
- **Dark mode toggle** — re-expose dark mode as a user setting once the light theme is the default.

---

## Pass 3 — Agent Role / Model Split

### Why this pass

The current `AgentProfile` table bundles two separate concepts:
- **Role** — the behavioral instructions for an agent (what it does, what it is forbidden to do, its output contract)
- **Runtime/Model** — the CLI command and provider used to execute it (Claude, Codex, Gemini)

This means "Brainstorm A on Claude" and "Brainstorm A on Codex" would require two separate AgentProfile rows with duplicated content. That is the wrong model.

The goal of Pass 3 is a clean architecture where:
- roles are reusable across models
- models are reusable across roles
- a node independently selects both

### New architecture

Two separate concerns:

**AgentRole** — a new table. Defines what a node does:
- name (e.g. "Brainstorm A")
- slug (machine key, e.g. "brainstorm-a")
- description
- instruction_file (path to the .md file)
- is_builtin

**AgentProfile** (trimmed) — kept as runtime-only. Defines what executes it:
- name (e.g. "Claude", "Codex")
- provider
- command_template
- is_builtin

**ChatNode** gains `agent_role_id` FK alongside the existing `agent_profile_id`.

### Agent role library

Nine built-in roles seeded from md files in `profiles/agents/`:
- Brainstorm A
- Brainstorm B
- Critic
- Decider
- Planner
- Builder (from builder-v2.md)
- Reviewer (from reviewer-v2.md)
- Human Gate
- Repo Context

### Execution change

`_execute_node_send` loads the role's instruction_file content and prepends it to the prompt before conversation history. Nodes with no role assigned run bare (existing behavior unchanged).

### Implementation phases

Phase 1 — Data model split
- Add AgentRole model to models.py
- Remove instruction_file from AgentProfile
- Add agent_role_id FK to ChatNode
- Add BUILTIN_ROLES + seed_builtin_roles() to db.py
- Remove seed_default_profiles()
- DB reset

Phase 2 — Execution integration
- Load role instructions in _execute_node_send and prepend to prompt
- Add POST /workspaces/{ws_id}/nodes/{node_id}/role route
- Pass roles list to workspace_detail template context

Phase 3 — Settings + node UI
- Replace single agent picker in node panel with two dropdowns: Role and Model
- Add Roles tab to settings (built-in roles read-only, custom roles manageable)
- Remove legacy profile form routes

Phase 4 — Cleanup
- Remove seed_default_profiles() function body
- Remove profile_form.html
- Remove legacy /settings/profiles/* routes
- Full test suite pass

### Deferred (not in this pass)

- Frontmatter control flag parsing and enforcement (can_edit_files, can_run_commands, etc.)
- Human Gate pause/approval execution mechanic
- Scribe and RepoPrompt Crafter role files (separate design track)
- Template / saved workflow library
- Multi-output routing

### Keep / Drop

Keep: workspace/node/message model, CLI runner, background task pattern, FastAPI structure, all existing routing logic

Drop: AgentProfile.instruction_file column, seed_default_profiles(), profile_form.html, /settings/profiles/new and /settings/profiles/{id}/edit routes
