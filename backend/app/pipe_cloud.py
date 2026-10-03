"""Allsolve workflow. One persistent project/cache per parameter set."""
import hashlib
import json
import logging
from pathlib import Path
from .pipe_model import PipeParams, coefficients, simulate, MODEL_VERSION

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "sim" / "pipe_freezing" / "heat_transfer.py"
logger = logging.getLogger("frost.allsolve")


class CloudRunError(RuntimeError):
    """A safe, actionable cloud error that can be shown in the interface."""


def scenario_fingerprint(params):
    model_source = Path(__file__).with_name("pipe_model.py").read_text(encoding="utf-8")
    return hashlib.sha256((params.model_dump_json() + SCRIPT.read_text(encoding="utf-8")
                           + model_source + MODEL_VERSION).encode()).hexdigest()[:20]


def extract_results(values, params, project_url):
    """Sort cloud output and interpolate all temperatures to first interface onset."""
    result = simulate(params)
    rows = []
    for key, row in values.items():
        try:
            seconds = float(key)
        except (ValueError, TypeError):
            continue
        if "T_min_water" not in row:
            continue
        def scalar(value):
            return float(value[0] if isinstance(value, (list, tuple)) else value)
        rows.append((seconds, scalar(row["T_min_water"]),
                     scalar(row["T_min_interface"]), scalar(row["T_min_wall"]), row))
    rows.sort(key=lambda r: r[0])
    if not rows:
        raise RuntimeError("Allsolve returned no water-temperature results.")
    history = []
    freeze = None
    last_row = rows[-1][4]
    previous_row = None
    profile_fraction = None
    wall_minimum = rows[-1][3]
    for seconds, bulk, interface, wall, row in rows:
        if interface <= 0 and history:
            prev = history[-1]
            fraction = prev["interface_temperature_c"] / (prev["interface_temperature_c"] - interface)
            freeze = prev["hours"] + fraction * (seconds / 3600 - prev["hours"])
            water_at_onset = prev["temperature_c"] + fraction * (bulk - prev["temperature_c"])
            history.append({"hours": freeze, "temperature_c": water_at_onset,
                            "interface_temperature_c": 0.0})
            wall_minimum = previous_wall + fraction * (wall - previous_wall)
            last_row, profile_fraction = row, fraction
            break
        history.append({"hours": seconds / 3600, "temperature_c": bulk,
                        "interface_temperature_c": interface})
        previous_row, previous_wall = row, wall
    if freeze is None and rows[-1][0] < params.duration_h * 3600 - 1:
        raise RuntimeError("Allsolve output ended before the requested exposure.")
    profile = []
    for i in range(41):
        key = "profile_" + str(i)
        value = scalar(last_row[key])
        if profile_fraction is not None:
            previous = scalar(previous_row[key])
            value = previous + profile_fraction * (value - previous)
        profile.append({"distance_m": params.length_m * i / 40, "temperature_c": value})
    result.update(engine="allsolve", project_url=project_url, history=history,
                  freeze_hours=freeze, end_hours=history[-1]["hours"],
                  minimum_c=history[-1]["temperature_c"], minimum_wall_c=wall_minimum,
                  minimum_interface_c=history[-1]["interface_temperature_c"],
                  risk="freezing" if freeze is not None else
                  ("near" if history[-1]["interface_temperature_c"] < 2 else "above"),
                  profile=profile)
    return result


def run_cloud(params: PipeParams, progress):
    try:
        import allsolve
    except ImportError as exc:
        raise CloudRunError("Install the Allsolve SDK in the backend environment to use cloud FEM.") from exc
    fingerprint = scenario_fingerprint(params)
    cache = ROOT / ".allsolve_cache" / "pipe" / fingerprint
    cache.mkdir(parents=True, exist_ok=True)
    result_file = cache / "result.json"
    state_file = cache / "project.json"
    if result_file.exists():
        logger.info("Using cached Allsolve result: %s (no new cloud request)", fingerprint)
        return json.loads(result_file.read_text(encoding="utf-8"))
    dotenv = ROOT / ".env"
    try:
        client = allsolve.Client(dotenv_file=str(dotenv) if dotenv.exists() else None,
                                cache_base_dir=str(cache), _set_as_default=False)
    except ValueError as exc:
        raise CloudRunError("Allsolve is not configured or could not authenticate. Set ALLSOLVE_ACCESS_KEY "
                            "and ALLSOLVE_SECRET_KEY in backend/.env, then run again.") from exc
    with client:
        logger.info("Connected to Allsolve host: %s; scenario: %s", client.host, fingerprint)
        if state_file.exists():
            state = json.loads(state_file.read_text(encoding="utf-8"))
            project = client.get_project(state["project_id"])
            sims = project.get_simulations()
            if sims and sims[0].get_status() == allsolve.Job.SUCCESS:
                result = extract_results(sims[0].get_output_values(refresh=True),
                                         params, client.get_url(project))
                result_file.write_text(json.dumps(result), encoding="utf-8")
                return result
            raise CloudRunError("This Allsolve project already exists and is incomplete. "
                               "Inspect it in Allsolve before rerunning: " + client.get_url(project))
        quota = client.get_quota()
        if quota.total_running_cores + 3 > quota.max_concurrent_cores:
            raise CloudRunError("Allsolve compute quota is busy. Try again when capacity is free.")
        c = coefficients(params)
        dt = min(60, params.duration_h * 3600 / 720, c["tau"] / 40,
                 c["capacity_wall"] / (c["g_water_wall"] + c["g_wall_environment"]) / 30)
        progress("Building Allsolve pipe model", 10)
        project = client.create_project(name="Frost pipe " + fingerprint[:8], dimension=2,
            description="Coupled water/wall thermal model, prescribed flow, derived external heat transfer and location assumptions.")
        state_file.write_text(json.dumps({"project_id": project.id}), encoding="utf-8")
        variables = {"T_initial": params.water_c + 273.15,
                     "T_ambient": params.ambient_c + 273.15,
                     "length": params.length_m, "velocity": c["velocity"],
                     "rate_water": c["g_water_wall"] / c["capacity_water"],
                     "rate_wall": c["g_water_wall"] / c["capacity_wall"],
                     "rate_environment": c["g_wall_environment"] / c["capacity_wall"],
                     "film_fraction": c["film_fraction"],
                     "dt_steady": min(600, params.duration_h * 3600 / 720),
                     "t_end": params.duration_h * 3600, "dt": dt}
        project.create_variables([(k, str(v), k) for k, v in variables.items()])
        builder = project.geometry_builder()
        builder.add_rectangle(name="axial_domain", position=(0, 0),
                              size=(1, 0.02), alignment=allsolve.CadAlignment.CORNER)
        builder.build(print_logs=True, on_error=allsolve.OnError.STRICT)
        water = project.create_region_rule(name="water", entity_type=allsolve.Region.SURFACE,
                                            bounding_box=((-1e-6, -1e-6, -1e-6), (1.000001, .020001, 1e-6)))
        project.create_region_rule(name="inlet", entity_type=allsolve.Region.CURVE,
                                   bounding_box=((-1e-6, -1e-6, -1e-6), (1e-6, .020001, 1e-6)))
        project.create_material(name="Water", target_region=water, density=1000,
                                heat_capacity=4184, thermal_conductivity=0.6)
        physics = project.get_default_physics_set()
        physics.add_physics(allsolve.Physics.HeatTransfer())
        mesh = project.create_mesh(allsolve.MeshSettings(name="Axial mesh",
            mesh_size_min=1 / 240, mesh_size_max=1 / 120,
            max_run_time_minutes=10, use_mesh_refiner=False))
        progress("Meshing in Allsolve", 30)
        mesh.run(print_logs=True, on_error=allsolve.OnError.STRICT)
        sim = project.create_simulation_transient(name="Pipe freezing onset",
            description="Prescribed-flow reduced thermal FEM", max_run_time_minutes=15,
            mesh=mesh, physics_set=physics,
            timestep_algorithm=allsolve.TimestepAlgorithm.IMPLICIT_EULER,
            transient_start_time="0", transient_end_time="t_end", transient_timestep_size="dt")
        sim.set_scripts([allsolve.Script(name=SCRIPT.name,
            content=SCRIPT.read_text(encoding="utf-8"), is_main=True)])
        sim.set_runtime(allsolve.Runtime(node_type=allsolve.CPU.CORES_3_10GB_FAST_START))
        sim.save()
        progress("Solving temperature transport in Allsolve", 60)
        sim.run(print_logs=True, on_error=allsolve.OnError.STRICT)
        progress("Reading water temperatures", 95)
        result = extract_results(sim.get_output_values(refresh=True), params, client.get_url(project))
        result_file.write_text(json.dumps(result), encoding="utf-8")
        return result

