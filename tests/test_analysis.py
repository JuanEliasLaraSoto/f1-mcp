from f1_mcp.analysis import clean_laps, head_to_head, pace_stats


def lap(n: int, t: float | None, pit_out: bool = False) -> dict:
    return {"lap_number": n, "lap_duration": t, "is_pit_out_lap": pit_out}


def test_clean_laps_drops_lap1_pit_out_missing_and_outliers() -> None:
    laps = [
        lap(1, 95.0),  # standing start: dropped
        lap(2, 90.0),
        lap(3, 90.5),
        lap(4, None),  # no time: dropped
        lap(5, 115.0),  # safety car (>107% of median): dropped
        lap(6, 112.0, pit_out=True),  # pit-out lap: dropped
        lap(7, 89.8),
    ]
    assert clean_laps(laps) == {2: 90.0, 3: 90.5, 7: 89.8}


def test_pace_stats_basic() -> None:
    s = pace_stats([90.0, 91.0, 92.0])
    assert s["laps"] == 3
    assert s["fastest"] == 90.0
    assert s["mean"] == 91.0
    assert round(s["std"], 3) == 1.0


def test_head_to_head_only_shared_laps() -> None:
    a = {2: 90.0, 3: 90.0, 4: 90.0}
    b = {2: 90.5, 3: 89.5, 5: 88.0}  # A has no lap 5: not counted
    h = head_to_head(a, b)
    assert h["common_laps"] == 2
    assert h["a_faster"] == 1
    assert h["delta_mean"] == 0.0


def test_stint_degradation_recovers_the_slope() -> None:
    from f1_mcp.analysis import FUEL_EFFECT_PER_LAP, stint_degradation

    # Synthetic data: exactly 0.1 s/lap slower between laps 10 and 20
    clean = {n: 90.0 + 0.1 * (n - 10) for n in range(10, 21)}
    clean[5] = 85.0  # outside the stint: ignored

    deg = stint_degradation(clean, 10, 20)

    assert deg is not None
    assert deg["laps"] == 11
    assert round(deg["slope"], 6) == 0.1
    assert round(deg["slope_fuel_corrected"], 6) == round(0.1 + FUEL_EFFECT_PER_LAP, 6)


def test_stint_degradation_none_with_too_few_laps() -> None:
    from f1_mcp.analysis import stint_degradation

    assert stint_degradation({10: 90.0, 11: 90.1}, 10, 20) is None


def test_residual_consistency_ignores_trend_and_outliers() -> None:
    from f1_mcp.analysis import detrended_residuals, pace_stats, robust_consistency

    # One stint: 0.1 s/lap faster (trend) + ±0.1 s noise + one lap in traffic (+5 s)
    clean = {n: 90.0 - 0.1 * (n - 2) + 0.1 * (-1) ** n for n in range(2, 22)}
    clean[10] += 5.0
    stints = [{"lap_start": 2, "lap_end": 21}]

    raw_std = pace_stats(list(clean.values()))["std"]
    consistency = robust_consistency(detrended_residuals(clean, stints))

    # The raw standard deviation is inflated by the trend and the outlier...
    assert raw_std > 0.5
    # ...the residual-based consistency recovers the real noise (~0.1 s)
    assert consistency is not None
    assert consistency < 0.2
