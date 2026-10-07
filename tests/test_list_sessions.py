import httpx
import respx

from f1_mcp.mcp.tools.sessions import list_sessions
from f1_mcp.openf1 import BASE_URL


@respx.mock
async def test_list_sessions_includes_session_key() -> None:
    # respx intercepta la llamada a OpenF1 y devuelve esto en vez de ir a internet
    respx.get(f"{BASE_URL}/sessions").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "session_key": 1234,
                    "session_name": "Race",
                    "date_start": "2025-09-07T13:00:00+00:00",
                    "country_name": "Italy",
                    "circuit_short_name": "Monza",
                }
            ],
        )
    )

    output = await list_sessions(2025, "Italy")

    assert "session_key: 1234" in output
    assert "Race" in output


@respx.mock
async def test_list_sessions_without_results_returns_clear_message() -> None:
    respx.get(f"{BASE_URL}/sessions").mock(return_value=httpx.Response(404))

    output = await list_sessions(2025, "Narnia")

    assert output == "No sessions found for 2025 in Narnia."
