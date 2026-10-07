"""Lap-time analysis. Pure functions: no network, no MCP, easy to test."""

import statistics
from typing import Any

# A lap slower than 107 % of the median is not representative of pace (safety car,
# in-lap, traffic, incident...). Same spirit as F1's 107 % qualifying rule.
OUTLIER_FACTOR = 1.07

# Approximate lap-time gain from burning fuel (s/lap). Common estimate in F1 analysis
# (~1.5-1.8 kg of fuel per lap × ~0.03 s/kg).
FUEL_EFFECT_PER_LAP = 0.055


def clean_laps(laps: list[dict[str, Any]]) -> dict[int, float]:
    """Returns {lap number: lap time} for laps that represent race pace only: drops
    lap 1 (standing start), pit-out laps, laps without a time and outliers above
    OUTLIER_FACTOR times the median."""
    candidates = {
        lap["lap_number"]: lap["lap_duration"]
        for lap in laps
        if lap.get("lap_duration") and not lap.get("is_pit_out_lap") and lap["lap_number"] > 1
    }
    if not candidates:
        return {}
    threshold = statistics.median(candidates.values()) * OUTLIER_FACTOR
    return {n: t for n, t in candidates.items() if t <= threshold}


def pace_stats(times: list[float]) -> dict[str, float]:
    """Summary statistics of pace. cv = coefficient of variation (%): standard
    deviation relative to the mean."""
    mean = statistics.mean(times)
    std = statistics.stdev(times) if len(times) > 1 else 0.0
    return {
        "laps": len(times),
        "fastest": min(times),
        "mean": mean,
        "median": statistics.median(times),
        "std": std,
        "cv": std / mean * 100,
    }


def head_to_head(a: dict[int, float], b: dict[int, float]) -> dict[str, float]:
    """Lap-by-lap comparison restricted to the clean laps both drivers share.
    delta_mean < 0 means driver A was faster on average."""
    common = sorted(a.keys() & b.keys())
    if not common:
        return {"common_laps": 0, "a_faster": 0, "delta_mean": 0.0}
    deltas = [a[n] - b[n] for n in common]
    return {
        "common_laps": len(common),
        "a_faster": sum(d < 0 for d in deltas),
        "delta_mean": statistics.mean(deltas),
    }


def stint_degradation(
    clean: dict[int, float], lap_start: int, lap_end: int
) -> dict[str, float] | None:
    """Fits a line lap_time = a + b·lap to the clean laps of a stint. The slope b is
    the observed degradation in s/lap. Since the car gets lighter as it burns fuel,
    the tyre's real degradation is estimated as b + FUEL_EFFECT_PER_LAP.
    Returns None if the stint has fewer than 3 clean laps."""
    points = [(n, t) for n, t in sorted(clean.items()) if lap_start <= n <= lap_end]
    if len(points) < 3:
        return None
    x = [n for n, _ in points]
    y = [t for _, t in points]
    slope, _intercept = statistics.linear_regression(x, y)
    return {
        "laps": len(points),
        "mean": statistics.mean(y),
        "slope": slope,
        "slope_fuel_corrected": slope + FUEL_EFFECT_PER_LAP,
    }


def detrended_residuals(clean: dict[int, float], stints: list[dict[str, Any]]) -> list[float]:
    """Fits a line per stint (fuel burn + degradation) and returns the residuals:
    how far each lap is from its own stint's trend."""
    if not clean:
        return []
    last = max(clean)
    residuals: list[float] = []
    for s in stints:
        start, end = s["lap_start"], s["lap_end"] or last
        pts = [(n, t) for n, t in sorted(clean.items()) if start <= n <= end]
        if len(pts) < 3:
            continue
        slope, intercept = statistics.linear_regression([n for n, _ in pts], [t for _, t in pts])
        residuals += [t - (intercept + slope * n) for n, t in pts]
    return residuals


def robust_consistency(residuals: list[float]) -> float | None:
    """Standard deviation of the residuals after removing outliers with the MAD
    (|r - median| > 3σ, with σ = 1.4826·MAD). Measures how regular the driver is,
    without the effect of fuel burn, degradation or abnormal laps.
    Returns None if there is not enough data."""
    if len(residuals) < 3:
        return None
    med = statistics.median(residuals)
    sigma = 1.4826 * statistics.median(abs(r - med) for r in residuals)
    kept = [r for r in residuals if sigma == 0 or abs(r - med) <= 3 * sigma]
    return statistics.stdev(kept) if len(kept) > 1 else 0.0


def strategy_label(stints: list[dict[str, Any]]) -> str:
    """'MEDIUM → HARD' from a driver's stints (ordered by stint_number). Used to
    group drivers who ran the same strategy."""
    ordered = sorted(stints, key=lambda s: s["stint_number"])
    return " → ".join(s["compound"] or "?" for s in ordered)


def of_driver(rows: list[dict[str, Any]], driver_number: int) -> list[dict[str, Any]]:
    """Filters OpenF1 rows (laps, stints...) for a single driver."""
    return [r for r in rows if r["driver_number"] == driver_number]
