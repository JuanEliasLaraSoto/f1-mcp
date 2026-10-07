"""Lap and pace tools: lap by lap, driver comparison and stints."""

import asyncio

from f1_mcp import analysis, openf1
from f1_mcp.analysis import of_driver
from f1_mcp.formatting import fmt_time
from f1_mcp.mcp.errors import friendly_errors
from f1_mcp.mcp.server import mcp_server


@mcp_server.tool()
@friendly_errors
async def get_laps(session_key: int, driver_number: int) -> str:
    """A driver's laps in a session: lap time, sector times and whether it was a
    pit-out lap. Use list_sessions for the session_key and list_drivers for the
    driver_number."""
    laps = await openf1.get("laps", session_key=session_key, driver_number=driver_number)
    if not laps:
        return f"No laps found for driver #{driver_number} in session {session_key}."

    lines = ["Lap | Time | S1 | S2 | S3 | Notes"]
    for lap in sorted(laps, key=lambda x: x["lap_number"]):
        notes = "pit out" if lap.get("is_pit_out_lap") else ""
        lines.append(
            f"{lap['lap_number']} | {fmt_time(lap.get('lap_duration'))} | "
            f"{lap.get('duration_sector_1') or '—'} | {lap.get('duration_sector_2') or '—'} | "
            f"{lap.get('duration_sector_3') or '—'} | {notes}"
        )

    timed = [lap["lap_duration"] for lap in laps if lap.get("lap_duration")]
    if timed:
        lines.append(f"\nFastest lap: {fmt_time(min(timed))} | Timed laps: {len(timed)}")
    return "\n".join(lines)


@mcp_server.tool()
@friendly_errors
async def compare_drivers(session_key: int, driver_a: int, driver_b: int) -> str:
    """Compares the pace of two drivers in a session (best for races): fastest lap,
    mean and median pace, consistency and a lap-by-lap duel. Consistency is measured
    on the residuals after removing each stint's trend (fuel burn and degradation),
    so it reflects how regular the driver was, not how the car evolved.
    driver_a/driver_b are driver_number values (see list_drivers)."""
    # 3 whole-session requests (all laps and stints) instead of 5 per-driver ones:
    # stays within OpenF1's 3 req/s limit; filtering happens locally.
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
        return f"Not enough laps to compare {na} and {nb} in session {session_key}."

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

    return "\n".join(
        [
            f"Pace comparison — session {session_key}",
            f"{'':<22}{na:>12}{nb:>12}",
            f"{'Clean laps':<22}{sa['laps']:>12}{sb['laps']:>12}",
            f"{'Fastest lap':<22}{fmt_time(sa['fastest']):>12}{fmt_time(sb['fastest']):>12}",
            f"{'Mean pace':<22}{fmt_time(sa['mean']):>12}{fmt_time(sb['mean']):>12}",
            f"{'Median pace':<22}{fmt_time(sa['median']):>12}{fmt_time(sb['median']):>12}",
            f"{'Raw std dev (s)':<22}{sa['std']:>12.3f}{sb['std']:>12.3f}",
            f"{'Consistency σ (s)':<22}{fmt_cons(ca):>12}{fmt_cons(cb):>12}",
            "",
            f"Median pace: {faster} is {abs(median_gap):.3f} s/lap faster than {slower}.",
            f"Lap-by-lap duel ({h2h['common_laps']} comparable laps): "
            f"{na} faster in {h2h['a_faster']}, mean gap {h2h['delta_mean']:+.3f} s "
            f"(negative = {na} faster).",
            "Raw std dev: includes the gain from fuel burn and tyre degradation.",
            "Consistency σ: spread of the residuals after removing each stint's trend "
            "and outliers (MAD, 3σ). Lower = more consistent.",
            "Clean laps: excludes lap 1, pit-out laps and laps >107% of the median.",
        ]
    )


@mcp_server.tool()
@friendly_errors
async def get_stints(session_key: int, driver_number: int) -> str:
    """A driver's stints (runs on the same set of tyres): compound, laps, tyre age
    when fitted, mean pace and estimated degradation (slope of lap time per lap,
    observed and corrected for fuel burn). Useful for strategy and tyre management."""
    stints, laps = await asyncio.gather(
        openf1.get("stints", session_key=session_key, driver_number=driver_number),
        openf1.get("laps", session_key=session_key, driver_number=driver_number),
    )
    if not stints:
        return f"No stints found for driver #{driver_number} in session {session_key}."

    clean = analysis.clean_laps(laps)
    last_lap = max((lap["lap_number"] for lap in laps), default=0)

    lines = []
    for s in sorted(stints, key=lambda s: s["stint_number"]):
        start, end = s["lap_start"], s["lap_end"] or last_lap
        header = (
            f"Stint {s['stint_number']}: {s['compound']} | laps {start}-{end} "
            f"({end - start + 1}) | tyres {s['tyre_age_at_start']} laps old when fitted"
        )
        deg = analysis.stint_degradation(clean, start, end)
        if deg is None:
            lines.append(f"{header}\n  Too few clean laps to estimate degradation.")
        else:
            lines.append(
                f"{header}\n"
                f"  Mean pace: {fmt_time(deg['mean'])} ({deg['laps']} clean laps)\n"
                f"  Observed degradation: {deg['slope']:+.3f} s/lap | "
                f"fuel-corrected: {deg['slope_fuel_corrected']:+.3f} s/lap"
            )

    lines.append(
        f"\nNote: fuel correction is an approximation of "
        f"{analysis.FUEL_EFFECT_PER_LAP} s/lap; corrected degradation is an estimate."
    )
    return "\n".join(lines)
