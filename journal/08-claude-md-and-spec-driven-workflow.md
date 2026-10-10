# CLAUDE.md and a spec-driven workflow

**Date:** 2026-10-08

## Context
Claude Code reads `CLAUDE.md` at the start of every session as project instructions.
Without it, each session starts with no knowledge of the architecture, commands or rules.

## Decision
Add a short `CLAUDE.md` (well under 500 lines, so it does not crowd the context window)
that describes how to operate in the project: commands, module responsibilities, how to
add a tool, conventions. It does not explain how to write code.

Adopt spec-driven development: every new feature starts as a spec in `specs/` (goal,
inputs, outputs, edge cases, acceptance tests) that is approved before implementation.

## Consequences
- New sessions follow the same rules (no network in tests, maths in `analysis.py`, etc.).
- Specs become the reference for reviewing AI-generated code.
