"""
Local (no Allsolve) reference model for pipe freezing.

Lumped-capacitance cooling of the water + pipe wall (+ insulation) mass through
the series thermal resistance per unit length:

    R' = ln(r_wall/r_in)/(2π k_wall) + ln(r_out/r_wall)/(2π k_ins) + 1/(2π r_out h)

towards the surroundings of the chosen location (environment.py), with a
drip-flow heat input m_dot·cp·(T_supply - T)/L_run and a latent-heat plateau
at 0 °C. Stepped in enthalpy with implicit Euler (stable for any drip flow).

Used for demo mode, and for the insulation/drip suggestions in the verdict.
"Freezes" means blocked (90 % ice); first ice comes much earlier and on its own
gives a critical temperature of ~0 °C for any multi-hour cold snap.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..models.pipe_params import (
    BLOCKAGE_ICE_FRACTION,
    DRIP_RUN_LENGTH_M,
    INSULATION_MATERIALS,
    InsulationType,
    LATENT_HEAT,
    PipeParams,
    SeriesPoint,
    SweepPoint,
    WATER_CP,
    WATER_RHO,
)
from .environment import Environment, environment, surroundings_at

ICE_CP = 2100.0  # J/(kg·K), used after the water is fully frozen

# Standard insulation wall thicknesses tried for the suggestion [mm] (slider max 50)
INSULATION_CANDIDATES_MM = [10, 13, 19, 25, 32, 38, 50]
N_STEPS = 2000  # Time steps over the analysed window

# Coldest outside temperature considered when searching for the critical temperature [°C]
CRITICAL_SEARCH_C = -60.0


@dataclass
class Run:
    """Result of one lumped run at a fixed outside temperature."""

    hours: List[float]
    temps: List[float]
    ice: List[float]
    onset: Optional[float]
    blockage: Optional[float]


@dataclass
class LumpedModel:
    """Per-unit-length lumped parameters."""

    c_water: float  # J/(m·K), sensible capacity with liquid water
    c_ice: float  # J/(m·K), sensible capacity with ice
    latent: float  # J/m, latent heat of the water column
    r_inner: float  # (m·K)/W, wall + insulation conduction resistance
    r_outer: float  # m, outermost radius
    d: float  # W/(m·K), drip conductance to supply temperature
    t0: float  # °C, initial water temperature (= drip supply temperature)

    def conductance(self, env: Environment) -> float:
        """W/(m·K) from the water to the surroundings."""
        return 1.0 / (self.r_inner + 1.0 / (2.0 * math.pi * self.r_outer * env.h))

    def run(self, env: Environment, hours: float, stop_at_blockage: bool = False) -> Run:
        """Implicit-Euler enthalpy stepping.

        E (J/m) is measured from fully frozen water at 0 °C:
        E > latent: liquid, T = (E - latent)/c_water
        0..latent:  freezing at 0 °C, ice = 1 - E/latent
        E < 0:      ice, T = E/c_ice
        """
        g = self.conductance(env)
        k = g + self.d
        dt = hours * 3600.0 / N_STEPS
        energy = self.latent + self.c_water * self.t0

        times, temps, ices = [0.0], [self.t0], [0.0]
        onset = blockage = None
        for step in range(1, N_STEPS + 1):
            t_h = step * dt / 3600.0
            source = g * surroundings_at(env, t_h) + self.d * self.t0  # W/m (+ k·T loss)

            # Try each phase; exactly one is self-consistent because T(E) is monotone
            e_liquid = (energy + dt * source + dt * k * self.latent / self.c_water) / (
                1.0 + dt * k / self.c_water
            )
            if e_liquid >= self.latent:
                energy = e_liquid
            elif 0.0 <= energy + dt * source <= self.latent:
                energy = energy + dt * source
            else:
                energy = min((energy + dt * source) / (1.0 + dt * k / self.c_ice), 0.0)

            if energy >= self.latent:
                temp, ice = (energy - self.latent) / self.c_water, 0.0
            elif energy >= 0.0:
                temp, ice = 0.0, 1.0 - energy / self.latent
            else:
                temp, ice = energy / self.c_ice, 1.0

            times.append(t_h)
            temps.append(temp)
            ices.append(ice)
            if onset is None and temp <= 0.0:
                onset = t_h
            if blockage is None and ice >= BLOCKAGE_ICE_FRACTION:
                blockage = t_h
                if stop_at_blockage:
                    break
        return Run(times, temps, ices, onset, blockage)


def build_model(params: PipeParams) -> LumpedModel:
    pipe = params.pipe_props()
    ins = params.insulation_props()
    r_i, r_w, r_o = params.r_inner, params.r_wall, params.r_outer

    a_water = math.pi * r_i**2
    c_solid = pipe["rho"] * pipe["cp"] * math.pi * (r_w**2 - r_i**2)
    resistance = math.log(r_w / r_i) / (2 * math.pi * pipe["k"])
    if ins:
        c_solid += ins["rho"] * ins["cp"] * math.pi * (r_o**2 - r_w**2)
        resistance += math.log(r_o / r_w) / (2 * math.pi * ins["k"])

    return LumpedModel(
        c_water=WATER_RHO * WATER_CP * a_water + c_solid,
        c_ice=WATER_RHO * ICE_CP * a_water + c_solid,
        latent=WATER_RHO * LATENT_HEAT * a_water,
        r_inner=resistance,
        r_outer=r_o,
        d=params.m_dot * WATER_CP / DRIP_RUN_LENGTH_M,
        t0=params.initial_water_temp_c,
    )


def run_at(params: PipeParams, outside_c: float, hours: float, stop_at_blockage: bool = False) -> Run:
    return build_model(params).run(environment(params, outside_c), hours, stop_at_blockage)


def series(params: PipeParams, outside_c: float, n_points: int = 241) -> List[SeriesPoint]:
    run = run_at(params, outside_c, params.window_hours)
    stride = max(1, (len(run.hours) - 1) // (n_points - 1))
    return [
        SeriesPoint(
            time_hours=run.hours[i],
            t_min_water_c=run.temps[i],
            t_avg_water_c=run.temps[i],
            t_max_water_c=run.temps[i],
            ice_fraction=run.ice[i],
        )
        for i in range(0, len(run.hours), stride)
    ]


def sweep(params: PipeParams, ambients_c: List[float]) -> List[SweepPoint]:
    """Freeze events per outside temperature, within the analysed window."""
    points = []
    for outside_c in ambients_c:
        run = run_at(params, outside_c, params.window_hours, stop_at_blockage=True)
        points.append(
            SweepPoint(ambient_c=outside_c, t_onset_hours=run.onset, t_blockage_hours=run.blockage)
        )
    return points


def critical_ambient(params: PipeParams) -> Optional[float]:
    """Outside temperature (°C) at which the pipe blocks by the end of the cold snap.

    Blockage time falls monotonically with colder air, so bisect between
    CRITICAL_SEARCH_C and just below 0 °C. None if outside that range.
    """
    snap = params.cold_snap_hours

    def blocked_within(outside_c: float) -> bool:
        return run_at(params, outside_c, snap, stop_at_blockage=True).blockage is not None

    warm, cold = -0.01, CRITICAL_SEARCH_C
    if blocked_within(warm) or not blocked_within(cold):
        return None
    for _ in range(25):  # ~2e-6 °C resolution
        mid = 0.5 * (warm + cold)
        if blocked_within(mid):
            cold = mid
        else:
            warm = mid
    return 0.5 * (warm + cold)


def surroundings_end_of_snap(params: PipeParams, outside_c: float) -> float:
    return surroundings_at(environment(params, outside_c), params.cold_snap_hours)


def suggest_insulation(params: PipeParams, target_hours: float) -> Optional[Tuple[InsulationType, float]]:
    """(material, thickness mm): the thinnest standard insulation that keeps the pipe
    open past `target_hours`. Keeps the current material, or foam wrap if uninsulated."""
    material = params.insulation if params.has_insulation else InsulationType.FOAM_WRAP
    current = params.insulation_thickness_mm if params.has_insulation else 0.0
    for mm in INSULATION_CANDIDATES_MM:
        if mm <= current:
            continue
        trial = params.model_copy(update={"insulation": material, "insulation_thickness_mm": float(mm)})
        if run_at(trial, params.outside_temp_c, target_hours, stop_at_blockage=True).blockage is None:
            return material, float(mm)
    return None


def suggest_drip_lpm(params: PipeParams) -> float:
    """Drip flow (L/min, rounded up to 0.05) that keeps the water above 0 °C indefinitely."""
    model = build_model(params)
    env = environment(params, params.outside_temp_c)
    t_env = surroundings_end_of_snap(params, params.outside_temp_c)
    if t_env >= 0.0:
        return 0.0
    # Steady state T >= 0  <=>  d >= -g * T_env / T_supply
    d_needed = -model.conductance(env) * t_env / params.initial_water_temp_c
    m_dot = d_needed * DRIP_RUN_LENGTH_M / WATER_CP  # kg/s
    lpm = m_dot * 60.0 * 1000.0 / WATER_RHO
    return max(0.05, math.ceil(lpm / 0.05) * 0.05)


def describe_insulation(material: InsulationType, mm: float) -> str:
    return f"{mm:g} mm {INSULATION_MATERIALS[material]['label'].lower()}"
