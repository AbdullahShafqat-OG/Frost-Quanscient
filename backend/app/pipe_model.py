"""Two-node radial thermal model with axial water transport.

All material/environment values are representative fixed assumptions, not
installation-specific data. See assumptions() and README for the limits.
"""
import math
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

MODEL_VERSION = "exposed-pipe-3mps-v4"
# k [W/m K], rho [kg/m3], cp [J/kg K]: representative room-temperature values.
PIPE_MATERIALS = {
    "copper": {"k": 385.0, "rho": 8960.0, "cp": 385.0},
    "steel": {"k": 45.0, "rho": 7850.0, "cp": 470.0},
    "pvc": {"k": 0.19, "rho": 1400.0, "cp": 900.0},
    "pex": {"k": 0.40, "rho": 940.0, "cp": 2300.0},
}
INSULATION_MATERIALS = {
    "fiberglass": {"label": "Fiber glass", "k": 0.040},
    "foam_wrap": {"label": "Foam wrap", "k": 0.036},
    "mineral_wool": {"label": "Mineral wool", "k": 0.039},
    "none": {"label": "No insulation", "k": None},
}
WIND_SPEED = 3.0


class PipeParams(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    ambient_c: float = Field(-20, ge=-60, le=30)
    water_c: float = Field(10, gt=0, le=60)
    length_m: float = Field(20, ge=0.1, le=1000)
    diameter_mm: float = Field(25, ge=5, le=500)
    wall_mm: float = Field(2, ge=0.5, le=30)
    material: Literal["copper", "steel", "pvc", "pex"] = "copper"
    insulation_material: Literal["fiberglass", "foam_wrap", "mineral_wool", "none"] = "none"
    insulation_mm: float = Field(0, ge=0, le=200)
    flow_l_min: float = Field(0, ge=0, le=100)
    duration_h: float = Field(12, ge=0.1, le=168)

    @model_validator(mode="after")
    def normalize_insulation(self):
        if self.insulation_material == "none":
            self.insulation_mm = 0
        elif self.insulation_mm <= 0:
            raise ValueError("Choose a positive insulation thickness for the selected material.")
        return self


def air_coefficient(surface_c: float, ambient_c: float, diameter_m: float) -> float:
    """Churchill–Bernstein cylinder crossflow at 3 m/s + linearized radiation."""
    ts, ta = surface_c + 273.15, ambient_c + 273.15
    film = (ts + ta) / 2
    rho = 101325 / (287.05 * film)
    mu = 1.716e-5 * (film / 273.15) ** 1.5 * (273.15 + 111) / (film + 111)
    k = 0.0241 * (film / 273.15) ** 0.9
    nu, alpha = mu / rho, k / (rho * 1006)
    pr = nu / alpha
    re = WIND_SPEED * diameter_m / nu
    nusselt = (0.3 + 0.62 * math.sqrt(re) * pr ** (1 / 3) /
               (1 + (0.4 / pr) ** (2 / 3)) ** .25 *
               (1 + (re / 282000) ** (5 / 8)) ** (4 / 5))
    # Fixed emissivity: 0.8, representative of a dull/weathered surface.
    radiation = 0.8 * 5.670374419e-8 * (ts + ta) * (ts * ts + ta * ta)
    return nusselt * k / diameter_m + radiation


def coefficients(p: PipeParams) -> dict:
    ri = p.diameter_mm / 2000
    ro = ri + p.wall_mm / 1000
    rs = ro + p.insulation_mm / 1000
    material = PIPE_MATERIALS[p.material]
    insulation_k = INSULATION_MATERIALS[p.insulation_material]["k"]
    area = math.pi * ri ** 2
    velocity = p.flow_l_min / 60000 / area
    # Water properties at a representative cool liquid temperature.
    reynolds = 1000 * velocity * (2 * ri) / 0.0013
    # Fully developed laminar Nu; stagnant limit approximates radial conduction.
    nu_internal = 2.0 if velocity == 0 else 3.66
    if reynolds > 2300:
        turbulent_re = max(3000, reynolds)
        friction = (0.79 * math.log(turbulent_re) - 1.64) ** -2
        pr = 4184 * 0.0013 / 0.6
        turbulent = ((friction / 8) * (turbulent_re - 1000) * pr /
                     (1 + 12.7 * math.sqrt(friction / 8) * (pr ** (2 / 3) - 1)))
        blend = min(1, (reynolds - 2300) / 700)
        nu_internal = 3.66 * (1 - blend) + turbulent * blend
    h_internal = nu_internal * 0.6 / (2 * ri)
    r_internal = 1 / (2 * math.pi * ri * h_internal)
    r_pipe = math.log(ro / ri) / (2 * math.pi * material["k"])
    r_insulation = math.log(rs / ro) / (2 * math.pi * insulation_k) if insulation_k else 0
    reference_water = p.water_c / 2
    surface = reference_water
    for _ in range(30):
        h_external = air_coefficient(surface, p.ambient_c, 2 * rs)
        r_air = 1 / (2 * math.pi * rs * h_external)
        predicted = p.ambient_c + (reference_water - p.ambient_c) * r_air / (
            r_internal + r_pipe + r_insulation + r_air)
        surface = (surface + predicted) / 2
    r_external = 1 / (2 * math.pi * rs * h_external)
    r_water_wall = r_internal + r_pipe / 2
    r_wall_environment = r_pipe / 2 + r_insulation + r_external
    capacity_water = 1000 * 4184 * area
    capacity_wall = material["rho"] * material["cp"] * math.pi * (ro ** 2 - ri ** 2)
    resistance = r_water_wall + r_wall_environment
    return {"resistance": resistance, "area": area, "tau": capacity_water * resistance,
            "velocity": velocity, "capacity_water": capacity_water, "capacity_wall": capacity_wall,
            "g_water_wall": 1 / r_water_wall, "g_wall_environment": 1 / r_wall_environment,
            "r_internal": r_internal, "film_fraction": r_internal / r_water_wall,
            "h_internal": h_internal, "h_external": h_external, "reynolds": reynolds,
            "pipe_k": material["k"], "insulation_k": insulation_k}


def assumptions() -> list[str]:
    return [
        "Horizontal pipe continuously exposed to outside air at a fixed 3.0 m/s perpendicular crosswind.",
        "Outside temperature, drip rate and inlet temperature stay constant for the entire cold snap.",
        "Pipe wall and water start at the selected initial water temperature.",
        "Water and pipe wall have separate temperatures and heat capacities; each cross-section is represented by two uniform thermal nodes.",
        "Dry, intact insulation uses representative constant conductivity; insulation heat capacity, moisture and thermal bridges are omitted.",
        "Freezing onset is the estimated water / inner-wall interface reaching 0 °C at atmospheric pressure. Nucleation and supercooling are omitted. The calculation stops there; latent heat, ice growth, blockage and bursting are not modelled.",
        "Internal heat transfer uses a conduction approximation for stagnant water, fully developed laminar flow and a blended turbulent correlation.",
        "Radiation uses emissivity 0.8 and surroundings at outside temperature. Sun, rain, snow and colder sky radiation are omitted.",
        "External convection and radiation are estimated at an iterated surface temperature using a reference water temperature halfway to 0 °C, then held fixed during the run.",
        "The local model uses 160 axial finite-volume cells with implicit time stepping. The cloud model uses reduced axial FEM with stabilizing diffusion. Mesh and time-step errors remain.",
    ]


def critical_flow(p: PipeParams) -> float:
    """Solve steady inner-wall interface=0 with flow-dependent heat transfer."""
    if p.ambient_c >= 0:
        return 0.0
    def outlet(flow):
        c = coefficients(p.model_copy(update={"flow_l_min": flow}))
        r = c["resistance"]
        return p.ambient_c + (p.water_c - p.ambient_c) * math.exp(
            -p.length_m / (1000 * 4184 * flow / 60000 * r)) * (1 - c["r_internal"] / r)
    low, high = 0.0, 1.0
    while outlet(high) <= 0:
        high *= 2
    for _ in range(50):
        middle = (low + high) / 2
        if outlet(middle) > 0:
            high = middle
        else:
            low = middle
    return high


def simulate(p: PipeParams, cells: int = 160, time_refinement: float = 1.0) -> dict:
    """Implicit finite-volume water advection coupled to stationary wall nodes."""
    c = coefficients(p)
    n = cells if c["velocity"] else 1
    dx = p.length_m / n
    cw, cp = c["capacity_water"], c["capacity_wall"]
    gi, go = c["g_water_wall"], c["g_wall_environment"]
    advection = 1000 * 4184 * p.flow_l_min / 60000 / dx
    water, wall = [p.water_c] * n, [p.water_c] * n
    horizon = p.duration_h * 3600
    wall_time = cp / (gi + go)
    dt_base = min(60, horizon / 720, c["tau"] / 40, wall_time / 30) / time_refinement
    elapsed, freeze = 0.0, None
    film_fraction = c["film_fraction"]
    interface = [p.water_c] * n
    history = [{"hours": 0.0, "temperature_c": p.water_c, "interface_temperature_c": p.water_c}]
    sample_interval = min(horizon / 180, c["tau"] / 40)
    next_sample = sample_interval
    steady = False
    while elapsed < horizon:
        dt = min((min(600, horizon / 720) if steady else dt_base), horizon - elapsed)
        environment = p.ambient_c
        a, d = cw / dt + advection + gi, cp / dt + gi + go
        denominator = a - gi * gi / d
        new_water, new_wall = [], []
        upstream = p.water_c
        change = 0
        for i in range(n):
            rw = cw / dt * water[i] + advection * upstream
            rp = cp / dt * wall[i] + go * environment
            tw = (rw + gi * rp / d) / denominator
            tp = (rp + gi * tw) / d
            new_water.append(tw)
            new_wall.append(tp)
            change = max(change, abs(tw - water[i]), abs(tp - wall[i]))
            upstream = tw
        new_interface = [tw - film_fraction * (tw - tp) for tw, tp in zip(new_water, new_wall)]
        minimum = min(new_interface)
        if minimum <= 0:
            previous_min = min(interface)
            fraction = previous_min / (previous_min - minimum)
            elapsed += dt * fraction
            water = [old + fraction * (new - old) for old, new in zip(water, new_water)]
            wall = [old + fraction * (new - old) for old, new in zip(wall, new_wall)]
            freeze = elapsed / 3600
            interface = [old + fraction * (new - old) for old, new in zip(interface, new_interface)]
            history.append({"hours": freeze, "temperature_c": min(water), "interface_temperature_c": 0.0})
            break
        elapsed += dt
        water, wall, interface = new_water, new_wall, new_interface
        if elapsed >= next_sample or elapsed >= horizon:
            history.append({"hours": elapsed / 3600, "temperature_c": min(water),
                            "interface_temperature_c": minimum})
            next_sample = elapsed + sample_interval
        if change / dt < 1e-8:
            steady = True
    profile = ([{"distance_m": 0.0, "temperature_c": p.water_c}] +
               [{"distance_m": dx * (i + .5), "temperature_c": max(0, value)} for i, value in enumerate(water)] +
               [{"distance_m": p.length_m, "temperature_c": max(0, water[-1])}]
               if c["velocity"] else
               [{"distance_m": p.length_m * i / 40, "temperature_c": max(0, water[0])} for i in range(41)])
    return {
        "parameters": p.model_dump(), "engine": "estimate", "model_version": MODEL_VERSION,
        "risk": "freezing" if freeze is not None else ("near" if min(interface) < 2 else "above"),
        "freeze_hours": freeze, "end_hours": elapsed / 3600,
        "minimum_c": max(0, min(water)), "minimum_wall_c": min(wall),
        "minimum_interface_c": max(0, min(interface)),
        "critical_flow_l_min": critical_flow(p),
        "flow_threshold_note": "Flow must exceed this estimate to keep the inner-wall interface above 0 °C at steady state. It does not predict ice growth or blockage.",
        "residence_minutes": p.length_m / c["velocity"] / 60 if c["velocity"] else None,
        "environment": {
            "wind_m_s": WIND_SPEED, "external_h_w_m2k": c["h_external"],
            "internal_h_w_m2k": c["h_internal"], "reynolds": c["reynolds"],
            "pipe_k_w_mk": c["pipe_k"], "insulation_k_w_mk": c["insulation_k"],
        },
        "assumptions": assumptions(), "history": history, "profile": profile,
    }

