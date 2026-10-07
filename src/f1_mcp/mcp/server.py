import logging

from mcp.server.mcpserver import MCPServer

# httpx logs every request; silence it so it does not clutter the output
logging.getLogger("httpx").setLevel(logging.WARNING)

mcp_server = MCPServer("f1-mcp")


@mcp_server.tool()
def ping() -> str:
    """Health check: confirms the server is up and tools can be called."""
    return "pong"


# Importing these modules registers their tools, resources and prompts. This goes
# at the bottom because they all import mcp_server from this file: it must exist first.
from f1_mcp.mcp import prompts, resources  # noqa: E402, F401
from f1_mcp.mcp.tools import laps, sessions, strategy  # noqa: E402, F401
