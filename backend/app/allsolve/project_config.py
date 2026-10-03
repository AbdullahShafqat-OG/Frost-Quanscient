"""Generate Allsolve project configuration from pipe parameters."""

import math
from typing import Any
from ..models.pipe_params import (
    DRIP_RUN_LENGTH_M,
    Location,
    PipeParams,
    WATER_CP,
    WATER_K,
    WATER_RHO,
)
from ..analysis.environment import BURIAL_DEPTH_M, GROUND_TEMP_C, SOIL_ALPHA, environment

# Segment length as a multiple of the outer diameter. Ends are adiabatic, so
# the result doesn't depend on it; it only needs to give a sane mesh.
SEGMENT_LENGTH_FACTOR = 3.0


def sweep_variables(params: PipeParams, outside_c: float) -> dict[str, float]:
    """Project variables that change with the outside temperature.

    T_amb: outside air [K] (identifies the sweep step)
    T_env: surroundings [K]; for underground, the ground surface temperature
    h_out: estimated external heat transfer coefficient [W/(m²·K)]
    """
    surroundings = environment(params, outside_c)
    return {
        "T_amb": round(outside_c + 273.15, 6),
        "T_env": round(surroundings.t_env_c + 273.15, 6),
        "h_out": round(surroundings.h, 6),
    }


def simulation_timing(params: PipeParams) -> dict[str, float]:
    """End time, timestep and output interval in seconds."""
    t_end = params.window_hours * 3600.0
    dt = min(max(t_end / 1500.0, 10.0), 30.0)
    dt_out = dt * max(1, round(t_end / 240.0 / dt))
    return {"t_end": t_end, "dt": dt, "dt_out": dt_out}


def generate_project_config(params: PipeParams) -> dict[str, Any]:
    """
    Generate an Allsolve project configuration dictionary from pipe parameters.

    This creates a complete project configuration including:
    - Concentric-cylinder geometry (water / pipe wall / insulation)
    - Region definitions (volumes and the lateral outer surface)
    - Material definitions
    - Variables used by the simulation script (sim/pipe_freeze.py)
    - Coarse mesh settings

    Args:
        params: User-specified pipe parameters

    Returns:
        Dictionary that can be passed to allsolve.import_project()
    """
    r_i, r_w, r_o = params.r_inner, params.r_wall, params.r_outer
    seg_len = SEGMENT_LENGTH_FACTOR * 2.0 * r_o
    timing = simulation_timing(params)

    insulation_label = (
        f"{params.insulation_thickness_mm:g} mm {params.insulation.value}"
        if params.has_insulation
        else "bare"
    )

    config = {
        "name": (
            f"Pipe Freeze - {params.inner_diameter_mm:g} mm {params.pipe_material.value}, "
            f"{insulation_label}, {params.location.value}"
        ),
        "description": (
            f"Freeze-risk analysis: water at {params.initial_water_temp_c:g}°C in a "
            f"{params.pipe_material.value} pipe {params.location.value}, "
            f"{params.outside_temp_c:g}°C outside"
        ),
        "dimension": 3,
        "verbose": True,
        "labels": ["pipe-freeze", "heat-transfer"],
        "geometries": _generate_geometries(params, seg_len),
        "regions": _generate_regions(params, seg_len),
        "variables": [
            # Geometry (for reference in the project)
            {"name": "r_inner", "expression": r_i},
            {"name": "r_wall", "expression": r_w},
            {"name": "r_outer", "expression": r_o},
            {"name": "seg_len", "expression": seg_len},
            # Outside conditions (swept together, see sweep_variables)
            *[
                {"name": name, "expression": value}
                for name, value in sweep_variables(params, params.outside_temp_c).items()
            ],
            # Underground: surroundings follow the cold wave into the soil
            {"name": "underground", "expression": int(params.location == Location.UNDERGROUND)},
            {"name": "z_burial", "expression": BURIAL_DEPTH_M},
            {"name": "alpha_soil", "expression": SOIL_ALPHA},
            {"name": "T_ground0", "expression": GROUND_TEMP_C + 273.15},
            # Water
            {"name": "T_init", "expression": params.initial_water_temp_c + 273.15},
            {"name": "T_supply", "expression": params.initial_water_temp_c + 273.15},
            # Drip flow: m_dot [kg/s] spread over the water in the cold run
            {"name": "m_dot", "expression": params.m_dot},
            {"name": "L_exposed", "expression": DRIP_RUN_LENGTH_M},
            {"name": "A_water", "expression": math.pi * r_i**2},
            # Simulation control
            {"name": "t_end", "expression": timing["t_end"]},
            {"name": "dt", "expression": timing["dt"]},
            {"name": "dt_out", "expression": timing["dt_out"]},
        ],
        "materials": _generate_materials(params),
        # Mesh configuration - keep it coarse for fast simulation
        "meshes": [
            {
                "name": "pipe_mesh",
                "nodeType": "lambda",  # Fast starting nodes
                "scaleFactor": 1.0,
                "useMeshRefiner": False,
                "curvedMesh": False,
                "curvatureEnhancement": 1,
                "maxRunTimeMinutes": 10,
                "meshSizeMin": 0.5 * (r_w - r_i),
                "meshSizeMax": r_o,
                "refinements": _generate_refinements(params),
            }
        ],
    }

    return config


def _generate_geometries(params: PipeParams, seg_len: float) -> list[dict]:
    """Concentric cylinders along z, centred on the origin.

    In Allsolve, cylinder 'position' is the centre of the cylinder volume and
    'axis' is the full height vector. After fragmentAll each outer cylinder
    still carries the inner fragments under its name, so the shells are
    isolated with computed 'difference' regions.
    """

    def cylinder(name: str, radius: float) -> dict:
        return {
            "type": "cylinder",
            "name": name,
            "position": {"x": 0, "y": 0, "z": 0},
            "axis": {"x": 0, "y": 0, "z": seg_len},
            "radius": radius,
        }

    geometries = [
        cylinder("water_cyl", params.r_inner),
        cylinder("wall_cyl", params.r_wall),
    ]
    if params.has_insulation:
        geometries.append(cylinder("insulation_cyl", params.r_outer))
    geometries.append({"type": "fragmentAll", "name": "partition_geometry"})
    return geometries


def _name_rule(name: str, cad_name: str) -> dict:
    return {
        "name": name,
        "type": "regionRule",
        "entityType": "volume",
        "attributePath": [{"key": "name", "value": cad_name}],
    }


def _computed(name: str, entity_type: str, operation: str, regions: list[str]) -> dict:
    return {
        "name": name,
        "type": "computed",
        "entityType": entity_type,
        "operation": operation,
        "regions": regions,
    }


def _end_cap_rule(name: str, z: float, r_box: float, eps: float) -> dict:
    """Surfaces lying in the plane z (the flat end of the segment)."""
    return {
        "name": name,
        "type": "regionRule",
        "entityType": "surface",
        "boundingBox": {
            "min": {"x": -r_box, "y": -r_box, "z": z - eps},
            "max": {"x": r_box, "y": r_box, "z": z + eps},
        },
    }


def _generate_regions(params: PipeParams, seg_len: float) -> list[dict]:
    """Volume regions water / wall / insulation, plus the lateral outer surface.

    The convective BC goes on `outer_surface` only; the end caps get no BC,
    i.e. zero flux (adiabatic), so the segment behaves like an infinitely long pipe.
    """
    regions = [
        _name_rule("water", "water_cyl"),
        _name_rule("wall_all", "wall_cyl"),
        _computed("wall", "volume", "difference", ["wall_all", "water"]),
    ]
    if params.has_insulation:
        regions += [
            _name_rule("insulation_all", "insulation_cyl"),
            _computed("insulation", "volume", "difference", ["insulation_all", "wall_all"]),
            _computed("solid", "volume", "union", ["wall", "insulation"]),
        ]
    else:
        regions.append(_computed("solid", "volume", "difference", ["wall_all", "water"]))

    r_box = 1.5 * params.r_outer
    eps = 0.01 * seg_len
    regions += [
        _computed("all_domain", "volume", "union", ["water", "solid"]),
        _computed("outer_boundary", "surface", "boundary", ["all_domain"]),
        _end_cap_rule("end_cap_top", seg_len / 2.0, r_box, eps),
        _end_cap_rule("end_cap_bottom", -seg_len / 2.0, r_box, eps),
        _computed("end_caps", "surface", "union", ["end_cap_top", "end_cap_bottom"]),
        _computed("outer_surface", "surface", "difference", ["outer_boundary", "end_caps"]),
    ]
    return regions


def _generate_materials(params: PipeParams) -> list[dict]:
    """Materials. The script replaces the water properties with the freezing model."""
    pipe = params.pipe_props()
    materials = [
        {
            "name": "Water",
            "target": "water",
            "color": "#38BDF8",
            "description": "Stagnant water (freezing handled in the simulation script)",
            "density": WATER_RHO,
            "thermalConductivity": WATER_K,
            "heatCapacity": WATER_CP,
        },
        {
            "name": pipe["label"],
            "target": "wall",
            "color": "#B87333",
            "description": f"{pipe['label']} pipe wall",
            "density": pipe["rho"],
            "thermalConductivity": pipe["k"],
            "heatCapacity": pipe["cp"],
        },
    ]
    ins = params.insulation_props()
    if ins:
        materials.append(
            {
                "name": f"{ins['label']} insulation",
                "target": "insulation",
                "color": "#9CA3AF",
                "description": f"{ins['label']} pipe insulation",
                "density": ins["rho"],
                "thermalConductivity": ins["k"],
                "heatCapacity": ins["cp"],
            }
        )
    return materials


def _generate_refinements(params: PipeParams) -> list[dict]:
    wall_t = params.r_wall - params.r_inner
    refinements = [
        {"region": "water", "maxSize": params.r_inner / 2.5},
        {"region": "wall", "maxSize": max(1.5 * wall_t, params.r_inner / 5.0)},
    ]
    if params.has_insulation:
        ins_t = params.r_outer - params.r_wall
        refinements.append(
            {"region": "insulation", "maxSize": max(ins_t / 2.0, params.r_outer / 4.0)}
        )
    return refinements
