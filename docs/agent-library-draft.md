# ChatMasala Agent Library Draft

> Second draft. Refined after joint review with Claude and Codex.

## 1. Design Principles

Agents and flows are separate concerns.

- **Agent** = a reusable role definition (purpose, constraints, output contract)
- **Flow** = a composition of agents wired together for a specific task
- **Template** = a saved, loadable flow pattern users can start from and edit

Agent types should not hardcode a workflow. They define what a node *can do*, not how it is connected. Users wire them however they want.

A proper agent definition includes:

- purpose
- instruction file
- allowed actions
- forbidden actions
- output contract
- loop suitability
- whether it requires human approval

The core safety goal:

- ideation agents may propose ideas
- only execution agents may implement
- prompt alone is not enough — see §5 for the control model

---

## 2. Agent Categories

### Ideation

- Brainstorm A
- Brainstorm B
- Repo Context
- RepoPrompt Crafter

### Critique / Decision

- Critic
- Decider

### Planning

- Planner
- Scribe

### Execution

- Builder
- Reviewer

### Control

- Human Gate
- Router *(future — not part of the current executable library)*

---

## 3. Agent Definitions

### Brainstorm A

Purpose:
- generate first-pass ideas, options, directions, and angles

Allowed:
- read provided context
- explore tradeoffs
- propose code concepts at a high level

Forbidden:
- no file edits
- no implementation steps executed
- no pretending work was done

Output contract:
- ideas
- tradeoffs
- unanswered questions
- suggested next direction

Loop suitability: yes

Human approval required: no

---

### Brainstorm B

Purpose:
- produce a distinct second-pass direction rather than echoing Brainstorm A

Allowed:
- read prior brainstorm output
- propose alternative approaches
- widen or sharpen the option space

Forbidden:
- no file edits
- no implementation
- no shallow agreement-only output

Output contract:
- alternative ideas
- contrasting approach
- strengths/weaknesses compared with prior brainstorm

Loop suitability: yes

Human approval required: no

---

### Critic

Purpose:
- stress-test proposed ideas and find weak assumptions

Allowed:
- critique ideas
- identify missing constraints
- reject weak plans

Forbidden:
- no implementation
- no replacing critique with solutioning only

Output contract:
- risks
- contradictions
- missing information
- what would need to improve
- if configured for loop routing: strict final line `GO` or `NO_GO`

Loop suitability: yes

Human approval required: no

---

### Decider

Purpose:
- decide whether the current loop produced something ready to move forward

Allowed:
- compare prior brainstorm and critique outputs
- choose whether to continue or stop

Forbidden:
- no implementation
- no sprawling ideation

Output contract:
- concise decision summary
- exact final line: `GO` or `NO_GO`

Note: `HUMAN` as a third sentinel is a future routing option. For now, wire a Human Gate node manually if a pause is needed. Human Gate is the current model for human-in-the-loop pauses.

Loop suitability: yes

Human approval required: optional

---

### Planner

Purpose:
- turn accepted ideas into a clear implementation or execution plan

Allowed:
- structure work into phases
- identify dependencies
- produce checklists and plans

Forbidden:
- no direct code implementation
- no vague brainstorming-only output

Output contract:
- phased plan
- scope boundaries
- risks
- next actions

Loop suitability: optional

Human approval required: often yes before Builder

---

### Repo Context

Purpose:
- inspect the repository and explain the relevant architecture or current implementation

Allowed:
- read files
- summarize current structure
- identify likely impacted areas

Forbidden:
- no code edits
- no implementation

Output contract:
- codebase summary
- relevant files
- constraints
- architectural implications

Loop suitability: optional

Human approval required: no

---

### RepoPrompt Crafter

Purpose:
- turn repo context into a high-quality RepoPrompt brief ready for submission

This is intentionally narrow. Repo Context explains the codebase; RepoPrompt Crafter transforms that explanation into a structured prompt brief for RepoPrompt. They do different jobs.

Allowed:
- inspect repository context output
- prepare prompt text for RepoPrompt
- suggest what files/context should be included

Forbidden:
- no app code implementation
- no pretending RepoPrompt work has already run unless it actually has

Output contract:
- prompt text
- context summary
- recommended file set
- expected deliverable shape

Loop suitability: optional

Human approval required: no

---

### Builder

Purpose:
- implement approved work

Allowed:
- write code
- edit files
- run project-appropriate implementation steps

Forbidden:
- no broad ideation loops
- no unapproved scope expansion

Output contract:
- implementation summary
- files changed
- verification status

Loop suitability: yes, but only in execution flows

Human approval required: often yes before or after run, depending on workflow

---

### Reviewer

Purpose:
- review implementation for bugs, regressions, missing tests, and correctness

Allowed:
- inspect diffs
- identify defects
- send fixes back to Builder

Forbidden:
- no pretending code is correct without evidence
- no broad feature invention

Output contract:
- findings
- severity
- exact final line: `GO` or `NO_GO`

Loop suitability: yes

Human approval required: optional

---

### Scribe

Purpose:
- preserve durable conclusions across a workflow

Scribe is a passive recorder, not an active routing node. It does not drive the workflow forward — it captures what was decided and hands off clean context.

Allowed:
- summarize decisions
- record accepted conclusions
- maintain high-signal context

Forbidden:
- no implementation
- no independent routing decisions

Output contract:
- concise summary
- durable notes
- handoff context

Loop suitability: no

Human approval required: no

---

### Human Gate

Purpose:
- explicitly pause the workflow and wait for user direction

Human Gate is the current model for human-in-the-loop approval. It is a manually wired pause node, not a sentinel. A future `HUMAN` sentinel could automate routing into a gate, but that is not implemented yet.

Allowed:
- present current state
- request approval
- route only after user input

Forbidden:
- no autonomous continuation

Output contract:
- current state summary
- options
- requested user decision

Loop suitability: not a loop worker; it is a pause/control node

Human approval required: yes by definition

---

### Router *(future — not part of the current executable library)*

Router depends on multi-output/conditional routing, which is not yet implemented in ChatMasala. It is included in the taxonomy because it is the motivating use case for that infrastructure work, but it should not be built as an agent profile until multi-output routing ships.

Purpose:
- choose which route should be taken next when routing is conditional on output content

Allowed:
- inspect current outputs
- recommend next branch

Forbidden:
- no implementation
- no hidden decision-making without making the route reason visible

Output contract *(draft, subject to change with routing infrastructure)*:
- route choice
- reason for route
- future sentinel form: `ROUTE:<label>`

Blocked on: multi-output routing (highest-priority deferred infrastructure item)

---

## 4. Control Model (Guardrails)

Prompt text alone is not enough to enforce agent role boundaries.

Each agent profile should declare a set of mode-level constraints that ChatMasala can enforce independently of the prompt:

| Flag | Description |
|---|---|
| `can_edit_files` | agent is allowed to write or modify files |
| `can_run_commands` | agent is allowed to execute shell commands |
| `requires_human_approval` | workflow must pause for user approval before this node continues |
| `read_only_repo` | agent may read the repo but cannot write to it |
| `max_turn_scope` | limit how many tool calls or steps a single agent turn may take |

This is how brainstorm-style agents are kept from turning into builders, even if the underlying CLI agent has broader capabilities.

Initial constraint assignments by category:

- **Ideation agents** (Brainstorm A/B, Repo Context, RepoPrompt Crafter): `read_only_repo: true`, `can_edit_files: false`, `can_run_commands: false`
- **Critique/Decision agents** (Critic, Decider): same as ideation
- **Planner, Scribe**: same as ideation
- **Builder**: `can_edit_files: true`, `can_run_commands: true`, `requires_human_approval: true` (before run, by default)
- **Reviewer**: `can_edit_files: false`, `can_run_commands: false` (read + inspect only)
- **Human Gate**: `requires_human_approval: true` by definition

---

## 5. Implementation Notes

### Instruction files

Agent profiles should be backed by dedicated `.md` files:

- `profiles/agents/brainstorm-a.md`
- `profiles/agents/brainstorm-b.md`
- `profiles/agents/critic.md`
- `profiles/agents/decider.md`
- `profiles/agents/planner.md`
- `profiles/agents/repo-context.md`
- `profiles/agents/repoprompt-crafter.md`
- `profiles/agents/builder-v2.md`
- `profiles/agents/reviewer-v2.md`
- `profiles/agents/scribe.md`
- `profiles/agents/human-gate.md`

The old `builder.md`, `reviewer.md`, and `single-agent.md` are legacy references. Do not update them — replace them.

Router does not get a profile file until multi-output routing ships.

---

## 6. Example Flow Patterns

These are recommended starting patterns, not fixed definitions. Users can wire agents however they want. Templates (§7) make these loadable.

### Brainstorm Loop

```
Brainstorm A → Brainstorm B → Critic → Decider
                                         ↓ NO_GO → back to Brainstorm A
                                         ↓ GO → Planner
```

Best for: early-stage idea exploration before any implementation commitment.

---

### Plan Then Build

```
Planner → Human Gate → Builder → Reviewer
                                    ↓ NO_GO → back to Builder
                                    ↓ GO → Scribe
```

Best for: executing a known plan with a human checkpoint before code runs.

---

### Spec to Code

```
Repo Context → RepoPrompt Crafter → Planner → Human Gate → Builder → Reviewer
                                                                         ↓ NO_GO → back to Builder
                                                                         ↓ GO → Scribe
```

Best for: starting from an existing codebase and building a new feature with full context.

---

### Research Synthesis

```
Brainstorm A → Critic → Scribe
```

Best for: capturing a one-pass research or analysis result with critique baked in.

---

### Writing Loop

```
Writer (Brainstorm A) → Critic → Editor (Brainstorm B) → Decider
                                                            ↓ NO_GO → back to Writer
                                                            ↓ GO → Scribe
```

Best for: iterative writing or document drafting with critique gating.

---

## 7. Template Workflow Library *(future)*

Templates are saved, loadable flow configurations. They are prewired agent arrangements that users can load and then edit freely. They are not mandatory presets.

Good first templates to build:

| Template name | Flow |
|---|---|
| Brainstorm Loop | Brainstorm A → Brainstorm B → Critic → Decider |
| Plan Then Build | Planner → Human Gate → Builder → Reviewer → Scribe |
| Spec to Code | Repo Context → RepoPrompt Crafter → Planner → Human Gate → Builder → Reviewer |
| Research Synthesis | Brainstorm A → Critic → Scribe |
| Writing Loop | Writer → Critic → Editor → Decider |

Templates are the accelerator layer. The primary model is still workspace + nodes + routing.

---

## 8. Status

- concept draft: yes (second pass)
- implemented in app: no
- suitable as planning input for the next pass: yes
- next action: write agent profile `.md` files, then add control model flags to agent schema
