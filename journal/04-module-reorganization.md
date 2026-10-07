# Reorganising the code by responsibility

**Date:** 2026-10-07

## Problem

`server.py` had grown past 300 lines, mixing server creation, eight tools on different
topics and formatting helpers. Every new phase made it bigger.

## Decision

Split by responsibility, following the same layout as spotify-mcp:

- `config.py`: API URL, cache path and retries in one place.
- `formatting.py`: `fmt_time`, `fmt_duration`, `fmt_gap`.
- `analysis.py`: pure maths (gains `of_driver`).
- `mcp/server.py`: only creates the `MCPServer`, defines `ping` and imports the rest at the bottom.
- `mcp/tools/`: `sessions.py` (calendar, drivers, results), `laps.py` (laps, comparison,
  stints), `strategy.py` (race strategy).
- `mcp/resources.py`, `mcp/prompts.py`, and `scripts/` for the test client.

The code was moved with a small script based on Python's `ast` module (exact copy of each
function with its decorators) and `git mv`, so file history is preserved.

## Verification

A behaviour-preserving refactor: the same 19 tests pass before and after, and all 8 tools,
2 resources and 2 prompts are still registered.
