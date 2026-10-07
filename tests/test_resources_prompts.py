"""Resources y prompts probados a través del protocolo MCP real (cliente en memoria),
igual que los usaría Claude."""

import json

import httpx
import respx
from mcp.client._memory import InMemoryTransport
from mcp.client.session import ClientSession

from f1_mcp.openf1 import BASE_URL
from f1_mcp.mcp.server import mcp_server


async def test_resources_y_prompts_registrados() -> None:
    async with InMemoryTransport(mcp_server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            templates = await session.list_resource_templates()
            prompts = await session.list_prompts()

    uris = {t.uri_template for t in templates.resource_templates}
    assert uris == {"f1://sessions/{year}", "f1://session/{session_key}/results"}
    assert {p.name for p in prompts.prompts} == {"analizar_carrera", "comparar_pilotos"}


@respx.mock
async def test_leer_resource_de_resultados() -> None:
    respx.get(f"{BASE_URL}/session_result").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"driver_number": 4, "position": 2, "number_of_laps": 53, "gap_to_leader": 19.2},
                {"driver_number": 1, "position": 1, "number_of_laps": 53, "gap_to_leader": 0},
            ],
        )
    )
    respx.get(f"{BASE_URL}/drivers").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"driver_number": 1, "name_acronym": "VER", "team_name": "Red Bull Racing"},
                {"driver_number": 4, "name_acronym": "NOR", "team_name": "McLaren"},
            ],
        )
    )

    async with InMemoryTransport(mcp_server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.read_resource("f1://session/9912/results")

    data = json.loads(result.contents[0].text)
    assert data["session_key"] == 9912
    assert [r["driver"] for r in data["results"]] == ["VER", "NOR"]


async def test_prompt_comparar_pilotos_incluye_datos_y_tools() -> None:
    async with InMemoryTransport(mcp_server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.get_prompt(
                "comparar_pilotos",
                {"year": "2025", "circuit": "Monza", "piloto_a": "Leclerc", "piloto_b": "Hamilton"},
            )

    text = result.messages[0].content.text
    assert "Leclerc" in text and "Hamilton" in text and "2025" in text
    assert "compare_drivers" in text and "get_stints" in text
