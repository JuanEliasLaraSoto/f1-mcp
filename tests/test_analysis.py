from f1_mcp.analysis import clean_laps, head_to_head, pace_stats


def lap(n: int, t: float | None, pit_out: bool = False) -> dict:
    return {"lap_number": n, "lap_duration": t, "is_pit_out_lap": pit_out}


def test_clean_laps_quita_vuelta1_pitout_nulos_y_outliers() -> None:
    laps = [
        lap(1, 95.0),                 # salida: fuera
        lap(2, 90.0),
        lap(3, 90.5),
        lap(4, None),                 # sin tiempo: fuera
        lap(5, 115.0),                # safety car (>107% mediana): fuera
        lap(6, 112.0, pit_out=True),  # salida de boxes: fuera
        lap(7, 89.8),
    ]
    assert clean_laps(laps) == {2: 90.0, 3: 90.5, 7: 89.8}


def test_pace_stats_basico() -> None:
    s = pace_stats([90.0, 91.0, 92.0])
    assert s["laps"] == 3
    assert s["fastest"] == 90.0
    assert s["mean"] == 91.0
    assert round(s["std"], 3) == 1.0


def test_head_to_head_solo_vueltas_comunes() -> None:
    a = {2: 90.0, 3: 90.0, 4: 90.0}
    b = {2: 90.5, 3: 89.5, 5: 88.0}   # la vuelta 5 no la tiene A: no cuenta
    h = head_to_head(a, b)
    assert h["common_laps"] == 2
    assert h["a_faster"] == 1
    assert h["delta_mean"] == 0.0
