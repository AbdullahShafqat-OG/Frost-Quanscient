"""Rule-based verdict and advice text from analysis results."""

from typing import List, Literal, Optional

from ..models.pipe_params import (
    Location,
    PipeParams,
    SweepPoint,
    Verdict,
)
from . import reference

LOCATION_LABEL = {
    Location.OUTDOORS: "outdoors",
    Location.INDOORS: "indoors",
    Location.UNDERGROUND: "underground",
}


def fmt_hours(hours: float) -> str:
    if hours < 1.0:
        return f"{hours * 60:.0f} min"
    return f"{hours:.1f} h"


def build_verdict(
    params: PipeParams,
    mode: Literal["simulation", "demo"],
    onset: Optional[float],
    blockage: Optional[float],
    critical: Optional[float],
    critical_note: Optional[str],
    sweep: List[SweepPoint],
) -> Verdict:
    snap = params.cold_snap_hours
    t_out = params.outside_temp_c
    where = LOCATION_LABEL[params.location]

    # ---- Level: "freezes" = blocked during the cold snap ----
    if blockage is not None and blockage <= snap:
        level = "freezes"
    elif (
        (onset is not None and onset <= snap)
        or (blockage is not None and blockage <= 1.5 * snap)
        or (critical is not None and critical >= t_out - 3.0)
    ):
        level = "at_risk"
    else:
        level = "safe"

    # ---- Headline ----
    if level == "freezes":
        headline = (
            f"Freezes {where} at {t_out:g} °C: blocked with ice after {fmt_hours(blockage)} "
            f"(cold snap lasts {snap:g} h)."
        )
    elif level == "at_risk" and onset is not None and onset <= snap:
        headline = (
            f"At risk {where} at {t_out:g} °C: ice starts forming after {fmt_hours(onset)}, "
            f"but the pipe stays open through the {snap:g} h cold snap."
        )
    elif level == "at_risk":
        headline = f"Marginal {where} at {t_out:g} °C: survives the {snap:g} h cold snap, but with little margin."
    else:
        headline = f"Safe {where} at {t_out:g} °C for {snap:g} h."

    # ---- Details ----
    details: List[str] = []
    if critical is not None:
        details.append(
            f"Critical outside temperature for a {snap:g} h cold snap: {critical:.1f} °C "
            "(pipe blocked by the end)."
        )
    elif critical_note:
        details.append(critical_note)

    safe_pts = [p for p in sweep if p.t_blockage_hours is None or p.t_blockage_hours > snap]
    fail_pts = [p for p in sweep if p.t_blockage_hours is not None and p.t_blockage_hours <= snap]
    if safe_pts:
        coldest_safe = min(safe_pts, key=lambda p: p.ambient_c)
        details.append(f"Safe at {coldest_safe.ambient_c:g} °C for {snap:g} h.")
    if fail_pts:
        warmest_fail = max(fail_pts, key=lambda p: p.ambient_c)
        details.append(
            f"Fails at {warmest_fail.ambient_c:g} °C after {fmt_hours(warmest_fail.t_blockage_hours)}."
        )

    if onset is None:
        details.append(f"No ice within the {params.window_hours:g} h analysed at {t_out:g} °C.")
    else:
        line = f"At {t_out:g} °C: first ice after {fmt_hours(onset)}"
        if blockage is not None:
            line += f", blocked after {fmt_hours(blockage)}"
        else:
            line += f", not blocked within the {params.window_hours:g} h analysed"
        details.append(line + ".")
    if params.drip_flow_lpm > 0:
        details.append(f"Includes a {params.drip_flow_lpm:g} L/min drip.")

    # ---- Actions (sizing from the analytic reference model) ----
    actions: List[str] = []
    if level == "safe":
        actions.append("No action needed for this scenario.")
        if critical is not None:
            actions.append(f"Margin to the critical temperature: {t_out - critical:.1f} °C.")
    else:
        target = 1.5 * snap
        drip = reference.suggest_drip_lpm(params)
        drip_text = (
            f"run a {drip:.2f} L/min drip"
            if drip <= 1.0
            else "a drip would need more than 1 L/min"
        )
        if blockage is None or blockage >= target:
            # Already stays open with margin; only ice-free operation is left to gain
            actions.append(f"To keep the water ice-free, {drip_text}.")
        else:
            # Blocked during the snap: aim to survive it; marginal: aim for 1.5× margin
            freezes_in_snap = blockage <= snap
            insulation = reference.suggest_insulation(
                params, target_hours=snap if freezes_in_snap else target
            )
            if insulation:
                verb = "Use" if params.has_insulation else "Add"
                benefit = "keeps it open through the cold snap" if freezes_in_snap else "adds a safety margin"
                actions.append(
                    f"{verb} {reference.describe_insulation(*insulation)} insulation "
                    f"({benefit}) or {drip_text}."
                )
            else:
                actions.append(
                    f"Insulation alone is not enough here (even 50 mm): "
                    f"{drip_text}, fit heat tracing, or drain the line."
                )
        if level == "freezes":
            actions.append("If the space will be unheated and unused, shut off and drain the pipe.")

    # ---- Caveats ----
    caveats = [
        "No supercooling: real water can dip a few degrees below 0 °C before ice forms, slightly delaying first ice.",
        "No natural convection inside the water; stagnant water conducts heat only.",
        "No heat flow along the pipe from adjacent warm sections or the heated building.",
        "External heat transfer is estimated from the location and outside temperature, not measured.",
        "Suggested insulation and drip are estimates from the analytic model.",
    ]
    if params.drip_flow_lpm > 0:
        caveats.append("Drip flow is modelled as uniform heat input along the run (no flow simulation).")
    if mode == "demo":
        caveats.insert(
            0,
            "Demo mode: a single-temperature (lumped) estimate. First ice is when the bulk water "
            "reaches 0 °C, so it is later than the real first ice at the pipe wall.",
        )
    else:
        caveats.insert(
            0,
            "Full simulation: a short pipe segment with adiabatic ends; latent heat is smeared "
            "over ±1 K around 0 °C (apparent heat capacity).",
        )

    return Verdict(level=level, headline=headline, details=details, actions=actions, caveats=caveats)
