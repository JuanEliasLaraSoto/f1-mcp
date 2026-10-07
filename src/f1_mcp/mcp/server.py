import logging

from mcp.server.mcpserver import MCPServer

# httpx loguea cada petición; lo silenciamos para que no ensucie la salida
logging.getLogger("httpx").setLevel(logging.WARNING)

mcp_server = MCPServer("f1-mcp")


@mcp_server.tool()
def ping() -> str:
    """Health-check: confirma que el servidor responde."""
    return "pong"


# Importar estos módulos registra sus tools, resources y prompts. Va al final
# porque todos importan mcp_server de este archivo: tiene que existir ya.
from f1_mcp.mcp import prompts, resources  # noqa: E402, F401
from f1_mcp.mcp.tools import laps, sessions, strategy  # noqa: E402, F401
