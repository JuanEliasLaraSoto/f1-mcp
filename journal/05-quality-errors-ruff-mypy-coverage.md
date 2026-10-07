# Quality: friendly errors, ruff, strict mypy and coverage

**Date:** 2026-10-07

## Friendly errors

When OpenF1 failed (timeout, no network, persistent 429, 5xx) the tool raised an httpx
exception and the model received a technical error. Now `openf1.get` turns every failure
into an `OpenF1Error` with a readable message, and the `friendly_errors` decorator
(`mcp/errors.py`) turns that into text the model can explain or retry on. A decorator
instead of a try/except per tool keeps error handling in one place. `functools.wraps`
preserves name, docstring and signature, so the MCP schema is unchanged (verified).

## Quality tooling

- **ruff** (lint + format), rules E, F, I, UP, B. E501 ignored in prompts (prose) and in
  tests (inline test data).
- **Strict mypy** on `src/`. Passed without code changes: types were annotated from the
  start. The decorator uses PEP 695 generics (`[**P]`) to preserve the wrapped signature.
- **pytest-cov** with `fail_under = 80`. `__init__.py` is excluded (it only starts the server).
- **pre-commit** (hygiene hooks, ruff, mypy) and **GitHub Actions** CI (tests with coverage;
  ruff + mypy), plus Dependabot.

## Coverage

First measurement: 79 %, with `laps.py` at 26 % (its three tools had no tests). After adding
tests built on synthetic data with known properties, plus tests through the MCP protocol
(all 8 tools registered with a description, end-to-end calls): **95 %**, 32 tests.
