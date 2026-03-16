# FORGE Spec Template
> **You are here:** This is the Spec Template — the execution tool. Use it to turn a project direction into a complete agent-ready brief.
>
> **The other docs in this system:**
> - **Quick Reference** (`FORGE-quickref.md`) — start here if you don't have a project direction yet. If the request is a new idea or open-ended, go to the Quick Reference and run the Divergence → Convergence Loop or the Self-Spec Agent first. Come back here once you have a chosen direction.
> - **Canonical Framework** (`FORGE-canonical.md`) — go there if you encounter a concept in this template you don't fully understand. Each section maps to a section in the canonical doc.
>
> **When to be in this doc:** You have a specific project or direction. You are ready to define it completely before handing it to an agent. If you can't fill in a field, that is an unresolved decision — resolve it here, not mid-run.
>
> **Solo operator shortcut:** Instead of filling this manually, use the Self-Spec Agent prompt in the Quick Reference to generate a draft, then review and approve it here.

---

> Fill in every field before handing to an agent. A blank field is an unresolved decision — resolve it here, not mid-run.
> *Based on the FORGE*

---

## 0. Pre-Flight Decisions
> These must be set first. Everything else is built on top of them.

**Risk Tier:** [ ] Low  [ ] Medium  [ ] High
*(If unsure, go one tier higher)*

**Primary Cognitive Mode for this project:**
[ ] Deterministic  [ ] Exploratory  [ ] Adversarial  [ ] Synthesis  [ ] Audit
[ ] Multi-phase — using Divergence → Convergence Loop (see Section 6)
*→ Unsure which mode? See Cognitive Mode table in Quick Reference or Canonical doc.*

**Resource Governance:**
- Model tier (Planner): `_______________`
- Model tier (Workers): `_______________`
- Max runtime per sub-task: `_______________`
- Total compute / cost budget: `_______________`
- Retry limit before escalation: `_______________`
- Cost threshold that triggers stop-and-report: `_______________`

---

## 1. Specification Layer — The Blueprint

### 1.1 Final Deliverable
*Describe precisely. Not "a good analysis" — describe the exact artifact, format, and measurable quality.*

```
Deliverable: _______________________________________________

Format: ___________________________________________________

Length / Size: _____________________________________________

Measurable quality bar: ____________________________________
```

### 1.2 Scope Boundaries
*Be explicit. Ambiguity here becomes scope creep mid-run.*

**In scope:**
- `_______________`
- `_______________`
- `_______________`

**Out of scope (Must-Not):**
- `_______________`
- `_______________`
- `_______________`

### 1.3 Task Decomposition
*Break the project into sub-tasks. Each must satisfy the 5 Primitives and complete in under 2 hours.*
*→ Need a reminder of the 5 Primitives? See Quick Reference or Canonical doc Section "5 Primitives."*

| # | Sub-task | Cognitive Mode | Risk Tier | Acceptance Criteria | Eval Method |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

*Add rows as needed. Every sub-task needs all five columns filled.*

*Note: Sub-task risk tiers may differ from the overall project tier. A research sub-task and a production deployment sub-task in the same project have different risk profiles — assign each independently. The project-level tier sets the floor for escalation; sub-task tiers govern validation routing.*

### 1.4 Acceptance Criteria — Master Definition of Done
*Binary. Measurable. No subjective criteria.*

The project is complete when ALL of the following are true:
- [ ] `_______________`
- [ ] `_______________`
- [ ] `_______________`

---

## 2. Intent Layer — The Compass

### 2.1 Agent Deployment Purpose
*Tell the agent what it is, what it is not, and who consumes its output. One clear paragraph.*

```
You are: ___________________________________________________

You are NOT responsible for: _______________________________

Your output is consumed by: ________________________________
  (human decision-maker / another agent / automated pipeline)

Your output feeds into: ____________________________________
```

### 2.2 Trade-off Hierarchy
*Rank these in order of priority. The agent will use this when it hits a fork.*

Rank the following from 1 (highest) to n (lowest) for this task:

| Priority | Value |
|---|---|
| `___` | Accuracy / Correctness |
| `___` | Speed / Efficiency |
| `___` | Cost / Token economy |
| `___` | Safety / Risk avoidance |
| `___` | Novelty / Creativity |
| `___` | Completeness |
| `___` | Simplicity / Readability |
| `___` | *(add domain-specific value)* |

### 2.3 Constraint Architecture

**Must (non-negotiable requirements):**
- `_______________`
- `_______________`

**Must-Not (hard prohibitions):**
- `_______________`
- `_______________`

**Prefer (soft preferences when trade-offs arise):**
- `_______________`
- `_______________`

**Escalate (stop and surface to human when):**
- `_______________`
- `_______________`

### 2.4 Forbidden Approaches
*Specific methods, tools, frameworks, or reasoning patterns to avoid.*

- `_______________`
- `_______________`

---

## 3. Context Layer — The Environment

### 3.1 Provided Context
*List all documents, artifacts, or data sources being provided. Mark each as AUTHORITATIVE or REFERENCE.*

| Source | Type | Authority Level | Notes |
|---|---|---|---|
| | | AUTHORITATIVE / REFERENCE | |
| | | AUTHORITATIVE / REFERENCE | |
| | | AUTHORITATIVE / REFERENCE | |

### 3.2 Known State
*What has already been tried? What failed? What is known?*

```
Prior attempts: ____________________________________________

Known failures / dead ends: ________________________________

Known constraints: _________________________________________

Current blockers: __________________________________________
```

### 3.3 Context Freshness
*Tell the agent when to trust the provided context vs. when to re-fetch or verify.*

[ ] All provided context is current — use as ground truth
[ ] The following sources may be stale and should be verified: `_______________`
[ ] The agent must re-fetch live data for: `_______________`
[ ] MCP connections available: `_______________`

### 3.4 Domain Conventions
*Terminology, style, standards, or norms the agent must match.*

```
Terminology to use: ________________________________________

Terminology to avoid: ______________________________________

Style / format standards: __________________________________

Domain-specific conventions: _______________________________
```

---

## 4. Prompt Layer — The Trigger

### 4.1 Opening System Instruction
*The master instruction that frames the entire run. Reference Sections 1–3 explicitly.*

```
You are [deployment purpose from 2.1].

Your task is to produce [deliverable from 1.1].

You are operating within the following constraints: [from 2.3].

Your trade-off priority order is: [from 2.2].

The context you have been provided is: [from 3.1].

You will complete this task by executing the following sub-tasks in order: [from 1.3].

For each sub-task, your completion criterion is: [from 1.4].
```

### 4.2 Per-Sub-Task Prompt Template
*Use this template for each sub-task trigger.*

```
Sub-task [#]: [name]
Cognitive mode: [mode]
Your input: [what you're working from]
Your output: [exact format and content required]
Acceptance criteria: [binary criteria from 1.3]
Evaluation: [how this will be checked]
Resource cap: [max runtime / tokens for this sub-task]
```

---

## 5. Governance & Validation

### 5.1 Escalation Contract

**Escalation triggers** *(from 2.3 — repeated here for executor clarity)*:
- `_______________`
- `_______________`

**Who reviews escalations:**
```
Name / Role: _______________________________________________
Contact: __________________________________________________
Response SLA: ______________________________________________
```

**If no response arrives within SLA, the agent should:**
[ ] Hold and wait
[ ] Attempt alternative path: `_______________`
[ ] Abort and report

### 5.2 Adversarial Reflection Trigger
*(Required for Medium and High risk tasks)*

[ ] Not required (Low risk)
[ ] Required after sub-task(s): `_______________`
[ ] Required before final delivery

The agent should critique: `_______________`
The revision threshold is: `_______________` *(what level of critique warrants a revision?)*

### 5.3 Uncertainty Reporting
*(Required for non-deterministic domains)*

[ ] Not required
[ ] Required — agent must report:
  - Confidence estimate (0–100%) with justification
  - Primary uncertainty drivers
  - What data would most reduce uncertainty
  - Alternative plausible interpretations

---

## 6. Brainstorming Mode (Divergence → Convergence)
*Complete this section only if primary mode is multi-phase brainstorming.*

**Phase 1 — DIVERGE (Exploratory Mode)**
```
Generate: _________________________________________________
Constraint: No filtering or judgment at this stage.
Output format: ____________________________________________
Volume target: ____________________________________________
```

**Phase 2 — CLUSTER (Synthesis Mode)**
```
Organize the output of Phase 1 by: ________________________
Identify: _________________________________________________
Output format: ____________________________________________
```

**Phase 3 — STRESS-TEST (Adversarial Mode)**
```
Attack the top [n] candidates from Phase 2.
Criteria to stress-test against: __________________________
Output format: ____________________________________________
What constitutes a fatal flaw: ____________________________
```

**Phase 4 — FORMALIZE (Deterministic Mode)**
```
Selected direction: ______________________________________
Formalize as: ____________________________________________
Acceptance criteria: _____________________________________
```

---

## 7. Domain-Specific Additions

### If Coding:
- Language / framework / version: `_______________`
- Performance targets: `_______________`
- API / interface contracts: `_______________`
- Security requirements: `_______________`
- Test coverage expectation: `_______________`

### If Science / Research:
- Null hypothesis: `_______________`
- Falsification criteria: `_______________`
- Authorized data sources: `_______________`
- Forbidden data sources: `_______________`
- Statistical significance threshold: `_______________`
- Correction method: `_______________`
- Reproducibility requirements: `_______________`

### If Writing / Content:
- Audience: `_______________`
- Purpose: `_______________`
- Structure: `_______________`
- Word count / length: `_______________`
- Style reference: `_______________`
- Mandatory inclusions: `_______________`
- Mandatory exclusions: `_______________`

### If Business / Strategy:
- Decision-maker: `_______________`
- Decision to be made: `_______________`
- Options to evaluate: `_______________`
- Recommendation format: `_______________`
- Regulatory Must-Nots: `_______________`
- Stakeholder sensitivities: `_______________`

---

## 8. Spec Validation (Red-Team Checklist)
*Complete before handing to the agent. Every unchecked box is a known risk.*

**5 Primitives — does every sub-task have:**
- [ ] A self-contained problem statement (zero questions needed to start)
- [ ] A Constraint Architecture (Must / Must-Not / Prefer / Escalate)
- [ ] A runtime under 2 hours
- [ ] Binary acceptance criteria
- [ ] A built-in evaluation method

**Failure Mode Taxonomy — does this spec prevent:**
- [ ] Scope Creep — explicit Must-Not list and scope boundaries
- [ ] Hallucinated Completion — binary acceptance criteria defined
- [ ] Intent Drift — ranked trade-offs and deployment purpose explicit
- [ ] Context Collapse — context curated; noise removed
- [ ] Runaway Cost — resource caps set before decomposition
- [ ] Overconfident Output — uncertainty reporting required (if applicable)

**Final gate:**
- [ ] Risk tier and resource governance set *before* decomposition
- [ ] Every agent has a deployment purpose statement
- [ ] Escalation contract complete (who, when, SLA, no-response behavior)
- [ ] Planner execution plan will be saved as artifact

---

*FORGE Spec Template v1.0 — companion to the FORGE system. A blank field is an unresolved decision.*
*System docs: Quick Reference · Canonical Framework · Spec Template (this doc)*
