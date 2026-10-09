import logging

from mcp.server.mcpserver import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse

# httpx logs every request; silence it so it does not clutter the output
logging.getLogger("httpx").setLevel(logging.WARNING)

mcp_server = MCPServer("f1-mcp")


@mcp_server.tool()
def ping() -> str:
    """Health check: confirms the server is up and tools can be called."""
    return "pong"


@mcp_server.custom_route("/health", methods=["GET"])  # type: ignore[untyped-decorator]
async def health(request: Request) -> JSONResponse:
    """Liveness probe for the reverse proxy and the deploy pipeline (HTTP mode only)."""
    return JSONResponse({"status": "ok"})


# Importing these modules registers their tools, resources and prompts. This goes
# at the bottom because they all import mcp_server from this file: it must exist first.
from f1_mcp.mcp import prompts, resources  # noqa: E402, F401
from f1_mcp.mcp.tools import laps, regulations, sessions, strategy  # noqa: E402, F401
