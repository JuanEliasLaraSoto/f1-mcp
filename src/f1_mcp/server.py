import asyncio
import logging

from mcp.server.mcpserver import MCPServer

from f1_mcp import analysis, openf1

# httpx loguea cada petición; lo silenciamos para que no ensucie la salida
logging.getLogger("httpx").setLevel(logging.WARNING)

mcp_server = MCPServer("f1-mcp")


def fmt_time(seconds: float | None) -> str:
    """91.743 -> '1:31.743'. None (vuelta sin tiempo) -> '—'."""
    if seconds is None:
        return "—"
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes)}:{secs:06.3f}"


@mcp_server.tool()
def ping() -> str:
    """Health-check: confirma que el servidor responde."""
    return "pong"


@mcp_server.tool()
async def list_sessions(year: int, country: str | None = None) -> str:
    """Lista las sesiones de F1 (FP1, Qualifying, Race...) de un año, opcionalmente
    filtradas por país en inglés (p. ej. 'Italy'). Un país puede tener varios GPs
    en un año (Italia: Imola y Monza): fíjate en el circuito. Cada sesión incluye
    su session_key, que usan el resto de tools."""
    sessions = await openf1.get("sessions", year=year, country_name=country)
    if not sessions:
        return f"No hay sesiones para {year}" + (f" en {country}." if country else ".")
    return "\n".join(
        f"{s['date_start'][:10]} | {s['country_name']} ({s['circuit_short_name']}) | "
        f"{s['session_name']} | session_key: {s['session_key']}"
        for s in sessions
    )


@mcp_server.tool()
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
async def get_laps(session_key: int, driver_number: int) -> str:
    """Vueltas de un piloto en una sesión: tiempo por vuelta, tiempos de sector y si
    fue vuelta de salida de boxes (pit out). Usa list_sessions para el session_key
    y list_drivers para el driver_number."""
    laps = await openf1.get("laps", session_key=session_key, driver_number=driver_number)
    if not laps:
        return f"No hay vueltas del piloto #{driver_number} en la sesión {session_key}."

    lines = ["Vuelta | Tiempo | S1 | S2 | S3 | Notas"]
    for lap in sorted(laps, key=lambda x: x["lap_number"]):
        notes = "pit out" if lap.get("is_pit_out_lap") else ""
        lines.append(
            f"{lap['lap_number']} | {fmt_time(lap.get('lap_duration'))} | "
            f"{lap.get('duration_sector_1') or '—'} | {lap.get('duration_sector_2') or '—'} | "
            f"{lap.get('duration_sector_3') or '—'} | {notes}"
        )

    timed = [lap["lap_duration"] for lap in laps if lap.get("lap_duration")]
    if timed:
        lines.append(f"\nVuelta rápida: {fmt_time(min(timed))} | Vueltas con tiempo: {len(timed)}")
    return "\n".join(lines)


@mcp_server.tool()
async def compare_drivers(session_key: int, driver_a: int, driver_b: int) -> str:
    """Compara el ritmo de dos pilotos en una sesión (ideal para carreras): vuelta
    rápida, ritmo medio y mediano, consistencia (desviación típica y coeficiente de
    variación) y duelo vuelta a vuelta. Excluye vueltas no representativas (vuelta 1,
    salidas de boxes, safety car...). driver_a/driver_b son driver_number (ver list_drivers)."""
    laps_a, laps_b, drivers = await asyncio.gather(
        openf1.get("laps", session_key=session_key, driver_number=driver_a),
        openf1.get("laps", session_key=session_key, driver_number=driver_b),
        openf1.get("drivers", session_key=session_key),
    )
    names = {d["driver_number"]: d["name_acronym"] for d in drivers}
    na, nb = names.get(driver_a, f"#{driver_a}"), names.get(driver_b, f"#{driver_b}")

    clean_a, clean_b = analysis.clean_laps(laps_a), analysis.clean_laps(laps_b)
    if not clean_a or not clean_b:
        return f"No hay vueltas suficientes para comparar a {na} y {nb} en la sesión {session_key}."

    sa = analysis.pace_stats(list(clean_a.values()))
    sb = analysis.pace_stats(list(clean_b.values()))
    h2h = analysis.head_to_head(clean_a, clean_b)

    median_gap = sa["median"] - sb["median"]
    faster, slower = (na, nb) if median_gap < 0 else (nb, na)

    return "\n".join([
        f"Comparación de ritmo — sesión {session_key}",
        f"{'':<18}{na:>12}{nb:>12}",
        f"{'Vueltas limpias':<18}{sa['laps']:>12}{sb['laps']:>12}",
        f"{'Vuelta rápida':<18}{fmt_time(sa['fastest']):>12}{fmt_time(sb['fastest']):>12}",
        f"{'Ritmo medio':<18}{fmt_time(sa['mean']):>12}{fmt_time(sb['mean']):>12}",
        f"{'Ritmo mediano':<18}{fmt_time(sa['median']):>12}{fmt_time(sb['median']):>12}",
        f"{'Desv. típica (s)':<18}{sa['std']:>12.3f}{sb['std']:>12.3f}",
        f"{'Coef. variación':<18}{sa['cv']:>11.2f}%{sb['cv']:>11.2f}%",
        "",
        f"Ritmo mediano: {faster} es {abs(median_gap):.3f} s/vuelta más rápido que {slower}.",
        f"Duelo vuelta a vuelta ({h2h['common_laps']} vueltas comparables): "
        f"{na} más rápido en {h2h['a_faster']}, diferencia media {h2h['delta_mean']:+.3f} s "
        f"(negativo = {na} más rápido).",
        "Criterio: se excluyen vuelta 1, salidas de boxes y vueltas >107% de la mediana.",
    ])


@mcp_server.tool()
async def get_stints(session_key: int, driver_number: int) -> str:
    """Stints de un piloto (tramos con el mismo juego de neumáticos): compuesto,
    vueltas, edad del neumático al montarlo, ritmo medio y degradación estimada
    (pendiente del tiempo por vuelta, observada y corregida por consumo de combustible).
    Útil para analizar estrategia y gestión de neumáticos."""
    stints, laps = await asyncio.gather(
        openf1.get("stints", session_key=session_key, driver_number=driver_number),
        openf1.get("laps", session_key=session_key, driver_number=driver_number),
    )
    if not stints:
        return f"No hay stints del piloto #{driver_number} en la sesión {session_key}."

    clean = analysis.clean_laps(laps)
    last_lap = max((lap["lap_number"] for lap in laps), default=0)

    lines = []
    for s in sorted(stints, key=lambda s: s["stint_number"]):
        start, end = s["lap_start"], s["lap_end"] or last_lap
        header = (
            f"Stint {s['stint_number']}: {s['compound']} | vueltas {start}-{end} "
            f"({end - start + 1}) | neumático con {s['tyre_age_at_start']} vueltas al montarlo"
        )
        deg = analysis.stint_degradation(clean, start, end)
        if deg is None:
            lines.append(f"{header}\n  Pocas vueltas limpias para estimar degradación.")
        else:
            lines.append(
                f"{header}\n"
                f"  Ritmo medio: {fmt_time(deg['mean'])} ({deg['laps']} vueltas limpias)\n"
                f"  Degradación observada: {deg['slope']:+.3f} s/vuelta | "
                f"corregida por combustible: {deg['slope_fuel_corrected']:+.3f} s/vuelta"
            )

    lines.append(
        f"\nNota: corrección de combustible aproximada de "
        f"{analysis.FUEL_EFFECT_PER_LAP} s/vuelta; la degradación corregida es una estimación."
    )
    return "\n".join(lines)
