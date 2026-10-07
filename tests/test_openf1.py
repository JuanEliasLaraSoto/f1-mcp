import httpx
import respx

from f1_mcp import openf1

URL = f"{openf1.BASE_URL}/drivers"
DATA = [{"driver_number": 16, "name_acronym": "LEC"}]


@respx.mock
async def test_second_call_comes_from_cache() -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, json=DATA))

    first = await openf1.get("drivers", session_key=9912)
    second = await openf1.get("drivers", session_key=9912)

    assert first == second == DATA
    assert route.call_count == 1  # the second call never hit the network


@respx.mock
async def test_retries_after_429(monkeypatch) -> None:
    async def no_sleep(_: float) -> None:
        pass

    monkeypatch.setattr(openf1, "_sleep", no_sleep)
    route = respx.get(URL).mock(side_effect=[httpx.Response(429), httpx.Response(200, json=DATA)])

    result = await openf1.get("drivers", session_key=9912)

    assert result == DATA
    assert route.call_count == 2


@respx.mock
async def test_empty_responses_are_not_cached() -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(404))

    await openf1.get("drivers", session_key=1)
    await openf1.get("drivers", session_key=1)

    assert route.call_count == 2
