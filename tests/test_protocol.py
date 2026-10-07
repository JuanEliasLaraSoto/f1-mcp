"""Tools a través del protocolo MCP real: registro y una llamada de extremo a extremo."""

import httpx
import respx
from mcp.client._memory import InMemoryTransport
from mcp.client.session import ClientSession

from f1_mcp.mcp.server import mcp_server
from f1_mcp.openf1 import BASE_URL

TOOLS = {
    "ping",
    "list_sessions",
    "list_drivers",
    "get_laps",
    "compare_drivers",
    "get_stints",
    "get_results",
    "race_strategy",
}


async def test_todas_las_tools_registradas_con_descripcion() -> None:
    async with InMemoryTransport(mcp_server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()

    assert {t.name for t in tools.tools} == TOOLS
    for tool in tools.tools:
        assert tool.description, f"{tool.name} no tiene descripción"


async def test_ping_por_protocolo() -> None:
    async with InMemoryTransport(mcp_server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("ping", {})

    assert not result.is_error
    assert result.content[0].text == "pong"


@respx.mock
async def test_list_drivers_por_protocolo() -> None:
    respx.get(f"{BASE_URL}/drivers").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "driver_number": 14,
                    "full_name": "Fernando ALONSO",
                    "name_acronym": "ALO",
                    "team_name": "Aston Martin",
                }
            ],
        )
    )

    async with InMemoryTransport(mcp_server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("list_drivers", {"session_key": 9912})

    assert result.content[0].text == "#14 Fernando ALONSO (ALO) — Aston Martin"


@respx.mock
async def test_leer_resource_de_sesiones() -> None:
    respx.get(f"{BASE_URL}/sessions").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "session_key": 9912,
                    "session_name": "Race",
                    "circuit_short_name": "Monza",
                    "country_name": "Italy",
                    "date_start": "2025-09-07T13:00:00+00:00",
                }
            ],
        )
    )

    async with InMemoryTransport(mcp_server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.read_resource("f1://sessions/2025")

    assert '"circuit": "Monza"' in result.contents[0].text
