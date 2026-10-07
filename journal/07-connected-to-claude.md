# Connected to Claude: first real conversation

**Date:** 2026-10-08

## Setup

The server is registered in Claude Code running inside WSL, the same environment as the
project, with `claude mcp add f1-mcp -- uv run --directory "$(pwd)" f1-mcp`. A first attempt
used the Windows Claude Code binary picked up from WSL's PATH, which tried to launch the
server on Windows and failed; logging in to the WSL install from Windows Terminal solved it.

## What the conversation showed

Asked who was faster at Monza 2025 (Leclerc or Hamilton), Claude called the tools six times
on its own, including qualifying (session 9908), which it was not asked for.

- **The residual-based consistency works on real data**: σ = 0.215 s (LEC) and 0.256 s (HAM),
  versus ~1.1 s for the raw standard deviation (see entry 01). The detrended figure is in
  the range expected for F1 race pace.
- **The model reasons about which number to trust**: it discarded the median gap (0.335 s)
  as inflated by different pit-stop timing and preferred the same-lap duel (0.179 s/lap),
  the criterion stated in the tool's output.

## Finding: ungrounded claims

The answer ended with a claim not present in any tool output (a grid penalty for Hamilton),
introduced with "as far as I recall". The model hedged it, but it is exactly the kind of
ungrounded statement evals should catch: answers must be backed by tool results. It was left
out of the README example. Next step: an eval set that checks tool selection and grounding.
