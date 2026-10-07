"""Tools de vueltas (get_laps, compare_drivers, get_stints) con datos sintéticos."""

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
    """Vuelta 1 lenta (salida), vuelta 11 de salida de boxes y el resto con una
    mejora de 0.05 s/vuelta (combustible) y un ruido alterno de ±0.1 s."""
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
async def test_get_laps_tabla_y_vuelta_rapida() -> None:
    respx.get(f"{BASE_URL}/laps").mock(return_value=httpx.Response(200, json=make_laps(16, 83.0)))

    output = await get_laps(9912, 16)

    lines = output.splitlines()
    assert lines[0].startswith("Vuelta | Tiempo")
    assert "pit out" in lines[11]  # vuelta 11
    assert "Vuelta rápida: 1:21.950" in output  # vuelta 19: 83 - 0.95 - 0.1
    assert "Vueltas con tiempo: 20" in output


@respx.mock
async def test_get_laps_sin_datos() -> None:
    respx.get(f"{BASE_URL}/laps").mock(return_value=httpx.Response(404))

    assert await get_laps(9912, 99) == "No hay vueltas del piloto #99 en la sesión 9912."


@respx.mock
async def test_compare_drivers_detecta_al_mas_rapido() -> None:
    laps = make_laps(16, 83.0) + make_laps(44, 83.3)  # HAM 0.3 s/vuelta más lento
    respx.get(f"{BASE_URL}/laps").mock(return_value=httpx.Response(200, json=laps))
    respx.get(f"{BASE_URL}/stints").mock(
        return_value=httpx.Response(200, json=make_stints(16) + make_stints(44))
    )
    respx.get(f"{BASE_URL}/drivers").mock(return_value=httpx.Response(200, json=DRIVERS))

    output = await compare_drivers(9912, 16, 44)

    assert "LEC es 0.300 s/vuelta más rápido que HAM" in output
    assert "18 vueltas comparables): LEC más rápido en 18" in output  # sin vuelta 1 ni 11
    assert "Consistencia σ (s)" in output


@respx.mock
async def test_compare_drivers_sin_vueltas() -> None:
    respx.get(f"{BASE_URL}/laps").mock(return_value=httpx.Response(200, json=make_laps(16, 83.0)))
    respx.get(f"{BASE_URL}/stints").mock(return_value=httpx.Response(404))
    respx.get(f"{BASE_URL}/drivers").mock(return_value=httpx.Response(200, json=DRIVERS))

    output = await compare_drivers(9912, 16, 44)

    assert output == "No hay vueltas suficientes para comparar a LEC y HAM en la sesión 9912."


@respx.mock
async def test_get_stints_compuestos_y_degradacion() -> None:
    respx.get(f"{BASE_URL}/stints").mock(return_value=httpx.Response(200, json=make_stints(16)))
    respx.get(f"{BASE_URL}/laps").mock(return_value=httpx.Response(200, json=make_laps(16, 83.0)))

    output = await get_stints(9912, 16)

    assert "Stint 1: MEDIUM | vueltas 1-10 (10)" in output
    assert "Stint 2: HARD | vueltas 11-20 (10)" in output
    # Los datos mejoran 0.05 s/vuelta: pendiente observada ≈ -0.05, corregida ≈ +0.005
    assert "Degradación observada: -0.0" in output
    assert "corrección de combustible aproximada" in output


@respx.mock
async def test_get_stints_sin_datos() -> None:
    respx.get(f"{BASE_URL}/stints").mock(return_value=httpx.Response(404))
    respx.get(f"{BASE_URL}/laps").mock(return_value=httpx.Response(404))

    assert await get_stints(9912, 16) == "No hay stints del piloto #16 en la sesión 9912."
