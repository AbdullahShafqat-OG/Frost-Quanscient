"""Freeze events from time series and critical ambient temperature from a sweep."""

import math
from typing import List, Optional, Tuple

from ..models.pipe_params import (
    BLOCKAGE_ICE_FRACTION,
    FREEZE_TEMP_C,
    SeriesPoint,
    SweepPoint,
)


def _first_crossing(
    times: List[float], values: List[float], threshold: float, rising: bool
) -> Optional[float]:
    """First time `values` crosses `threshold`, linearly interpolated."""
    for i, value in enumerate(values):
        crossed = value >= threshold if rising else value <= threshold
        if not crossed:
            continue
        if i == 0:
            return times[0]
        v0, v1 = values[i - 1], value
        t0, t1 = times[i - 1], times[i]
        if v1 == v0:
            return t1
        return t0 + (threshold - v0) * (t1 - t0) / (v1 - v0)
    return None


def detect_events(series: List[SeriesPoint]) -> Tuple[Optional[float], Optional[float]]:
    """(onset, blockage) in hours.

    onset    = first time the coldest water reaches 0 °C (first ice)
    blockage = first time the ice fraction reaches 90 % (pipe frozen shut)
    """
    times = [p.time_hours for p in series]
    onset = _first_crossing(times, [p.t_min_water_c for p in series], FREEZE_TEMP_C, rising=False)
    blockage = _first_crossing(
        times, [p.ice_fraction for p in series], BLOCKAGE_ICE_FRACTION, rising=True
    )
    return onset, blockage


def critical_from_sweep(
    points: List[SweepPoint], target_hours: float, window_hours: float
) -> Tuple[Optional[float], Optional[str]]:
    """Ambient temperature where t_blockage == target_hours.

    Interpolates log(t_blockage) linearly in ambient temperature between the
    warmest pair that brackets the target. A point that didn't block inside the
    window is taken as t_blockage = window (conservative: gives a warmer result).
    """
    pts = sorted(points, key=lambda p: p.ambient_c, reverse=True)  # warm -> cold
    if not pts:
        return None, "No sweep results available."

    def blockage(p: SweepPoint) -> float:
        return p.t_blockage_hours if p.t_blockage_hours is not None else window_hours

    for warm, cold in zip(pts, pts[1:]):
        if (
            blockage(warm) >= target_hours
            and cold.t_blockage_hours is not None
            and blockage(cold) < target_hours
        ):
            t_w, t_c = max(blockage(warm), 1e-6), max(blockage(cold), 1e-6)
            if math.isclose(t_w, t_c):
                return cold.ambient_c, None
            frac = (math.log(target_hours) - math.log(t_w)) / (math.log(t_c) - math.log(t_w))
            critical = warm.ambient_c + frac * (cold.ambient_c - warm.ambient_c)
            note = None
            if warm.t_blockage_hours is None:
                note = "Interpolated against a point that did not block within the window (conservative)."
            return critical, note

    if all(p.t_blockage_hours is None for p in pts):
        return None, (
            f"No blockage within the {window_hours:g} h window, even at {pts[-1].ambient_c:g} °C."
        )
    if blockage(pts[0]) < target_hours:
        return None, (
            f"The pipe blocks within {target_hours:g} h even at {pts[0].ambient_c:g} °C; "
            "the critical temperature is warmer than that."
        )
    return None, (
        f"No blockage within {target_hours:g} h down to {pts[-1].ambient_c:g} °C; "
        "the critical temperature is colder than that."
    )
