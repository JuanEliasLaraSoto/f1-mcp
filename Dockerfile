FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev
ENV F1_MCP_TRANSPORT=http F1_MCP_HOST=0.0.0.0 F1_MCP_PORT=8000
EXPOSE 8000
CMD ["/app/.venv/bin/f1-mcp"]
