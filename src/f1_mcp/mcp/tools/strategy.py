"""Tools de estrategia de carrera: neumáticos y paradas de toda la parrilla."""

import asyncio
from collections import Counter

from f1_mcp import analysis, openf1
from f1_mcp.analysis import of_driver
from f1_mcp.mcp.server import mcp_server


@mcp_server.tool()
async def race_strategy(session_key: int) -> str:
    """Estrategia de neumáticos de toda la parrilla en una carrera, en orden de llegada:
    compuestos con sus vueltas, número de paradas, vuelta de cada parada y tiempo
    parado. Termina con un resumen: estrategias más usadas y parada más rápida.
    Para el detalle de degradación de un piloto usa get_stints."""
    stints, pits, results = await asyncio.gather(
        openf1.get("stints", session_key=session_key),
        openf1.get("pit", session_key=session_key),
        openf1.get("session_result", session_key=session_key),
    )
    if not stints:
        return f"No hay datos de stints para la sesión {session_key}."
    drivers = await openf1.get("drivers", session_key=session_key)
    names = {d["driver_number"]: d["name_acronym"] for d in drivers}

    # Orden de llegada; si no hay resultados, por número de piloto
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
        tramos = " → ".join(
            f"{s['compound']} ({s['lap_start']}-{s['lap_end'] or '?'})" for s in ds
        )
        stops = sorted(of_driver(pits, num), key=lambda p: p["lap_number"])
        paradas = ", ".join(
            f"v{p['lap_number']}"
            + (f" ({p['stop_duration']:.1f} s parado)" if p.get("stop_duration") else "")
            for p in stops
        )
        p = f"P{pos[num]}" if pos.get(num) else "—"
        lines.append(
            f"{p:<4} {names.get(num, f'#{num}')}: {tramos} | "
            f"{len(stops)} parada(s){': ' + paradas if paradas else ''}"
        )

    resumen = [f"{n} piloto(s): {label}" for label, n in Counter(labels).most_common(3)]
    timed = [p for p in pits if p.get("stop_duration")]
    lines += ["", "Estrategias más usadas:", *resumen]
    if timed:
        best = min(timed, key=lambda p: p["stop_duration"])
        lines.append(
            f"Parada más rápida: {names.get(best['driver_number'], '?')} "
            f"{best['stop_duration']:.1f} s (vuelta {best['lap_number']})"
        )
    return "\n".join(lines)
