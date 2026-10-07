"""Tools de calendario, pilotos y resultados de una sesión."""

import asyncio

from f1_mcp import openf1
from f1_mcp.formatting import fmt_duration, fmt_gap
from f1_mcp.mcp.errors import friendly_errors
from f1_mcp.mcp.server import mcp_server


@mcp_server.tool()
@friendly_errors
async def list_sessions(year: int, country: str | None = None, circuit: str | None = None) -> str:
    """Lista las sesiones de F1 (FP1, Qualifying, Race...) de un año, opcionalmente
    filtradas por país en inglés (p. ej. 'Italy') y/o por circuito (p. ej. 'Monza',
    'Imola'; no distingue mayúsculas). Un país puede tener varios GPs en un año, así
    que usa circuit para concretar. Cada sesión incluye su session_key, que usan el
    resto de tools."""
    sessions = await openf1.get("sessions", year=year, country_name=country)
    if circuit:
        sessions = [s for s in sessions if circuit.lower() in s["circuit_short_name"].lower()]
    if not sessions:
        filtros = " / ".join(f for f in (country, circuit) if f)
        return f"No hay sesiones para {year}" + (f" en {filtros}." if filtros else ".")
    return "\n".join(
        f"{s['date_start'][:10]} | {s['country_name']} ({s['circuit_short_name']}) | "
        f"{s['session_name']} | session_key: {s['session_key']}"
        for s in sessions
    )


@mcp_server.tool()
@friendly_errors
async def list_drivers(session_key: int) -> str:
    """Lista los pilotos de una sesión con su driver_number, que es como OpenF1
    identifica a cada piloto en el resto de tools (p. ej. get_laps)."""
    drivers = await openf1.get("drivers", session_key=session_key)
    if not drivers:
        return f"No hay pilotos para la sesión {session_key}."
    return "\n".join(
        f"#{d['driver_number']} {d['full_name']} ({d['name_acronym']}) — {d['team_name']}"
        for d in sorted(drivers, key=lambda d: d["driver_number"])
    )


@mcp_server.tool()
@friendly_errors
async def get_results(session_key: int) -> str:
    """Clasificación final de una sesión: posición, piloto, vueltas completadas,
    tiempo total (en clasificación, el de la última ronda disputada), gap con el
    líder y abandonos (DNF = no terminó, DNS = no salió, DSQ = descalificado)."""
    results, drivers = await asyncio.gather(
        openf1.get("session_result", session_key=session_key),
        openf1.get("drivers", session_key=session_key),
    )
    if not results:
        return f"No hay resultados para la sesión {session_key}."
    info = {d["driver_number"]: d for d in drivers}

    lines = []
    for r in sorted(results, key=lambda r: (r.get("position") is None, r.get("position") or 0)):
        d = info.get(r["driver_number"], {})
        pos = f"P{r['position']}" if r.get("position") else "—"
        status = next((k.upper() for k in ("dnf", "dns", "dsq") if r.get(k)), "")
        lines.append(
            f"{pos:<4} #{r['driver_number']} {d.get('name_acronym', '?')} "
            f"({d.get('team_name', '?')}) | {r.get('number_of_laps', '—')} vueltas | "
            f"tiempo {fmt_duration(r.get('duration'))} | gap {fmt_gap(r.get('gap_to_leader'))}"
            + (f" | {status}" if status else "")
        )
    return "\n".join(lines)
