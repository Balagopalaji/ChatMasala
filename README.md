# ChatMasala

ChatMasala is a minimal local orchestration tool for two CLI AI agents.

The MVP goal is simple: you provide one task and one plan, the app relays work between a `builder` agent and a `reviewer` agent so you do not have to copy/paste between them.

This repository is optimized for AI agents building the product. The active source of truth is:

- `docs/mvp-build-spec.md`

Archived broader design material lives here and is not the current scope:

- `docs/archive/2026-03-16/`

## Current Product Boundary

Build only the narrow MVP:

- single-user
- local machine only
- two CLI agents only
- one workflow: `builder -> reviewer -> builder`
- deterministic routing
- transcript and basic controls

Do not add:

- generalized multi-agent graphs
- policy-pack framework
- plugin marketplace abstractions
- complex metrics
- embedded terminal UI
- cloud/multi-user features

If a future agent finds an attractive idea in the archive, it should not pull it into the MVP unless the active spec is updated first.
