"""Race strategy tools: tyres and pit stops for the whole grid."""

import asyncio
from collections import Counter

from f1_mcp import analysis, openf1
from f1_mcp.analysis import of_driver
from f1_mcp.mcp.errors import friendly_errors
from f1_mcp.mcp.server import mcp_server


@mcp_server.tool()
@friendly_errors
async def race_strategy(session_key: int) -> str:
    """Tyre strategy of the whole grid in a race, in finishing order: compounds with
    their laps, number of stops, lap of each stop and stationary time. Ends with a
    summary: most common strategies and fastest stop. For one driver's degradation
    details use get_stints."""
    stints, pits, results = await asyncio.gather(
        openf1.get("stints", session_key=session_key),
        openf1.get("pit", session_key=session_key),
        openf1.get("session_result", session_key=session_key),
    )
    if not stints:
        return f"No stint data found for session {session_key}."
    drivers = await openf1.get("drivers", session_key=session_key)
    names = {d["driver_number"]: d["name_acronym"] for d in drivers}

    # Finishing order; without results, by driver number
    ranked = sorted(results, key=lambda r: (r.get("position") is None, r.get("position") or 0))
    order = [r["driver_number"] for r in ranked] or sorted({s["driver_number"] for s in stints})
    pos = {r["driver_number"]: r.get("position") for r in results}

    lines = []
    labels = []
    for num in order:
        ds = sorted(of_driver(stints, num), key=lambda s: s["stint_number"])
        if not ds:
            continue
        labels.append(analysis.strategy_label(ds))
        runs = " → ".join(f"{s['compound']} ({s['lap_start']}-{s['lap_end'] or '?'})" for s in ds)
        stops = sorted(of_driver(pits, num), key=lambda p: p["lap_number"])
        stop_list = ", ".join(
            f"lap {p['lap_number']}"
            + (f" ({p['stop_duration']:.1f} s stationary)" if p.get("stop_duration") else "")
            for p in stops
        )
        p = f"P{pos[num]}" if pos.get(num) else "—"
        lines.append(
            f"{p:<4} {names.get(num, f'#{num}')}: {runs} | "
            f"{len(stops)} stop(s){': ' + stop_list if stop_list else ''}"
        )

    summary = [f"{n} driver(s): {label}" for label, n in Counter(labels).most_common(3)]
    timed = [p for p in pits if p.get("stop_duration")]
    lines += ["", "Most common strategies:", *summary]
    if timed:
        best = min(timed, key=lambda p: p["stop_duration"])
        lines.append(
            f"Fastest stop: {names.get(best['driver_number'], '?')} "
            f"{best['stop_duration']:.1f} s (lap {best['lap_number']})"
        )
    return "\n".join(lines)
