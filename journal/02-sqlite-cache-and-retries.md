# SQLite cache and retries on 429

**Date:** 2026-10-07

## Problem

OpenF1's free tier allows 3 requests/second and 30/minute. A single question to Claude can
chain several tools (list_sessions → list_drivers → compare_drivers → get_stints), each
making 1–3 requests, so a normal conversation hits the limit.

## Decision

- **SQLite cache** at `~/.cache/f1-mcp/openf1.sqlite`. Key = endpoint + parameters
  serialised with `sort_keys`, so parameter order does not matter. Past sessions never
  change, so entries never expire. Empty responses are not cached (a session may not have
  its data published yet).
- **`sqlite3` from the standard library**, no ORM: one key-value table does not justify one.
- Parameterised queries (`?`), never string formatting, to rule out SQL injection.
- **Retry on 429** with exponential backoff (1 s, 2 s), at most 3 attempts.

## Verification

- Two identical calls → `call_count == 1` on the respx mock.
- A 429 followed by a 200 → correct result after 2 calls.
- Empty (404) responses are requested again rather than cached.
- Tests use a temporary cache (`conftest.py`) so they never depend on the real one.
- Manually, a repeated `compare_drivers` is served from the cache without touching the network.
