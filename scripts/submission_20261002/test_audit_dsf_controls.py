"""单变量、网格、溯源与部分完成状态的定向测试。"""

import copy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from pip._vendor import toml

from audit_dsf_controls import (
    FIXED_KEYS, PendingRun, check_hash, compare, digest, exit_code, load_run, validate_plan,
)


def plan_fixture():
    jobs = []
    for sign, alpha in (("positive", 0.5), ("negative", -0.5)):
        for knob, dt, q in (("chi", 0.05, "0.2,0.6,1.0"), ("dt", 0.025, "0.2,0.6")):
            jobs.append({"name": f"{sign}_{knob}", "alpha": str(alpha), "dt": str(dt),
                         "chi": 256, "q_over_pi": q, "seed": sign, "seed_sha256": sign})
    return {"schema_version": 1, "jobs": jobs,
            "thresholds": {"spectrum_relative_l2": 0.03, "low_spectrum_relative_l2": 0.05,
                           "band_weight_relative": 0.05, "band_absolute_floor_C0": 0.001,
                           "main_peak_shift_J1": 0.015, "norm_drift": 0.01},
            "bands_J1": [[0, 0.6], [0.6, 2.5], [2.5, 4.0]]}


def run_fixture(chi=192, dt=0.05):
    meta = dict.fromkeys(FIXED_KEYS, 0)
    meta.update(dt=dt, tebd_maxdim=chi)
    omega = np.linspace(0, 4, 801)
    return {"metadata": meta, "directory": "synthetic", "q": np.array([0.2 * np.pi]),
            "omega": omega, "spectrum": np.array([np.exp(-omega)]),
            "metrics": [{"source_norm": 1.0}],
            "correlations": {0: {"norm_drift": 0.001, "source_relative_error": 1e-12,
                                 "norm_api_relative_error": 1e-15}}}


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.base = run_fixture()
        self.refined = run_fixture(256)
        self.plan = plan_fixture()

    def test_identical_single_chi_passes(self):
        result = compare(self.base, self.refined, "chi", 0.2, self.plan)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(len(result["bands"]), 3)
        self.assertEqual(result["full_relative_l2"], 0)

    def test_both_knobs_cannot_change(self):
        self.refined["metadata"]["dt"] = 0.025
        for knob in ("chi", "dt"):
            with self.subTest(knob=knob), self.assertRaises(ValueError):
                compare(self.base, self.refined, knob, 0.2, self.plan)

    def test_dt_comparison_requires_halving(self):
        base = run_fixture(256)
        fine = run_fixture(256, 0.025)
        self.assertEqual(compare(base, fine, "dt", 0.2, self.plan)["status"], "pass")
        fine["metadata"]["dt"] = 0.01
        with self.assertRaises(ValueError):
            compare(base, fine, "dt", 0.2, self.plan)

    def test_invariant_metadata_is_rejected(self):
        for key in FIXED_KEYS:
            changed = copy.deepcopy(self.refined)
            changed["metadata"][key] = 42
            with self.subTest(key=key), self.assertRaises(ValueError):
                compare(self.base, changed, "chi", 0.2, self.plan)

    def test_duplicate_or_missing_q_is_rejected(self):
        for grid in ([0.2 * np.pi, 0.2 * np.pi], [0.6 * np.pi]):
            self.refined["q"] = np.array(grid)
            with self.subTest(grid=grid), self.assertRaises(ValueError):
                compare(self.base, self.refined, "chi", 0.2, self.plan)

    def test_frequency_grid_mismatch_is_rejected(self):
        self.refined["omega"][5] += 1e-6
        with self.assertRaises(ValueError):
            compare(self.base, self.refined, "chi", 0.2, self.plan)

    def test_source_mismatch_is_rejected(self):
        self.refined["metrics"][0]["source_norm"] = 1.01
        with self.assertRaises(ValueError):
            compare(self.base, self.refined, "chi", 0.2, self.plan)

    def test_numeric_failure_keeps_metrics(self):
        self.base["spectrum"] *= 1.2
        result = compare(self.base, self.refined, "chi", 0.2, self.plan)
        self.assertEqual(result["status"], "fail")
        self.assertAlmostEqual(result["full_relative_l2"], 0.2)
        self.assertFalse(result["gates"]["band_weights"])
        self.assertTrue(result["integrity_passed"])

    def test_thresholds_are_read_from_plan(self):
        self.base["spectrum"] *= 1.001
        self.assertEqual(compare(self.base, self.refined, "chi", 0.2, self.plan)["status"], "pass")
        self.plan["thresholds"]["spectrum_relative_l2"] = 1e-5
        self.assertEqual(compare(self.base, self.refined, "chi", 0.2, self.plan)["status"], "fail")

    def test_band_floor_is_absolute_C0_tolerance(self):
        self.base["spectrum"][0, self.base["omega"] >= 2.5] = 0.0002
        self.refined["spectrum"][0, self.refined["omega"] >= 2.5] = 0.0001
        result = compare(self.base, self.refined, "chi", 0.2, self.plan)
        band = result["bands"][-1]
        self.assertAlmostEqual(band["relative_error"], 1)
        self.assertEqual(band["allowed_absolute_error"], 0.001)
        self.assertTrue(band["passed"])

    def test_norm_gate_checks_both_runs(self):
        self.base["correlations"][0]["norm_drift"] = 0.02
        result = compare(self.base, self.refined, "chi", 0.2, self.plan)
        self.assertFalse(result["gates"]["norm_drift"])

    def test_peak_shift_uses_frequency_units(self):
        self.base["spectrum"][0, 4] = 2
        result = compare(self.base, self.refined, "chi", 0.2, self.plan)
        self.assertAlmostEqual(result["main_peak_shift_J1"], 0.02)
        self.assertFalse(result["gates"]["peak_shift"])

    def test_exit_codes_distinguish_partial_and_failure(self):
        for status, optional, required in (("pass", 0, 0), ("partial", 0, 2), ("fail", 1, 1)):
            self.assertEqual(exit_code({"status": status}, False), optional)
            self.assertEqual(exit_code({"status": status}, True), required)

    def test_plan_rejects_wrong_jobs_and_q(self):
        validate_plan(self.plan)
        for key, value in (("chi", 192), ("q_over_pi", "0.2,0.7,1.0")):
            broken = copy.deepcopy(self.plan)
            broken["jobs"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_plan(broken)


class FileIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.seed = self.directory / "seed.jld2"
        self.seed.write_bytes(b"synthetic seed")
        meta = dict.fromkeys(FIXED_KEYS, 0)
        meta.update(dt=1.0, tmax=2.0, q_points=3, tebd_maxdim=256,
                    operator="connected full momentum Sz / sqrt(L)", time_window="triangular",
                    clipping=False, inversion_averaging=False, ground_seed_path=str(self.seed))
        (self.directory / "run_metadata.toml").write_text(toml.dumps(meta), encoding="utf-8")
        (self.directory / "result.jld2").write_bytes(b"synthetic complete marker")
        np.savetxt(self.directory / "q.csv", [0.2 * np.pi, 0.6 * np.pi], delimiter=",")
        self.omega = np.linspace(0, 4, 801)
        np.savetxt(self.directory / "omega.csv", self.omega, delimiter=",")
        np.savetxt(self.directory / "spectrum.csv", np.ones((2, 801)), delimiter=",")
        fields = "q_over_pi,source_norm,expected_static_norm,source_norm_error,norm_api_max_relative_error,relative_norm_drift,min_spectrum\n"
        (self.directory / "metrics.csv").write_text(fields + "0.2,1,1,0,0,0,1\n0.6,1,1,0,0,0,1\n", encoding="utf-8")
        for index in (1, 2):
            np.savetxt(self.directory / f"q{index:03}_correlation.csv", [[0, 1, 0, 1], [1, 1, 0, 1], [2, 1, 0, 1]],
                       delimiter=",", header="time,real_corr,imag_corr,norm_squared", comments="")

    def tearDown(self):
        self.temp.cleanup()

    def load(self):
        return load_run(self.directory, [0.2, 0.6], [0.2, 0.6], {"q_points": 3}, self.seed)

    def test_nominal_q_count_does_not_override_actual_grid(self):
        run = self.load()
        self.assertEqual(run["actual_q_points"], 2)
        self.assertEqual(run["nominal_q_points"], 3)

    def test_wrong_actual_q_is_rejected(self):
        np.savetxt(self.directory / "q.csv", [0.2 * np.pi, 0.7 * np.pi])
        with self.assertRaises(ValueError):
            self.load()

    def test_wrong_metric_order_is_rejected(self):
        path = self.directory / "metrics.csv"
        text = path.read_text().replace("0.2,1", "0.7,1")
        path.write_text(text)
        with self.assertRaises(ValueError):
            self.load()

    def test_incomplete_run_is_pending(self):
        (self.directory / "result.jld2").unlink()
        with self.assertRaises(PendingRun):
            self.load()

    def test_terminal_failure_is_not_pending(self):
        (self.directory / "result.jld2").unlink()
        (self.directory / "process.json").write_text(json.dumps({"status": "failed"}))
        with self.assertRaises(ValueError):
            self.load()

    def test_complete_marker_with_missing_data_fails(self):
        (self.directory / "spectrum.csv").unlink()
        with self.assertRaises(ValueError):
            self.load()

    def test_time_grid_mismatch_fails(self):
        path = self.directory / "q001_correlation.csv"
        data = np.loadtxt(path, delimiter=",", skiprows=1)
        data[1, 0] = 1.1
        np.savetxt(path, data, delimiter=",", header="time,real_corr,imag_corr,norm_squared", comments="")
        with self.assertRaises(ValueError):
            self.load()

    def test_source_t0_mismatch_fails(self):
        path = self.directory / "q001_correlation.csv"
        data = np.loadtxt(path, delimiter=",", skiprows=1)
        data[0, 1] = 0.9
        np.savetxt(path, data, delimiter=",", header="time,real_corr,imag_corr,norm_squared", comments="")
        with self.assertRaises(ValueError):
            self.load()

    def test_source_hash_mismatch_fails(self):
        expected = digest(self.seed)
        check_hash(self.seed, expected)
        self.seed.write_bytes(b"changed seed")
        with self.assertRaises(ValueError):
            check_hash(self.seed, expected)


if __name__ == "__main__":
    unittest.main()
