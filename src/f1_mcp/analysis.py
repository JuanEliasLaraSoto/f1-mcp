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
