# Remote HTTP deployment

**Date:** 2026-10-09

## Context
With stdio, f1-mcp only works on the machine where it is installed. A public URL lets
any MCP client use it.

## Decision
- Transport chosen by env var: stdio stays the default; the container runs streamable
  HTTP, stateless, at /mcp, plus a public GET /health.
- Docker image built with uv from the lockfile; Caddy in front for automatic HTTPS;
  SQLite cache in a named volume.
- Hosted on an IONOS VPS (Ubuntu 24.04): non-root `deploy` user, key-only SSH,
  ufw allowing only 22/80/443. Free hostname via sslip.io.
- Gotcha: bound to 127.0.0.1 the SDK enables DNS-rebinding protection (421 for other
  Host headers), so the container binds 0.0.0.0 behind Caddy.
- mypy: the SDK's custom_route decorator is untyped; ignored on that line only.

## Consequences
- Live at https://217-154-7-81.sslip.io/mcp
- No auth (public data). Risk: abuse exhausting OpenF1's rate limit.
- Continuous deployment followed: a GitHub Actions job deploys over SSH only after tests
  and lint pass, then checks `/health` (see `.github/workflows/ci.yml`).
