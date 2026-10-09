# Resources and prompts: the other two MCP primitives

**Date:** 2026-10-07

## Rule of thumb: tool, resource or prompt?

- **Tool**: chosen by the model, usually computes something from arguments
  (`compare_drivers`, `race_strategy`). Returns text meant for the model to interpret.
- **Resource**: read-only data with a URI that the host or the user attaches to the
  context, like a document. Returns JSON. `f1://sessions/{year}` and
  `f1://session/{session_key}/results`.
- **Prompt**: a template picked by the user. It packages domain knowledge: which tools to
  chain and what criteria to apply when concluding. `analyze_race`, `driver_duel`.

## Decisions

- Resources return JSON rather than tables: their consumer is a machine or the context,
  not a human reading it directly.
- `driver_duel` explicitly asks the model to separate raw pace from the final result.
  Real motivation: at Monza 2025 NOR finished P2 after a 5.9 s stop versus PIA's 1.9 s; the
  result does not reflect pace alone.
- Modules are registered by importing them at the bottom of the server module, after
  `mcp_server` exists, which avoids a circular import.

## Verification

Tested through a real in-memory MCP client/server session: resources and prompts are
registered, the results resource can be read (mocked data) and the prompt contains the
expected arguments and tool names.
