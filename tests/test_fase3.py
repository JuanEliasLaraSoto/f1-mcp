import httpx
import respx

from f1_mcp.analysis import strategy_label
from f1_mcp.openf1 import BASE_URL
from f1_mcp.server import fmt_duration, fmt_gap, get_results, list_sessions, race_strategy

SESSIONS = [
    {"session_key": 1, "session_name": "Race", "date_start": "2025-05-18T13:00:00+00:00",
     "country_name": "Italy", "circuit_short_name": "Imola"},
    {"session_key": 2, "session_name": "Race", "date_start": "2025-09-07T13:00:00+00:00",
     "country_name": "Italy", "circuit_short_name": "Monza"},
]
DRIVERS = [
    {"driver_number": 16, "name_acronym": "LEC", "team_name": "Ferrari"},
    {"driver_number": 44, "name_acronym": "HAM", "team_name": "Ferrari"},
]


def test_strategy_label_ordena_por_stint() -> None:
    stints = [
        {"stint_number": 2, "compound": "HARD"},
        {"stint_number": 1, "compound": "MEDIUM"},
    ]
    assert strategy_label(stints) == "MEDIUM → HARD"


def test_formatos_de_tiempo_y_gap() -> None:
    assert fmt_duration(4815.5) == "1:20:15.500"
    assert fmt_duration([80.1, 79.5, None]) == "1:19.500"
    assert fmt_gap(0) == "líder"
    assert fmt_gap(1.2345) == "+1.234 s" or fmt_gap(1.2345) == "+1.235 s"
    assert fmt_gap("+1 LAP") == "+1 LAP"


@respx.mock
async def test_list_sessions_filtra_por_circuito() -> None:
    respx.get(f"{BASE_URL}/sessions").mock(return_value=httpx.Response(200, json=SESSIONS))

    output = await list_sessions(2025, "Italy", circuit="monza")

    assert "Monza" in output
    assert "Imola" not in output


@respx.mock
async def test_get_results_ordena_y_marca_abandonos() -> None:
    respx.get(f"{BASE_URL}/session_result").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"driver_number": 44, "position": None, "number_of_laps": 30,
                 "duration": None, "gap_to_leader": None, "dnf": True, "dns": False, "dsq": False},
                {"driver_number": 16, "position": 1, "number_of_laps": 53,
                 "duration": 4815.5, "gap_to_leader": 0, "dnf": False, "dns": False, "dsq": False},
            ],
        )
    )
    respx.get(f"{BASE_URL}/drivers").mock(return_value=httpx.Response(200, json=DRIVERS))

    lines = (await get_results(2)).splitlines()

    assert lines[0].startswith("P1") and "LEC" in lines[0] and "líder" in lines[0]
    assert "HAM" in lines[1] and "DNF" in lines[1]


@respx.mock
async def test_race_strategy_resume_estrategias() -> None:
    stints = [
        {"driver_number": 16, "stint_number": 1, "compound": "MEDIUM", "lap_start": 1, "lap_end": 20},
        {"driver_number": 16, "stint_number": 2, "compound": "HARD", "lap_start": 21, "lap_end": 53},
        {"driver_number": 44, "stint_number": 1, "compound": "MEDIUM", "lap_start": 1, "lap_end": 25},
        {"driver_number": 44, "stint_number": 2, "compound": "HARD", "lap_start": 26, "lap_end": 53},
    ]
    pits = [
        {"driver_number": 16, "lap_number": 20, "stop_duration": 2.3},
        {"driver_number": 44, "lap_number": 25, "stop_duration": 2.9},
    ]
    results = [{"driver_number": 16, "position": 1}, {"driver_number": 44, "position": 2}]
    respx.get(f"{BASE_URL}/stints").mock(return_value=httpx.Response(200, json=stints))
    respx.get(f"{BASE_URL}/pit").mock(return_value=httpx.Response(200, json=pits))
    respx.get(f"{BASE_URL}/session_result").mock(return_value=httpx.Response(200, json=results))
    respx.get(f"{BASE_URL}/drivers").mock(return_value=httpx.Response(200, json=DRIVERS))

    output = await race_strategy(2)

    assert output.splitlines()[0].startswith("P1   LEC: MEDIUM (1-20) → HARD (21-53)")
    assert "2 piloto(s): MEDIUM → HARD" in output
    assert "Parada más rápida: LEC 2.3 s (vuelta 20)" in output
