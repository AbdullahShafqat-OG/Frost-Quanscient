"""
What the pipe sees from outside, per location.

The user only gives the outside air temperature. Each location has fixed
surroundings, and the external heat transfer coefficient h is estimated from
the location and that temperature (it is not a user input):

- Outdoors:    pipe exposed to outside air; forced convection at a fixed wind
               speed (or natural convection if stronger) + radiation.
- Indoors:     pipe in a wall cavity / unheated space whose air temperature
               sits between the heated interior and outside; still air.
- Underground: pipe at a fixed depth in a fixed soil; the soil at that depth
               cools as the cold soaks down from the surface (semi-infinite
               solid, surface stepped to the outside temperature), and heat
               leaves the pipe through the soil's conduction resistance.
"""

import math
from dataclasses import dataclass

from ..models.pipe_params import (
    DRIP_RUN_LENGTH_M,
    Location,
    PipeParams,
)

SIGMA = 5.670e-8  # W/(m²·K⁴)
EMISSIVITY = 0.9  # Oxidised metal, plastic and insulation jackets are all ~0.9

OUTDOOR_WIND_MS = 3.0  # Typical winter wind

INDOOR_TEMP_C = 20.0  # Building heated as normal
INDOOR_COUPLING = 0.3  # Space temperature = outside + 0.3 × (indoor − outside)

BURIAL_DEPTH_M = 0.45  # Pipe centre depth
SOIL_K = 1.0  # W/(m·K), moist loam
SOIL_RHO_CP = 2.0e6  # J/(m³·K), moist loam
SOIL_ALPHA = SOIL_K / SOIL_RHO_CP  # m²/s
GROUND_TEMP_C = 5.0  # Soil temperature before the cold snap


@dataclass
class Environment:
    location: Location
    h: float  # W/(m²·K), referred to the pipe's outer surface
    t_env_c: float  # Constant surroundings, or the ground surface for underground


def h_natural(delta_t: float, diameter: float) -> float:
    """Natural convection from a horizontal cylinder in still air (simplified laminar)."""
    return 1.32 * (max(abs(delta_t), 1.0) / diameter) ** 0.25


def h_radiation(t_env_c: float) -> float:
    """Linearised radiation between a ~0 °C surface and surroundings at t_env_c."""
    t_mean = (273.15 + (t_env_c + 273.15)) / 2.0
    return 4.0 * EMISSIVITY * SIGMA * t_mean**3


def environment(params: PipeParams, outside_c: float) -> Environment:
    """Surroundings and estimated h for a given outside temperature.

    Convection and radiation are evaluated with the pipe surface at ~0 °C,
    the temperature that matters while the water is freezing.
    """
    r_o = params.r_outer
    diameter = 2.0 * r_o

    if params.location == Location.OUTDOORS:
        h_conv = max(h_natural(outside_c, diameter), 3.8 * OUTDOOR_WIND_MS)
        return Environment(params.location, h_conv + h_radiation(outside_c), outside_c)

    if params.location == Location.INDOORS:
        t_space = outside_c + INDOOR_COUPLING * (INDOOR_TEMP_C - outside_c)
        h = h_natural(t_space, diameter) + h_radiation(t_space)
        return Environment(params.location, h, t_space)

    # Underground: buried-cylinder conduction shape factor, R' = ln(2z/r_o)/(2π k),
    # expressed as an equivalent h on the outer surface: h = k / (r_o ln(2z/r_o))
    h = SOIL_K / (r_o * math.log(2.0 * BURIAL_DEPTH_M / r_o))
    return Environment(params.location, h, outside_c)


def surroundings_at(env: Environment, hours: float) -> float:
    """Temperature (°C) the pipe exchanges heat with, `hours` into the cold snap."""
    if env.location != Location.UNDERGROUND:
        return env.t_env_c
    if hours <= 0.0:
        return GROUND_TEMP_C
    x = BURIAL_DEPTH_M / (2.0 * math.sqrt(SOIL_ALPHA * hours * 3600.0))
    return GROUND_TEMP_C + (env.t_env_c - GROUND_TEMP_C) * math.erfc(x)


def assumptions(params: PipeParams) -> list[str]:
    """Fixed conditions behind the analysis, for display."""
    common = []
    if params.drip_flow_lpm > 0:
        common.append(
            f"The drip draws water at the initial water temperature and serves a "
            f"{DRIP_RUN_LENGTH_M:g} m cold run."
        )

    if params.location == Location.OUTDOORS:
        return [
            "Pipe exposed to outside air at the given temperature.",
            f"Constant {OUTDOOR_WIND_MS:g} m/s wind (forced convection) plus radiation to the "
            "air temperature; no sun, no clear-night-sky cooling.",
        ] + common
    if params.location == Location.INDOORS:
        return [
            f"Building heated to {INDOOR_TEMP_C:g} °C throughout the cold snap.",
            f"Pipe in a wall cavity or unheated space whose air sits "
            f"{INDOOR_COUPLING * 100:.0f}% of the way from outside to indoor temperature.",
            "Still air: natural convection plus radiation to that space.",
        ] + common
    return [
        f"Pipe buried {BURIAL_DEPTH_M:g} m deep in moist loam (k = {SOIL_K:g} W/m·K), "
        f"soil initially at {GROUND_TEMP_C:g} °C.",
        "Ground surface drops to the outside temperature at once (no snow or turf insulation).",
        "Soil at pipe depth follows the 1D cold wave from the surface; the soil itself "
        "does not freeze (no soil latent heat), which is conservative.",
    ] + common
