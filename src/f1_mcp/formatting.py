"""Formatting of lap times and gaps for the text the tools return."""

from typing import Any


def fmt_time(seconds: float | None) -> str:
    """91.743 -> '1:31.743'. None (lap without a time) -> '—'."""
    if seconds is None:
        return "—"
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes)}:{secs:06.3f}"


def fmt_duration(value: Any) -> str:
    """Total session time. For qualifying OpenF1 returns [Q1, Q2, Q3]: the last
    available one is used. Over an hour -> 'h:mm:ss.sss'."""
    if isinstance(value, list):
        value = next((v for v in reversed(value) if v is not None), None)
    if value is None:
        return "—"
    if value >= 3600:
        hours, rest = divmod(value, 3600)
        return f"{int(hours)}:{fmt_time(rest).zfill(9)}"
    return fmt_time(value)


def fmt_gap(gap: Any) -> str:
    """Gap to the leader: a number (s), text ('+1 LAP') or a list [Q1, Q2, Q3]."""
    if isinstance(gap, list):
        gap = next((g for g in reversed(gap) if g is not None), None)
    if gap is None:
        return "—"
    if isinstance(gap, (int, float)):
        return "leader" if gap == 0 else f"+{gap:.3f} s"
    return str(gap)
