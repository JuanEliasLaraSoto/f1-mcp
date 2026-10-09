# Spec: remote deployment

## Goal
f1-mcp reachable at a public HTTPS URL so any MCP client can connect without
installing anything, deployed automatically when CI passes.

## Requirements
- Same codebase runs in stdio (default) or streamable HTTP, chosen by env vars:
  F1_MCP_TRANSPORT (stdio | http), F1_MCP_HOST, F1_MCP_PORT.
- HTTP mode is stateless and serves MCP at /mcp.
- GET /health returns {"status": "ok"}.
- Runs in Docker; the SQLite cache lives in a volume.
- Caddy terminates HTTPS with an automatic certificate.
- GitHub Actions deploys over SSH only after tests and lint pass, then checks /health.

## Decisions to defend
- No auth: public F1 data. Risk: abuse exhausting OpenF1's rate limit.
- VPS + Docker instead of a PaaS: cheaper, shows Linux, Docker and CI/CD.

## Acceptance
- Locally: F1_MCP_TRANSPORT=http uv run f1-mcp, then curl /health returns ok.
- A test checks /health and tools/list over HTTP.
- Production: claude mcp add --transport http f1-mcp https://DOMAIN/mcp works.
