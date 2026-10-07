# Driver consistency measured on residuals, not raw lap times

**Date:** 2026-10-07

## Problem

The first version of `compare_drivers` measured consistency as the standard deviation of
the driver's clean lap times. On real data (Monza 2025, LEC vs HAM) it came out at ~1.1 s,
far too high for an F1 driver on race pace.

The cause: race lap times have a **trend**. The car gets ~0.055 s/lap faster as fuel burns
(~3 s over 53 laps) and each stint has its own tyre degradation. The raw standard deviation
was measuring how the car evolved, not how regular the driver was. On top of that, the
107 %-of-median filter still lets in-laps through (~5 s slower).

## Decision

Measure consistency on the **residuals**:

1. For each stint, fit a least-squares line `lap_time = a + b·lap`.
2. Compute each lap's residual against its own stint's line.
3. Remove outliers robustly: |r − median| > 3σ, with σ = 1.4826·MAD.
4. Consistency = standard deviation of the remaining residuals.

The raw standard deviation is still shown next to it, so the difference is visible.

## Side effect: fewer requests

Also needing stints would have pushed `compare_drivers` to 5 concurrent requests (laps and
stints for each driver, plus drivers), above OpenF1's free limit of 3 req/s. Instead it
fetches laps and stints **for the whole session** once each and filters locally: 3 requests.

## Verification

Test with synthetic data (−0.1 s/lap trend + ±0.1 s noise + one lap at +5 s): the raw
standard deviation is above 0.5 s, while the residual-based consistency stays below 0.2 s,
recovering the injected noise.
