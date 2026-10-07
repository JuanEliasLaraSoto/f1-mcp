import httpx
import respx

from f1_mcp import openf1
from f1_mcp.mcp.tools.sessions import list_drivers

URL = f"{openf1.BASE_URL}/drivers"


@respx.mock
async def test_timeout_devuelve_mensaje_claro() -> None:
    respx.get(URL).mock(side_effect=httpx.ConnectTimeout("timeout"))

    output = await list_drivers(9912)

    assert output.startswith("No he podido obtener los datos de OpenF1")
    assert "tardando demasiado" in output


@respx.mock
async def test_error_500_devuelve_mensaje_claro() -> None:
    respx.get(URL).mock(return_value=httpx.Response(500))

    output = await list_drivers(9912)

    assert "error 500" in output


@respx.mock
async def test_429_persistente_devuelve_mensaje_claro(monkeypatch) -> None:
    async def no_sleep(_: float) -> None:
        pass

    monkeypatch.setattr(openf1, "_sleep", no_sleep)
    route = respx.get(URL).mock(return_value=httpx.Response(429))

    output = await list_drivers(9912)

    assert "límite de peticiones" in output
    assert route.call_count == openf1.MAX_RETRIES
