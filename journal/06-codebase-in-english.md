# Codebase in English

**Date:** 2026-10-07

## Decision

Translate the whole codebase to English: docstrings, comments, tool output, error
messages, prompt names (`analizar_carrera` → `analyze_race`, `comparar_pilotos` →
`driver_duel`) and the test client (`probar_cliente.py` → `try_client.py`).

## Why

- The repository is a portfolio piece for an international audience; README and journal
  were already in English.
- Docstrings are not just documentation here: they are what the model reads to decide which
  tool to call and how to fill its arguments. Keeping them in the same language as the rest
  of the tool descriptions in a typical MCP host avoids mixing languages in the context.

## Verification

Language-only change, no logic touched: the same 32 tests pass (with their expected strings
translated), coverage stays at 95 %, and ruff and strict mypy are clean. The cache keys are
unchanged, so existing cached responses remain valid.
