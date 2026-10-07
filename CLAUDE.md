# f1-mcp

MCP server that exposes Formula 1 data from the OpenF1 API (https://api.openf1.org/v1)
to LLM clients: lap times, stints, pit stops, results, and derived analysis
(clean-lap pace, head-to-head, fuel-corrected degradation, detrended consistency).

## How to work in this project

- The owner (Juan) is learning AI engineering with this project and must be able to
  defend every decision in a technical interview. Before implementing a change, explain
  what will change, why, and the alternatives with their trade-offs. Wait for approval.
- Architecture decisions (libraries, transport, deployment, data model) are Juan's call.
  Present options neutrally. Implementation details (names, types, test structure) are
  yours; mention them in the summary afterwards.
- Spec first: for any new feature, write or update a spec in `specs/` (goal, inputs,
  outputs, edge cases, acceptance tests) and get it approved before writing code.
- Never invent F1 data. Every number must come from OpenF1 through the tools.
- Everything in English: code, docstrings, tool descriptions, README, journal.

## Commands

- Run the server: `uv run f1-mcp` (stdio transport)
- Try it without Claude: `uv run python scripts/try_client.py [TOOL '{json}' | resources | read URI | prompts | prompt NAME '{json}']`
- Tests: `uv run pytest --cov` (coverage must stay >= 80%)
- Lint and format: `uv run ruff check . --fix && uv run ruff format .`
- Types: `uv run mypy` (strict mode)
- All checks: `uv run pre-commit run --all-files`
- Dependencies: `uv add <pkg>` / `uv add --dev <pkg>`. Never use pip.

## Architecture (src/f1_mcp/)

- `config.py`: base URL, cache path, retry count.
- `openf1.py`: the ONLY module that talks to the network. `get(endpoint, **params)` with
  SQLite cache (empty responses are not cached), exponential backoff on 429, and
  `OpenF1Error` with user-readable messages.
- `analysis.py`: pure functions, no I/O. All the maths lives here.
- `formatting.py`: lap time, duration and gap formatting.
- `mcp/server.py`: creates `mcp_server`; imports prompts, resources and tools at the
  bottom to register them (avoids circular imports).
- `mcp/tools/*.py`: tools grouped by topic (sessions, laps, strategy).
- `mcp/resources.py`: `f1://sessions/{year}`, `f1://session/{session_key}/results` (JSON).
- `mcp/prompts.py`: `analyze_race`, `driver_duel`.
- `mcp/errors.py`: `@friendly_errors` turns `OpenF1Error` into a message for the model.

## Adding a tool

1. Write the spec in `specs/`.
2. Data fetching goes through `openf1.get`; maths goes in `analysis.py` as a pure function.
3. Add the tool in the right `mcp/tools/` module with `@mcp_server.tool()` and
   `@friendly_errors`. The docstring and type hints ARE the schema the model sees:
   say when to use the tool and what each argument means.
4. Tests: unit tests for the analysis with synthetic data of known properties, and a
   tool test with OpenF1 mocked by `respx`. Never hit the real API in tests; the autouse
   fixture in `tests/conftest.py` already isolates the cache.
5. Check it by hand with `scripts/try_client.py`.

## Conventions

- Python 3.12, full type hints, PEP 695 generics.
- Tools return readable text for the model; resources return JSON.
- Atomic commits: one change per commit. pre-commit runs ruff and mypy on each commit.
- Every important decision gets a numbered entry in `journal/` (`NN-title.md`), linked
  from `journal/README.md`, written when the decision is made.
- `README.md` is for a reviewer (what it is, how it works, setup), not the decision log.
