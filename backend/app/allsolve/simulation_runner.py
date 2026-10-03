"""Allsolve simulation runner for pipe freeze-risk analyses."""

import io
import re
import logging
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable, List, Dict
from pathlib import Path

from ..config import get_settings
from ..models.pipe_params import AnalysisResults, PipeParams, SeriesPoint, SweepPoint
from ..analysis import build_results, detect_events, sweep_ambients
from .project_config import generate_project_config, simulation_timing, sweep_variables

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Import allsolve conditionally to allow running without the SDK (demo mode)
try:
    import allsolve

    ALLSOLVE_AVAILABLE = True
    logger.info("✅ Allsolve SDK imported successfully")
except ImportError as e:
    ALLSOLVE_AVAILABLE = False
    allsolve = None
    logger.warning(f"⚠️ Allsolve SDK not available: {e}")

SCRIPT_PATH = Path(__file__).parent.parent.parent / "sim" / "pipe_freeze.py"
OUTPUT_KEYS = ("T_min_water", "T_avg_water", "T_max_water", "ice_fraction")

ProgressCallback = Callable[[str, float], None]


class SweepParseError(RuntimeError):
    """Sweep outputs could not be mapped back to ambient temperatures."""


class AbortedError(RuntimeError):
    """The analysis was aborted by the user."""


class _ProjectRun:
    """
    One Allsolve project for a set of ambient temperatures.

    Handles the lifecycle: import project, wait for geometry and mesh,
    create the simulation (with an ambient-temperature sweep if more than one
    temperature), run it, and read back the series per ambient temperature.
    """

    def __init__(self, params: PipeParams, ambients_c: List[float], label: str):
        self.params = params
        self.ambients_c = ambients_c
        self.label = label
        self.aborted = False
        self.failed = False
        self._log_tail: deque[str] = deque(maxlen=60)
        self._project = None
        self._simulation = None
        self._mesh = None

    def run(self, update_progress: ProgressCallback) -> Dict[float, List[SeriesPoint]]:
        # Single temperature: bake it into the project instead of overriding
        params = self.params
        if len(self.ambients_c) == 1:
            params = params.model_copy(update={"outside_temp_c": self.ambients_c[0]})

        # Generate project configuration
        update_progress("Generating project configuration...", 5)
        logger.info(f"📝 [{self.label}] Generating project configuration...")
        config = generate_project_config(params)

        # Import project
        update_progress("Creating project in Allsolve...", 10)
        logger.info(f"☁️ [{self.label}] Creating project in Quanscient Allsolve cloud...")
        self._project = allsolve.import_project(config)
        logger.info(f"✅ [{self.label}] Project created: ID={self._project.id}")
        self._check_aborted()

        # Wait for geometry processing
        update_progress("Processing geometry...", 20)
        geometries = self._project.get_geometry()
        if geometries:
            for geom in geometries:
                logger.info(f"   Waiting for geometry '{geom.name}' to process...")
                while geom.is_running(refresh_delay_s=1):
                    self._check_aborted()
                logger.info(f"   ✅ Geometry '{geom.name}' processed")
        else:
            logger.warning("   ⚠️ No geometries found in project")

        # Get mesh
        update_progress("Waiting for mesh...", 30)
        meshes = self._project.get_meshes()
        if meshes:
            self._mesh = meshes[0]
            logger.info(f"   Found mesh (ID={self._mesh.id})")
            while self._mesh.is_running(refresh_delay_s=2):
                self._check_aborted()
                update_progress("Meshing in progress...", 40)
                self._mesh.print_new_loglines()
            logger.info("   ✅ Mesh generation complete")
        else:
            logger.warning("   ⚠️ No meshes found in project")

        # Outside temperature sweep (one cloud job for all temperatures).
        # T_env and h_out depend on the outside temperature, so they are
        # overridden in lockstep (SPECIFIC_VALUES pairs values by index).
        sweep_id = None
        if len(self.ambients_c) > 1:
            update_progress("Setting up outside temperature sweep...", 45)
            per_point = [sweep_variables(params, t) for t in self.ambients_c]
            sweep = allsolve.VariableOverrides.create(
                name="ambient_sweep",
                overrides=[(name, [p[name] for p in per_point]) for name in per_point[0]],
                project_id=self._project.id,
            )
            sweep_id = sweep.id
            logger.info(f"   ✅ Sweep created over T_amb = {self.ambients_c} °C")

        # Create simulation
        update_progress("Setting up simulation...", 50)
        logger.info(f"⚙️ [{self.label}] Setting up simulation...")
        self._simulation = allsolve.Simulation.create(
            name="Pipe Freeze",
            description="Transient pipe freezing (apparent heat capacity)",
            max_run_time_minutes=get_settings().sim_max_run_time_minutes,
            solver_mode=allsolve.SolverMode.DIRECT,
            mesh_id=self._mesh.id if self._mesh else None,
            variable_overrides_id=sweep_id,
            project_id=self._project.id,
        )
        logger.info(f"   ✅ Simulation created: ID={self._simulation.id}")

        self._simulation.set_runtime(
            allsolve.Runtime(
                node_type=allsolve.CPU.CORES_3_10GB_FAST_START,
                node_count=1,
            )
        )
        logger.info(f"   Setting simulation script: {SCRIPT_PATH}")
        self._simulation.set_scripts(
            [
                allsolve.Script(
                    # Read as UTF-8 ourselves: the SDK uses the locale
                    # codec (cp1252 on Windows) and chokes on 'ρ' etc.
                    content=SCRIPT_PATH.read_text(encoding="utf-8"),
                    name=SCRIPT_PATH.name,
                    is_main=True,
                ),
            ]
        )
        self._simulation.mesh_id = self._mesh.id if self._mesh else None
        self._simulation.save()
        self._check_aborted()

        # Start simulation
        update_progress("Running simulation...", 60)
        logger.info(f"🚀 [{self.label}] Starting simulation {self._simulation.id}")
        self._simulation.start()
        self._poll(params, update_progress)

        self._drain_logs()  # Fetch the tail: errors/tracebacks come last
        status = self._simulation.get_status()
        logger.info(f"   Final status: {status}")
        self._check_aborted()
        if status != allsolve.Job.SUCCESS:
            self.failed = True
            raise RuntimeError(
                f"Simulation failed with status: {status}. Solver log:\n{self._error_excerpt()}"
            )

        update_progress("Retrieving results...", 98)
        return self._read_outputs()

    def _poll(self, params: PipeParams, update_progress: ProgressCallback) -> None:
        """Wait for completion, parsing logs for progress across sweep points."""
        t_end = simulation_timing(params)["t_end"]
        n_points = len(self.ambients_c)
        time_pattern = re.compile(r"t=(\d+(?:\.\d+)?)s:")
        done, current_t = 0, 0.0

        while self._simulation.is_running(refresh_delay_s=3):
            for line in self._drain_logs():
                match = time_pattern.search(line)
                if match:
                    current_t = float(match.group(1))
                if "Analysis point complete" in line:
                    done, current_t = done + 1, 0.0

            fraction = min((done + min(current_t / t_end, 1.0)) / n_points, 1.0)
            point = f"point {min(done + 1, n_points)}/{n_points}, " if n_points > 1 else ""
            update_progress(
                f"Simulating... {point}{current_t / 3600:.1f} h / {t_end / 3600:.0f} h",
                min(60 + 35 * fraction, 95),
            )

    def _drain_logs(self) -> List[str]:
        """Fetch all new solver log lines (the SDK returns at most 100 per call)."""
        lines: List[str] = []
        for _ in range(100):  # Safety cap: 10k lines per drain
            buffer = io.StringIO()
            self._simulation.print_new_loglines(buffer, limit=100)
            chunk = [line for line in buffer.getvalue().splitlines() if line.strip()]
            if not chunk:
                break
            for line in chunk:
                logger.info(f"   [SIM {self.label}] {line}")
            lines.extend(chunk)
        self._log_tail.extend(lines)
        return lines

    def _error_excerpt(self, max_lines: int = 25) -> str:
        """The solver's traceback if there is one, else the last log lines."""
        tail = list(self._log_tail)
        for i, line in enumerate(tail):
            if "Traceback" in line or "Error" in line:
                return "\n".join(tail[i : i + max_lines])
        return "\n".join(tail[-max_lines:]) or "(no log lines received)"

    def _read_outputs(self) -> Dict[float, List[SeriesPoint]]:
        """Series per ambient temperature (°C)."""
        output_data = self._simulation.get_output_data(refresh=True)
        n_sweeps = output_data.get_sweep_count()
        logger.info(f"   Sweep steps in output: {n_sweeps} (expected {len(self.ambients_c)})")
        if n_sweeps != len(self.ambients_c):
            raise SweepParseError(
                f"Expected {len(self.ambients_c)} sweep steps, got {n_sweeps}"
            )

        try:
            overrides = output_data.get_sweep_step_overrides()
        except Exception as e:
            logger.warning(f"   Could not read sweep overrides ({e}); assuming sweep order")
            overrides = []

        results: Dict[float, List[SeriesPoint]] = {}
        for si in range(n_sweeps):
            ambient = self.ambients_c[si]  # SPECIFIC_VALUES keeps the given order
            t_amb_k = (overrides[si].get("T_amb") or [None])[0] if si < len(overrides) else None
            if t_amb_k is not None:
                ambient = min(self.ambients_c, key=lambda a: abs(a - (t_amb_k - 273.15)))

            series = _series_from_steps(output_data.to_dict(si))
            if not series:
                raise SweepParseError(f"No water outputs found for sweep step {si}")
            results[ambient] = series

        if len(results) != len(self.ambients_c):
            raise SweepParseError("Sweep steps did not map one-to-one onto ambient temperatures")
        return results

    def _check_aborted(self) -> None:
        if self.aborted:
            raise AbortedError("Analysis aborted by user")

    def abort(self) -> bool:
        """Abort all running jobs (geometry, mesh, simulation)."""
        self.aborted = True
        aborted = False

        if self._simulation:
            try:
                logger.info(f"🛑 [{self.label}] Aborting simulation...")
                self._simulation.abort()
                aborted = True
            except Exception as e:
                logger.warning(f"   Failed to abort simulation: {e}")

        if self._mesh:
            try:
                logger.info(f"🛑 [{self.label}] Aborting mesh...")
                self._mesh.abort()
                aborted = True
            except Exception as e:
                logger.warning(f"   Failed to abort mesh: {e}")

        if self._project:
            try:
                for geom in self._project.get_geometry() or []:
                    try:
                        geom.abort()
                        aborted = True
                    except Exception as e:
                        logger.warning(f"   Failed to abort geometry '{geom.name}': {e}")
            except Exception as e:
                logger.warning(f"   Failed to get geometries for abort: {e}")

        return aborted

    def cleanup(self) -> None:
        """Delete the project and everything in it."""
        settings = get_settings()
        if self._project and settings.keep_projects:
            url = f"{settings.qs_host.rstrip('/')}/#/projects/{self._project.id}"
            logger.info(f"   Keeping project {self._project.id} (KEEP_PROJECTS=true): {url}")
            self._project = None
            return
        if self._project and self.failed and settings.keep_failed_projects:
            url = f"{settings.qs_host.rstrip('/')}/#/projects/{self._project.id}"
            logger.warning(
                f"   Keeping failed project {self._project.id} for inspection "
                f"(KEEP_FAILED_PROJECTS=true): {url}"
            )
            self._project = None
            return
        if self._project:
            try:
                logger.info(f"🧹 [{self.label}] Deleting project {self._project.id}")
                self._project.delete()
            except Exception as e:
                logger.warning(f"   Failed to delete project: {e}")
            self._project = None
            self._simulation = None
            self._mesh = None


def _unwrap(value) -> float:
    """Output values may come back as [x] instead of x."""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else 0.0
    return float(value)


def _series_from_steps(steps: dict) -> List[SeriesPoint]:
    """Convert {step_time_s: {name: value}} output values into a sorted series."""
    series = []
    for step_key, values in steps.items():
        if step_key == "nostep" or not all(k in values for k in OUTPUT_KEYS):
            continue
        try:
            time_s = float(step_key)
        except ValueError:
            continue
        series.append(
            SeriesPoint(
                time_hours=time_s / 3600.0,
                t_min_water_c=_unwrap(values["T_min_water"]),
                t_avg_water_c=_unwrap(values["T_avg_water"]),
                t_max_water_c=_unwrap(values["T_max_water"]),
                ice_fraction=min(max(_unwrap(values["ice_fraction"]), 0.0), 1.0),
            )
        )
    series.sort(key=lambda p: p.time_hours)
    return series


class SimulationRunner:
    """
    Runs a full freeze-risk analysis on Allsolve.

    One project with a sweep over ambient temperatures; if the sweep results
    can't be parsed, falls back to one project per temperature, in parallel.
    """

    def __init__(self):
        self._runs: List[_ProjectRun] = []
        self._lock = threading.Lock()
        self._aborted = False

    def initialize(self) -> None:
        """Initialize the Allsolve SDK with credentials."""
        if not ALLSOLVE_AVAILABLE:
            logger.error("❌ Allsolve SDK is not installed!")
            raise RuntimeError("Allsolve SDK is not installed (pip install allsolve)")

        settings = get_settings()
        logger.info("🔧 Initializing Allsolve SDK...")
        logger.info(f"   Host: {settings.qs_host}")

        if not settings.qs_access_key or not settings.qs_secret_key:
            logger.error("❌ Allsolve API credentials not configured!")
            raise RuntimeError(
                "Allsolve API credentials not set. Set QS_ACCESS_KEY and QS_SECRET_KEY "
                "in backend/.env, or use Demo mode."
            )

        allsolve.setup(
            api_key=settings.qs_access_key,
            api_secret=settings.qs_secret_key,
            host=settings.qs_host,
        )
        logger.info("✅ Allsolve SDK initialized successfully")

    def run_analysis_sync(
        self,
        analysis_id: str,
        params: PipeParams,
        on_progress: Optional[ProgressCallback] = None,
    ) -> AnalysisResults:
        """
        Blocking analysis for thread pool execution.

        Args:
            analysis_id: ID used in the returned results
            params: Pipe parameters from the user
            on_progress: Optional sync callback for progress updates (status, percentage)
        """

        def update_progress(status: str, progress: float) -> None:
            if on_progress:
                on_progress(status, progress)

        ambients = sweep_ambients(params)
        logger.info("=" * 60)
        logger.info("❄️ STARTING PIPE FREEZE ANALYSIS (ALLSOLVE)")
        logger.info("=" * 60)
        logger.info(f"   Params: {params.model_dump()}")
        logger.info(f"   Outside temperature sweep: {ambients} °C")

        self.initialize()

        try:
            series_by_ambient = self._run_projects(params, [ambients], update_progress)
        except SweepParseError as e:
            logger.warning(f"⚠️ Sweep results not usable ({e}); falling back to parallel projects")
            self._cleanup_runs()
            update_progress("Sweep unavailable, running one project per temperature...", 5)
            series_by_ambient = self._run_projects(
                params, [[a] for a in ambients], update_progress
            )

        update_progress("Building verdict...", 99)
        sweep_points = []
        for ambient in ambients:
            onset, blockage = detect_events(series_by_ambient[ambient])
            sweep_points.append(
                SweepPoint(ambient_c=ambient, t_onset_hours=onset, t_blockage_hours=blockage)
            )

        results = build_results(
            analysis_id,
            "simulation",
            params,
            series=series_by_ambient[params.outside_temp_c],
            sweep=sweep_points,
        )
        update_progress("Complete!", 100)
        logger.info(f"🎉 ANALYSIS COMPLETE: {results.verdict.headline}")
        return results

    def _run_projects(
        self,
        params: PipeParams,
        groups: List[List[float]],
        update_progress: ProgressCallback,
    ) -> Dict[float, List[SeriesPoint]]:
        """Run one project per group of ambient temperatures, in parallel."""
        runs = [
            _ProjectRun(params, group, label=f"{i + 1}/{len(groups)}")
            for i, group in enumerate(groups)
        ]
        with self._lock:
            if self._aborted:
                raise AbortedError("Analysis aborted by user")
            self._runs.extend(runs)

        progress = [0.0] * len(runs)

        def make_callback(i: int) -> ProgressCallback:
            def callback(status: str, pct: float) -> None:
                progress[i] = pct
                label = f"[{i + 1}/{len(runs)}] " if len(runs) > 1 else ""
                update_progress(f"{label}{status}", sum(progress) / len(progress))

            return callback

        if len(runs) == 1:
            return runs[0].run(make_callback(0))

        merged: Dict[float, List[SeriesPoint]] = {}
        with ThreadPoolExecutor(max_workers=len(runs)) as pool:
            futures = [pool.submit(run.run, make_callback(i)) for i, run in enumerate(runs)]
            try:
                for future in futures:
                    merged.update(future.result())
            except Exception:
                # Don't leave the other projects running
                for run in runs:
                    run.abort()
                raise
        return merged

    def abort(self) -> bool:
        """Abort every running project."""
        with self._lock:
            self._aborted = True
            runs = list(self._runs)
        return any([run.abort() for run in runs])

    def _cleanup_runs(self) -> None:
        with self._lock:
            runs, self._runs = self._runs, []
        for run in runs:
            run.cleanup()

    def cleanup(self) -> None:
        """Clean up simulation resources (deletes the Allsolve projects)."""
        self._cleanup_runs()
