"""Independent thermal checks and API/cloud contracts; never launch cloud jobs."""
import ast
import json
import logging
import math
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.pipe_model import PipeParams, coefficients, simulate, critical_flow, WIND_SPEED
from app.pipe_cloud import extract_results, run_cloud
from app import pipe_api

logging.disable(logging.CRITICAL)


def exact_stagnant(p, seconds):
    """Exact two-node matrix exponential, independent of the time-step solver."""
    c = coefficients(p)
    a = c["g_water_wall"] / c["capacity_water"]
    b = c["g_water_wall"] / c["capacity_wall"]
    d = c["g_wall_environment"] / c["capacity_wall"]
    discriminant = math.sqrt((a + b + d) ** 2 - 4 * a * d)
    slow = (-(a + b + d) + discriminant) / 2
    fast = (-(a + b + d) - discriminant) / 2
    weights = (-fast / (slow - fast), slow / (slow - fast))
    exponentials = (math.exp(slow * seconds), math.exp(fast * seconds))
    delta = p.water_c - p.ambient_c
    water = p.ambient_c + delta * sum(w * e for w, e in zip(weights, exponentials))
    wall = p.ambient_c + delta * sum(w * e * (1 + rate / a)
                                    for w, e, rate in zip(weights, exponentials, (slow, fast)))
    interface = water - c["film_fraction"] * (water - wall)
    return water, wall, interface


class PipePhysicsTests(unittest.TestCase):
    def test_freezing_is_interface_onset_before_bulk_water_freezes(self):
        r = simulate(PipeParams())
        self.assertEqual(r["risk"], "freezing")
        self.assertEqual(r["minimum_interface_c"], 0)
        self.assertGreater(r["minimum_c"], 0)
        self.assertEqual(r["end_hours"], r["freeze_hours"])
        self.assertEqual(r["history"][-1]["interface_temperature_c"], 0)
        self.assertAlmostEqual(r["profile"][0]["temperature_c"], r["profile"][-1]["temperature_c"])
        self.assertEqual(r["environment"]["wind_m_s"], 3)
        json.dumps(r, allow_nan=False)

    def test_onset_matches_exact_two_node_solution_and_time_refines(self):
        p = PipeParams()
        low, high = 0, coefficients(p)["tau"] * 10
        for _ in range(70):
            middle = (low + high) / 2
            if exact_stagnant(p, middle)[2] > 0:
                low = middle
            else:
                high = middle
        exact = high
        coarse = simulate(p)["freeze_hours"] * 3600
        refined = simulate(p, time_refinement=2)["freeze_hours"] * 3600
        self.assertLess(abs(coarse - exact) / exact, .03)
        self.assertLess(abs(refined - exact), abs(coarse - exact))

    def test_temperatures_and_stored_energy_match_exact_solution(self):
        p = PipeParams(ambient_c=1, duration_h=.1)
        r = simulate(p)
        water, wall, interface = exact_stagnant(p, 360)
        self.assertAlmostEqual(r["minimum_c"], water, delta=.04)
        self.assertAlmostEqual(r["minimum_wall_c"], wall, delta=.04)
        self.assertAlmostEqual(r["minimum_interface_c"], interface, delta=.04)
        c = coefficients(p)
        exact_energy = c["capacity_water"] * water + c["capacity_wall"] * wall
        numerical_energy = c["capacity_water"] * r["minimum_c"] + c["capacity_wall"] * r["minimum_wall_c"]
        self.assertLess(abs(numerical_energy - exact_energy) / exact_energy, .015)

    def test_uniform_equilibrium_is_preserved(self):
        p = PipeParams(ambient_c=10, water_c=10, flow_l_min=.1, duration_h=.1)
        r = simulate(p)
        self.assertIsNone(r["freeze_hours"])
        self.assertAlmostEqual(r["minimum_c"], 10, places=9)
        self.assertAlmostEqual(r["minimum_interface_c"], 10, places=9)

    def test_insulation_and_pipe_materials_affect_heat_loss(self):
        p = PipeParams()
        reference = simulate(p)
        for material in ["fiberglass", "foam_wrap", "mineral_wool"]:
            insulated = simulate(PipeParams(insulation_material=material, insulation_mm=30))
            self.assertGreater(insulated["freeze_hours"], reference["freeze_hours"])
            self.assertGreater(coefficients(insulated_params := PipeParams(insulation_material=material, insulation_mm=30))["resistance"], coefficients(p)["resistance"])
        for material in ["copper", "steel", "pvc", "pex"]:
            self.assertGreater(coefficients(PipeParams(material=material))["capacity_wall"], 0)
        self.assertGreater(coefficients(PipeParams(material="pvc"))["resistance"],
                           coefficients(PipeParams(material="copper"))["resistance"])

    def test_length_independence_for_stagnant_water(self):
        self.assertAlmostEqual(simulate(PipeParams(length_m=2))["freeze_hours"],
                               simulate(PipeParams(length_m=40))["freeze_hours"])

    def test_flow_threshold_is_self_consistent_and_cell_refinement_converges(self):
        p = PipeParams()
        threshold = critical_flow(p)
        def steady_interface(flow):
            c = coefficients(p.model_copy(update={"flow_l_min": flow}))
            outlet = p.ambient_c + (p.water_c - p.ambient_c) * math.exp(
                -p.length_m / (1000 * 4184 * flow / 60000 * c["resistance"]))
            return outlet - (outlet - p.ambient_c) * c["r_internal"] / c["resistance"]
        self.assertAlmostEqual(steady_interface(threshold), 0, places=9)
        below = simulate(p.model_copy(update={"flow_l_min": threshold * .9}))
        above_p = p.model_copy(update={"flow_l_min": threshold * 1.1})
        above = simulate(above_p, cells=160)
        finer = simulate(above_p, cells=320)
        self.assertEqual(below["risk"], "freezing")
        self.assertIsNone(above["freeze_hours"])
        self.assertGreater(above["minimum_interface_c"], 0)
        exact = steady_interface(above_p.flow_l_min)
        self.assertLess(abs(finer["minimum_interface_c"] - exact),
                        abs(above["minimum_interface_c"] - exact))
        self.assertAlmostEqual(finer["minimum_interface_c"], exact, delta=.15)

    def test_no_subzero_boundary_no_freeze_and_colder_air_accelerates_it(self):
        for ambient in [0, 5, 20]:
            r = simulate(PipeParams(ambient_c=ambient, duration_h=.1))
            self.assertIsNone(r["freeze_hours"])
            self.assertEqual(r["critical_flow_l_min"], 0)
            json.dumps(r, allow_nan=False)
        self.assertLess(simulate(PipeParams(ambient_c=-40))["freeze_hours"],
                        simulate(PipeParams())["freeze_hours"])
        self.assertEqual(WIND_SPEED, 3.0)

    def test_no_insulation_normalizes_thickness(self):
        p = PipeParams(insulation_material="none", insulation_mm=30)
        self.assertEqual(p.insulation_mm, 0)
        with self.assertRaises(ValueError):
            PipeParams(insulation_material="foam_wrap", insulation_mm=0)


class PipeApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_contract_and_validation(self):
        response = self.client.post("/api/pipe/estimate", json={})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["engine"], "estimate")
        self.assertGreater(len(data["history"]), 2)
        self.assertNotIn("location", data["parameters"])
        for invalid in [{"diameter_mm": 0}, {"flow_l_min": -1}, {"material": "glass"},
                        {"water_c": 0}, {"length_m": "NaN"}, {"location": "indoors"},
                        {"external_h": 20}, {"insulation_material": "invalid"}]:
            with self.subTest(invalid=invalid):
                self.assertEqual(self.client.post("/api/pipe/estimate", json=invalid).status_code, 422)
        self.assertEqual(self.client.get("/api/pipe/unknown").status_code, 404)

    def test_cloud_job_completion_and_failure_release_lock(self):
        result = simulate(PipeParams())
        result["engine"] = "allsolve"
        with patch("app.pipe_cloud.run_cloud", return_value=result):
            start = self.client.post("/api/pipe/start", json={})
        job = self.client.get("/api/pipe/" + start.json()["id"]).json()
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["result"]["engine"], "allsolve")
        with patch("app.pipe_cloud.run_cloud", side_effect=RuntimeError("cloud unavailable")):
            failed = self.client.post("/api/pipe/start", json={})
        self.assertEqual(self.client.get("/api/pipe/" + failed.json()["id"]).json()["status"], "failed")
        self.assertFalse(pipe_api.cloud_lock.locked())

    def test_only_one_cloud_job_at_a_time(self):
        pipe_api.cloud_lock.acquire()
        try:
            self.assertEqual(self.client.post("/api/pipe/start", json={}).status_code, 409)
        finally:
            pipe_api.cloud_lock.release()


class CloudOutputTests(unittest.TestCase):
    @staticmethod
    def row(bulk, interface, wall):
        return {"T_min_water": [bulk], "T_min_interface": [interface], "T_min_wall": [wall],
                **{"profile_" + str(i): [bulk] for i in range(41)}}

    def test_interface_onset_interpolates_bulk_wall_and_profile(self):
        values = {"120": self.row(8, -1, -1), "nostep": {},
                  "0": self.row(10, 10, 10), "60": self.row(9, 1, 1)}
        r = extract_results(values, PipeParams(), "https://example.com/project")
        self.assertEqual(r["engine"], "allsolve")
        self.assertAlmostEqual(r["freeze_hours"] * 3600, 90)
        self.assertAlmostEqual(r["minimum_c"], 8.5)
        self.assertEqual(r["minimum_interface_c"], 0)
        self.assertEqual(r["minimum_wall_c"], 0)
        self.assertAlmostEqual(r["profile"][-1]["temperature_c"], 8.5)

    def test_empty_and_incomplete_cloud_outputs_fail(self):
        with self.assertRaises(RuntimeError):
            extract_results({}, PipeParams(), "")
        with self.assertRaises(RuntimeError):
            extract_results({"0": self.row(10, 10, 10)}, PipeParams(), "")

    def test_cached_result_skips_cloud_connection(self):
        import app.pipe_cloud as cloud
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "script.py"
            script.write_text("# test")
            p = PipeParams()
            with patch.object(cloud, "ROOT", root), patch.object(cloud, "SCRIPT", script):
                fp = cloud.scenario_fingerprint(p)
                cache = root / ".allsolve_cache" / "pipe" / fp
                cache.mkdir(parents=True)
                (cache / "result.json").write_text(json.dumps(simulate(p)))
                client = MagicMock()
                with patch.dict(sys.modules, {"allsolve": MagicMock(Client=client)}):
                    run_cloud(p, MagicMock())
            client.assert_not_called()

    def test_sdk_objects_and_script_syntax(self):
        try:
            import allsolve
        except ImportError:
            self.skipTest("Optional Allsolve SDK not installed")
        from app.pipe_cloud import SCRIPT
        content = SCRIPT.read_text(encoding="utf-8")
        ast.parse(content)
        allsolve.Script(name="pipe.py", content=content, is_main=True)
        allsolve.MeshSettings(name="Axial mesh", mesh_size_min=1 / 240,
                             mesh_size_max=1 / 120, max_run_time_minutes=10,
                             use_mesh_refiner=False)
        allsolve.Physics.HeatTransfer()
        allsolve.Runtime(node_type=allsolve.CPU.CORES_3_10GB_FAST_START)


if __name__ == "__main__":
    unittest.main()

