"""Lap tools (get_laps, compare_drivers, get_stints) on synthetic data."""

import httpx
import respx

from f1_mcp.mcp.tools.laps import compare_drivers, get_laps, get_stints
from f1_mcp.openf1 import BASE_URL

DRIVERS = [
    {
        "driver_number": 16,
        "name_acronym": "LEC",
        "full_name": "Charles LECLERC",
        "team_name": "Ferrari",
    },
    {
        "driver_number": 44,
        "name_acronym": "HAM",
        "full_name": "Lewis HAMILTON",
        "team_name": "Ferrari",
    },
]


def make_laps(driver: int, base: float, n: int = 20) -> list[dict]:
    """Slow lap 1 (standing start), a pit-out lap 11, and the rest getting
    0.05 s/lap faster (fuel burn) with alternating ±0.1 s noise."""
    laps = []
    for lap in range(1, n + 1):
        t = base - 0.05 * lap + 0.1 * (-1) ** lap
        if lap == 1:
            t += 5
        laps.append(
            {
                "driver_number": driver,
                "lap_number": lap,
                "lap_duration": round(t, 3),
                "is_pit_out_lap": lap == 11,
                "duration_sector_1": 26.1,
                "duration_sector_2": 30.2,
                "duration_sector_3": 25.3,
            }
        )
    return laps


def make_stints(driver: int) -> list[dict]:
    return [
        {
            "driver_number": driver,
            "stint_number": 1,
            "compound": "MEDIUM",
            "lap_start": 1,
            "lap_end": 10,
            "tyre_age_at_start": 0,
        },
        {
            "driver_number": driver,
            "stint_number": 2,
            "compound": "HARD",
            "lap_start": 11,
            "lap_end": 20,
            "tyre_age_at_start": 0,
        },
    ]


@respx.mock
async def test_get_laps_table_and_fastest_lap() -> None:
    respx.get(f"{BASE_URL}/laps").mock(return_value=httpx.Response(200, json=make_laps(16, 83.0)))

    output = await get_laps(9912, 16)

    lines = output.splitlines()
    assert lines[0].startswith("Lap | Time")
    assert "pit out" in lines[11]  # lap 11
    assert "Fastest lap: 1:21.950" in output  # lap 19: 83 - 0.95 - 0.1
    assert "Timed laps: 20" in output


@respx.mock
async def test_get_laps_no_data() -> None:
    respx.get(f"{BASE_URL}/laps").mock(return_value=httpx.Response(404))

    assert await get_laps(9912, 99) == "No laps found for driver #99 in session 9912."


@respx.mock
async def test_compare_drivers_finds_the_faster_driver() -> None:
    laps = make_laps(16, 83.0) + make_laps(44, 83.3)  # HAM 0.3 s/lap slower
    respx.get(f"{BASE_URL}/laps").mock(return_value=httpx.Response(200, json=laps))
    respx.get(f"{BASE_URL}/stints").mock(
        return_value=httpx.Response(200, json=make_stints(16) + make_stints(44))
    )
    respx.get(f"{BASE_URL}/drivers").mock(return_value=httpx.Response(200, json=DRIVERS))

    output = await compare_drivers(9912, 16, 44)

    assert "LEC is 0.300 s/lap faster than HAM" in output
    assert "18 comparable laps): LEC faster in 18" in output  # no lap 1 or 11
    assert "Consistency σ (s)" in output


@respx.mock
async def test_compare_drivers_without_laps() -> None:
    respx.get(f"{BASE_URL}/laps").mock(return_value=httpx.Response(200, json=make_laps(16, 83.0)))
    respx.get(f"{BASE_URL}/stints").mock(return_value=httpx.Response(404))
    respx.get(f"{BASE_URL}/drivers").mock(return_value=httpx.Response(200, json=DRIVERS))

    output = await compare_drivers(9912, 16, 44)

    assert output == "Not enough laps to compare LEC and HAM in session 9912."


@respx.mock
async def test_get_stints_compounds_and_degradation() -> None:
    respx.get(f"{BASE_URL}/stints").mock(return_value=httpx.Response(200, json=make_stints(16)))
    respx.get(f"{BASE_URL}/laps").mock(return_value=httpx.Response(200, json=make_laps(16, 83.0)))

    output = await get_stints(9912, 16)

    assert "Stint 1: MEDIUM | laps 1-10 (10)" in output
    assert "Stint 2: HARD | laps 11-20 (10)" in output
    # The data improves 0.05 s/lap: observed slope ≈ -0.05, corrected ≈ +0.005
    assert "Observed degradation: -0.0" in output
    assert "fuel correction is an approximation" in output


@respx.mock
async def test_get_stints_no_data() -> None:
    respx.get(f"{BASE_URL}/stints").mock(return_value=httpx.Response(404))
    respx.get(f"{BASE_URL}/laps").mock(return_value=httpx.Response(404))

    assert await get_stints(9912, 16) == "No stints found for driver #16 in session 9912."
