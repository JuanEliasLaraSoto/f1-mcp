import asyncio
import logging
from collections import Counter
from typing import Any

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


def of_driver(rows: list[dict[str, Any]], driver_number: int) -> list[dict[str, Any]]:
    """Filtra filas de OpenF1 (vueltas, stints...) de un piloto concreto."""
    return [r for r in rows if r["driver_number"] == driver_number]


@mcp_server.tool()
def ping() -> str:
    """Health-check: confirma que el servidor responde."""
    return "pong"


@mcp_server.tool()
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
    rápida, ritmo medio y mediano, consistencia y duelo vuelta a vuelta. La
    consistencia se mide sobre los residuos tras quitar la tendencia de cada stint
    (combustible y degradación), así que refleja la regularidad del piloto y no la
    evolución del coche. driver_a/driver_b son driver_number (ver list_drivers)."""
    # 3 peticiones de sesión completa (todas las vueltas y stints) en vez de 5 por
    # piloto: respeta el límite de 3 req/s de OpenF1 y filtramos en local.
    laps, stints, drivers = await asyncio.gather(
        openf1.get("laps", session_key=session_key),
        openf1.get("stints", session_key=session_key),
        openf1.get("drivers", session_key=session_key),
    )
    names = {d["driver_number"]: d["name_acronym"] for d in drivers}
    na, nb = names.get(driver_a, f"#{driver_a}"), names.get(driver_b, f"#{driver_b}")

    clean_a = analysis.clean_laps(of_driver(laps, driver_a))
    clean_b = analysis.clean_laps(of_driver(laps, driver_b))
    if not clean_a or not clean_b:
        return f"No hay vueltas suficientes para comparar a {na} y {nb} en la sesión {session_key}."

    sa = analysis.pace_stats(list(clean_a.values()))
    sb = analysis.pace_stats(list(clean_b.values()))
    ca = analysis.robust_consistency(
        analysis.detrended_residuals(clean_a, of_driver(stints, driver_a))
    )
    cb = analysis.robust_consistency(
        analysis.detrended_residuals(clean_b, of_driver(stints, driver_b))
    )
    h2h = analysis.head_to_head(clean_a, clean_b)

    def fmt_cons(c: float | None) -> str:
        return f"{c:.3f}" if c is not None else "—"

    median_gap = sa["median"] - sb["median"]
    faster, slower = (na, nb) if median_gap < 0 else (nb, na)

    return "\n".join([
        f"Comparación de ritmo — sesión {session_key}",
        f"{'':<22}{na:>12}{nb:>12}",
        f"{'Vueltas limpias':<22}{sa['laps']:>12}{sb['laps']:>12}",
        f"{'Vuelta rápida':<22}{fmt_time(sa['fastest']):>12}{fmt_time(sb['fastest']):>12}",
        f"{'Ritmo medio':<22}{fmt_time(sa['mean']):>12}{fmt_time(sb['mean']):>12}",
        f"{'Ritmo mediano':<22}{fmt_time(sa['median']):>12}{fmt_time(sb['median']):>12}",
        f"{'Desv. típica bruta (s)':<22}{sa['std']:>12.3f}{sb['std']:>12.3f}",
        f"{'Consistencia σ (s)':<22}{fmt_cons(ca):>12}{fmt_cons(cb):>12}",
        "",
        f"Ritmo mediano: {faster} es {abs(median_gap):.3f} s/vuelta más rápido que {slower}.",
        f"Duelo vuelta a vuelta ({h2h['common_laps']} vueltas comparables): "
        f"{na} más rápido en {h2h['a_faster']}, diferencia media {h2h['delta_mean']:+.3f} s "
        f"(negativo = {na} más rápido).",
        "Desv. típica bruta: incluye la mejora por combustible y la degradación.",
        "Consistencia σ: desviación de los residuos tras quitar la tendencia de cada stint "
        "y outliers (MAD, 3σ). Más bajo = más regular.",
        "Vueltas limpias: sin vuelta 1, salidas de boxes ni vueltas >107% de la mediana.",
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


def fmt_duration(value: Any) -> str:
    """Tiempo total de una sesión. En clasificación OpenF1 da [Q1, Q2, Q3]: se usa
    el último disponible. Más de una hora -> 'h:mm:ss.sss'."""
    if isinstance(value, list):
        value = next((v for v in reversed(value) if v is not None), None)
    if value is None:
        return "—"
    if value >= 3600:
        hours, rest = divmod(value, 3600)
        return f"{int(hours)}:{fmt_time(rest).zfill(9)}"
    return fmt_time(value)


def fmt_gap(gap: Any) -> str:
    """Gap con el líder: número (s), texto ('+1 LAP') o lista [Q1, Q2, Q3]."""
    if isinstance(gap, list):
        gap = next((g for g in reversed(gap) if g is not None), None)
    if gap is None:
        return "—"
    if isinstance(gap, (int, float)):
        return "líder" if gap == 0 else f"+{gap:.3f} s"
    return str(gap)


@mcp_server.tool()
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


# Importar estos módulos registra sus @mcp_server.resource() y @mcp_server.prompt().
# Va al final porque ellos importan mcp_server de este archivo: tiene que existir ya.
from f1_mcp import prompts, resources  # noqa: E402, F401
