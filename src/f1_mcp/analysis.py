"""Cálculos sobre vueltas. Funciones puras: sin red ni MCP, fáciles de testear."""

import statistics
from typing import Any

# Una vuelta más lenta que el 107% de la mediana se considera no representativa
# (safety car, entrada a boxes, tráfico, incidente...). Mismo espíritu que la
# regla del 107% de clasificación de la F1.
OUTLIER_FACTOR = 1.07


def clean_laps(laps: list[dict[str, Any]]) -> dict[int, float]:
    """Devuelve {número de vuelta: tiempo} solo con vueltas representativas del ritmo:
    quita la vuelta 1 (salida), las de salida de boxes, las que no tienen tiempo
    y los outliers por encima del OUTLIER_FACTOR de la mediana."""
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
    """Resumen estadístico del ritmo. cv = coeficiente de variación (%):
    desviación típica relativa a la media; cuanto más bajo, más consistente."""
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
    """Compara vuelta a vuelta solo las vueltas limpias que ambos comparten.
    delta_mean < 0 significa que A fue más rápido de media."""
    common = sorted(a.keys() & b.keys())
    if not common:
        return {"common_laps": 0, "a_faster": 0, "delta_mean": 0.0}
    deltas = [a[n] - b[n] for n in common]
    return {
        "common_laps": len(common),
        "a_faster": sum(d < 0 for d in deltas),
        "delta_mean": statistics.mean(deltas),
    }


# Mejora aproximada del tiempo por vuelta al quemar combustible (s/vuelta).
# Estimación habitual en análisis de F1 (~1.5-1.8 kg/vuelta × ~0.03 s/kg).
FUEL_EFFECT_PER_LAP = 0.055


def stint_degradation(
    clean: dict[int, float], lap_start: int, lap_end: int
) -> dict[str, float] | None:
    """Ajusta una recta tiempo = a + b·vuelta a las vueltas limpias del stint.
    b (pendiente) es la degradación observada en s/vuelta. Como el coche se aligera
    al quemar combustible, la degradación real del neumático se estima como
    b + FUEL_EFFECT_PER_LAP. Devuelve None si hay menos de 3 vueltas limpias."""
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
    """Por cada stint ajusta una recta (combustible + degradación) y devuelve los
    residuos: cuánto se separa cada vuelta de la tendencia de su propio stint."""
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
    """Desviación típica de los residuos tras quitar outliers con la MAD
    (|r - mediana| > 3·σ, con σ = 1.4826·MAD). Mide la regularidad del piloto
    sin el efecto del combustible, la degradación ni vueltas anómalas.
    Devuelve None si no hay datos suficientes."""
    if len(residuals) < 3:
        return None
    med = statistics.median(residuals)
    sigma = 1.4826 * statistics.median(abs(r - med) for r in residuals)
    kept = [r for r in residuals if sigma == 0 or abs(r - med) <= 3 * sigma]
    return statistics.stdev(kept) if len(kept) > 1 else 0.0
