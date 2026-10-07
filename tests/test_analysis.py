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


def test_stint_degradation_recupera_la_pendiente() -> None:
    from f1_mcp.analysis import FUEL_EFFECT_PER_LAP, stint_degradation

    # Datos sintéticos: pierde exactamente 0.1 s por vuelta entre las vueltas 10 y 20
    clean = {n: 90.0 + 0.1 * (n - 10) for n in range(10, 21)}
    clean[5] = 85.0  # fuera del stint: se ignora

    deg = stint_degradation(clean, 10, 20)

    assert deg is not None
    assert deg["laps"] == 11
    assert round(deg["slope"], 6) == 0.1
    assert round(deg["slope_fuel_corrected"], 6) == round(0.1 + FUEL_EFFECT_PER_LAP, 6)


def test_stint_degradation_none_con_pocas_vueltas() -> None:
    from f1_mcp.analysis import stint_degradation

    assert stint_degradation({10: 90.0, 11: 90.1}, 10, 20) is None


def test_consistencia_sobre_residuos_ignora_tendencia_y_outliers() -> None:
    from f1_mcp.analysis import detrended_residuals, pace_stats, robust_consistency

    # Un stint: mejora 0.1 s/vuelta (tendencia) + ruido de ±0.1 s + una vuelta con tráfico (+5 s)
    clean = {n: 90.0 - 0.1 * (n - 2) + 0.1 * (-1) ** n for n in range(2, 22)}
    clean[10] += 5.0
    stints = [{"lap_start": 2, "lap_end": 21}]

    raw_std = pace_stats(list(clean.values()))["std"]
    consistency = robust_consistency(detrended_residuals(clean, stints))

    # La desviación bruta se infla por la tendencia y el outlier...
    assert raw_std > 0.5
    # ...la consistencia sobre residuos recupera el ruido real (~0.1 s)
    assert consistency is not None
    assert consistency < 0.2
