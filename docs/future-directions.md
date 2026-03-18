# ChatMasala Future Directions

> Product ideas intentionally deferred from the current build phases, but important enough to preserve as active direction.

## 1. Idea Revival

One of the strongest long-term product directions for ChatMasala is helping users revive unfinished ideas from past chat platforms and reroute them into new workflows.

The core concept:

- users have many valuable conversations trapped in ChatGPT, Claude, Gemini, and other tools
- many of those conversations contain half-finished ideas, abandoned outlines, research threads, design directions, and coding plans
- ChatMasala can become the place where those ideas are recovered, routed, refined, and reused

This is not implemented yet. It remains a future product pillar.

### Desired experience

- browse/search old conversations from external chat platforms
- pick one message, a short thread, or an extracted idea
- inject that material into a ChatMasala workspace node
- route it through agents such as Brainstorm, Critic, Decider, Planner, Writer, Builder, or Reviewer
- preserve provenance so users can see where the revived idea came from

### Phased approach

1. Manual import
- manual paste/import into a node
- preserve source label manually

2. File/export import
- import exported chat history files
- search and select messages from imported archives

3. Direct integrations
- browser extension
- MCP-based import
- direct connectors to supported chat/history sources

## 2. Integrations Direction

ChatMasala should evolve into a routing layer between existing tools, not a replacement for them.

Important future integration targets:

- RepoPrompt
- Figma
- ChatGPT history
- Claude history
- Gemini history
- Linear / Jira
- GitHub
- Notion / Obsidian

### Role of integrations

- import context into a workflow
- route work across specialized agents
- export back out where useful

Examples:

- Figma -> Spec -> Builder -> Reviewer
- Repo context -> RepoPrompt Crafter -> Builder
- old ChatGPT idea -> Brainstorm -> Critic -> Decider -> Planner

## 3. Human Control And Safety

ChatMasala needs stronger ways to keep agents from going rogue.

Future control features worth preserving:

- human approval gates
- pause-before-route controls
- route selection requiring human intervention
- diff review before downstream routing for coding flows
- explicit no-build / read-only agent modes
- richer audit trail of what each agent did

These ideas are related to the future `Human Gate`, `Router`, and `Scribe` node concepts.

## 4. Worktree Mode For Coding

For coding workflows, a future worktree-based isolation mode is promising.

Potential model:

- each coding node can run inside its own git worktree
- agents write only in that worktree
- diff is reviewed before merge or downstream routing
- bad runs can be discarded by deleting the worktree

This is a future enhancement, not part of the current pass.

## 5. Routing Evolution

The current model is intentionally narrow. Longer-term routing should likely support edge-based flow control.

Possible future edge types:

- output
- loop
- human_gate
- ai_route
- broadcast

Possible future conditions:

- GO
- NO_GO
- ALWAYS
- MANUAL

This would allow:

- multi-output routing
- conditional branching
- user-directed next steps
- AI-directed next steps
- parallel flows

## 6. Creative And Research Workflows

ChatMasala should not be thought of only as a coding tool.

High-potential non-coding workflow areas:

- brainstorming and concept development
- research synthesis
- writing books or long-form content
- product thinking and decision support
- design review and expansion
- repurposing abandoned ideas into new projects

The long-term identity is broader than "agent orchestration":

- a workspace where AI conversations become reusable material instead of dead ends

## 7. Status

Current status of these ideas:

- strategically important: yes
- implemented: no
- partially captured in `docs/build-plan.md`: yes
- fully specified: no

These should be revisited when planning the next major phase after the current agent and routing foundation is stable.
