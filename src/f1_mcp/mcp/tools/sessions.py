"""Tools for the calendar, drivers and results of a session."""

import asyncio

from f1_mcp import openf1
from f1_mcp.formatting import fmt_duration, fmt_gap
from f1_mcp.mcp.errors import friendly_errors
from f1_mcp.mcp.server import mcp_server


@mcp_server.tool()
@friendly_errors
async def list_sessions(year: int, country: str | None = None, circuit: str | None = None) -> str:
    """Lists the F1 sessions (FP1, Qualifying, Race...) of a year, optionally filtered
    by country name in English (e.g. 'Italy') and/or circuit (e.g. 'Monza', 'Imola';
    case-insensitive). A country can host more than one Grand Prix in a year, so use
    circuit to narrow it down. Each session includes its session_key, which every
    other tool needs."""
    sessions = await openf1.get("sessions", year=year, country_name=country)
    if circuit:
        sessions = [s for s in sessions if circuit.lower() in s["circuit_short_name"].lower()]
    if not sessions:
        filters = " / ".join(f for f in (country, circuit) if f)
        return f"No sessions found for {year}" + (f" in {filters}." if filters else ".")
    return "\n".join(
        f"{s['date_start'][:10]} | {s['country_name']} ({s['circuit_short_name']}) | "
        f"{s['session_name']} | session_key: {s['session_key']}"
        for s in sessions
    )


@mcp_server.tool()
@friendly_errors
async def list_drivers(session_key: int) -> str:
    """Lists the drivers of a session with their driver_number, which is how OpenF1
    identifies each driver in the other tools (e.g. get_laps)."""
    drivers = await openf1.get("drivers", session_key=session_key)
    if not drivers:
        return f"No drivers found for session {session_key}."
    return "\n".join(
        f"#{d['driver_number']} {d['full_name']} ({d['name_acronym']}) — {d['team_name']}"
        for d in sorted(drivers, key=lambda d: d["driver_number"])
    )


@mcp_server.tool()
@friendly_errors
async def get_results(session_key: int) -> str:
    """Final classification of a session: position, driver, laps completed, total
    time (in qualifying, the time of the last round reached), gap to the leader and
    retirements (DNF = did not finish, DNS = did not start, DSQ = disqualified)."""
    results, drivers = await asyncio.gather(
        openf1.get("session_result", session_key=session_key),
        openf1.get("drivers", session_key=session_key),
    )
    if not results:
        return f"No results found for session {session_key}."
    info = {d["driver_number"]: d for d in drivers}

    lines = []
    for r in sorted(results, key=lambda r: (r.get("position") is None, r.get("position") or 0)):
        d = info.get(r["driver_number"], {})
        pos = f"P{r['position']}" if r.get("position") else "—"
        status = next((k.upper() for k in ("dnf", "dns", "dsq") if r.get(k)), "")
        lines.append(
            f"{pos:<4} #{r['driver_number']} {d.get('name_acronym', '?')} "
            f"({d.get('team_name', '?')}) | {r.get('number_of_laps', '—')} laps | "
            f"time {fmt_duration(r.get('duration'))} | gap {fmt_gap(r.get('gap_to_leader'))}"
            + (f" | {status}" if status else "")
        )
    return "\n".join(lines)
