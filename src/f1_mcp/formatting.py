"""Formato de tiempos y gaps para el texto que devuelven las tools."""

from typing import Any


def fmt_time(seconds: float | None) -> str:
    """91.743 -> '1:31.743'. None (vuelta sin tiempo) -> '—'."""
    if seconds is None:
        return "—"
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes)}:{secs:06.3f}"


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
