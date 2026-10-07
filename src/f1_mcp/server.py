from mcp.server.mcpserver import MCPServer

from f1_mcp import openf1

mcp_server = MCPServer("f1-mcp")


@mcp_server.tool()
def ping() -> str:
    """Health-check: confirma que el servidor responde."""
    return "pong"


@mcp_server.tool()
async def list_sessions(year: int, country: str | None = None) -> str:
    """Lista las sesiones de F1 (FP1, Qualifying, Race...) de un año, opcionalmente
    filtradas por país en inglés (p. ej. 'Italy'). Cada sesión incluye su session_key,
    que usan el resto de tools."""
    sessions = await openf1.get("sessions", year=year, country_name=country)
    if not sessions:
        return f"No hay sesiones para {year}" + (f" en {country}." if country else ".")
    return "\n".join(
        f"{s['date_start'][:10]} | {s['country_name']} ({s['circuit_short_name']}) | "
        f"{s['session_name']} | session_key: {s['session_key']}"
        for s in sessions
    )
