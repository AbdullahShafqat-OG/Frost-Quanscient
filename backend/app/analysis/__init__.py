"""Freeze-risk analysis: environment, reference model, events, verdict and result assembly."""

from typing import List, Literal, Optional

from ..config import get_settings
from ..models.pipe_params import AnalysisResults, PipeParams, SeriesPoint, SweepPoint
from . import reference
from .environment import assumptions, environment
from .events import critical_from_sweep, detect_events
from .verdict import build_verdict


def sweep_ambients(params: PipeParams) -> List[float]:
    """Outside temperatures to analyse (°C, warm -> cold), always including the user's."""
    values = set(get_settings().sweep_ambients_c) | {params.outside_temp_c}
    return sorted(values, reverse=True)


def build_results(
    analysis_id: str,
    mode: Literal["simulation", "demo"],
    params: PipeParams,
    series: List[SeriesPoint],
    sweep: List[SweepPoint],
    critical: Optional[float] = None,
    critical_note: Optional[str] = None,
) -> AnalysisResults:
    """Assemble results; the critical temperature comes from the sweep unless given."""
    onset, blockage = detect_events(series)
    if critical is None and critical_note is None:
        critical, critical_note = critical_from_sweep(
            sweep, params.cold_snap_hours, params.window_hours
        )

    return AnalysisResults(
        analysis_id=analysis_id,
        mode=mode,
        parameters=params,
        h_out=environment(params, params.outside_temp_c).h,
        surroundings_c=reference.surroundings_end_of_snap(params, params.outside_temp_c),
        assumptions=assumptions(params),
        window_hours=params.window_hours,
        series=series,
        t_onset_hours=onset,
        t_blockage_hours=blockage,
        critical_ambient_c=critical,
        critical_note=critical_note,
        sweep=sweep,
        verdict=build_verdict(params, mode, onset, blockage, critical, critical_note, sweep),
    )


def run_demo(analysis_id: str, params: PipeParams) -> AnalysisResults:
    """Local estimate with the same response shape as a full simulation."""
    critical = reference.critical_ambient(params)
    return build_results(
        analysis_id,
        "demo",
        params,
        series=reference.series(params, params.outside_temp_c),
        sweep=reference.sweep(params, sweep_ambients(params)),
        critical=critical,
        critical_note=(
            None
            if critical is not None
            else (
                f"Critical temperature is outside {reference.CRITICAL_SEARCH_C:g}…0 °C "
                f"for a {params.cold_snap_hours:g} h cold snap."
            )
        ),
    )


__all__ = ["build_results", "run_demo", "sweep_ambients", "detect_events", "critical_from_sweep"]
