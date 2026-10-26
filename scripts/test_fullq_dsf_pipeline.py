"""验收条件的轻量回归测试。"""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np
from audit_fullq_dsf import quality, crosscheck, check_partial


def fixture():
    spectrum = np.array([[0., 0., 0.], [1., 2., 1.], [2., 3., 2.], [1., 2., 1.], [0., 0., 0.]])
    return {"q": np.linspace(0, 2 * np.pi, 5), "omega": np.array([0., 0.1, 0.2]),
            "spectrum": spectrum, "metrics": [{"source_norm": 1., "source_norm_error": 1e-12,
                "relative_norm_drift": 1e-5} for _ in range(5)],
            "metadata": {"alpha": 0.5, "beta": 0.5, "L": 40, "dt": 0.05, "tmax": 60.,
                "energy": -12.5, "itensors_version": "0.9.27", "itensormps_version": "0.4.1",
                "tebd_maxdim": 192, "variance_per_site": 1e-12,
                "static_reflection_relative_rms": 1e-12, "clipping": False,
                "inversion_averaging": False}}


class QualityTests(unittest.TestCase):
    def test_valid_raw_spectrum(self):
        self.assertTrue(quality(fixture())["baseline_pass"])

    def test_asymmetry_rejected_without_modification(self):
        run = fixture()
        run["spectrum"][1, 1] += 0.1
        original = run["spectrum"].copy()
        self.assertFalse(quality(run)["baseline_pass"])
        np.testing.assert_array_equal(run["spectrum"], original)

    def test_conserved_q0_rejected(self):
        run = fixture()
        run["spectrum"][[0, -1], 0] = 0.01
        self.assertTrue(quality(run)["inversion_pass"])
        self.assertFalse(quality(run)["q0_pass"])
        self.assertFalse(quality(run)["baseline_pass"])

    def test_negative_spectrum_rejected(self):
        run = fixture()
        run["spectrum"][2, 0] = -0.1
        self.assertFalse(quality(run)["baseline_pass"])

    def test_norm_drift_rejected(self):
        run = fixture()
        run["metrics"][0]["relative_norm_drift"] = 0.02
        self.assertFalse(quality(run)["baseline_pass"])

    def test_inconsistent_norm_monitor_rejected(self):
        run = fixture()
        run["metrics"][0]["norm_api_max_relative_error"] = 1e-5
        self.assertFalse(quality(run)["baseline_pass"])

    def test_partial_grid_not_full_spectrum(self):
        run = fixture()
        run["q"] = np.linspace(0.4, 1.6, 5) * np.pi
        self.assertFalse(quality(run)["baseline_pass"])

    def test_postprocessing_rejected(self):
        run = fixture()
        run["metadata"]["inversion_averaging"] = True
        self.assertFalse(quality(run)["baseline_pass"])


class CrosscheckTests(unittest.TestCase):
    def setUp(self):
        self.base = fixture()
        self.refined = deepcopy(self.base)
        self.refined["metadata"].update(dt=0.025, tebd_maxdim=256)

    def test_identical_refined_result_passes(self):
        self.assertTrue(crosscheck(self.base, self.refined)["passed"])

    def test_wrong_model_rejected(self):
        self.refined["metadata"]["alpha"] = -0.5
        with self.assertRaises(ValueError):
            crosscheck(self.base, self.refined)

    def test_unrefined_budget_rejected(self):
        self.refined["metadata"]["dt"] = 0.05
        with self.assertRaises(ValueError):
            crosscheck(self.base, self.refined)

    def test_wrong_ground_state_rejected(self):
        self.refined["metadata"]["energy"] += 1e-4
        with self.assertRaises(ValueError):
            crosscheck(self.base, self.refined)

    def test_wrong_source_weight_rejected(self):
        self.refined["metrics"][1]["source_norm"] *= 1.1
        with self.assertRaises(ValueError):
            crosscheck(self.base, self.refined)

    def test_changed_package_version_rejected(self):
        self.refined["metadata"]["itensormps_version"] = "0.5.0"
        with self.assertRaises(ValueError):
            crosscheck(self.base, self.refined)

    def test_missing_momentum_rejected(self):
        self.refined["q"][1] += 0.01
        with self.assertRaises(ValueError):
            crosscheck(self.base, self.refined)

    def test_large_spectral_drift_rejected(self):
        self.refined["spectrum"] *= 1.2
        self.assertFalse(crosscheck(self.base, self.refined)["passed"])


class PartialCheckTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.base = root / "base"
        self.partial = root / "partial"
        self.base.mkdir()
        self.partial.mkdir()
        self.run = fixture()
        self.run["directory"] = self.base
        t = np.arange(5) * 0.05
        corr = np.exp(-1j * t)
        self.data = np.column_stack((t, corr.real, corr.imag, np.ones(len(t))))
        self.write_data(self.base / "q002_correlation.csv", self.data)
        self.write_data(self.partial / "q002_correlation.csv", self.data)
        (self.partial / "partial_metadata.toml").write_text(
            'alpha = 0.5\nbeta = 0.5\nL = 40\ndt = 0.05\ntebd_maxdim = 192\n'
            'energy = -12.5\njulia_version = "1.12.3"\n[[cells]]\nname = "q002"\n'
            f'q = {np.pi / 2}\n', encoding="utf-8")

    @staticmethod
    def write_data(path, data):
        np.savetxt(path, data, delimiter=",", comments="",
                   header="time,real_corr,imag_corr,norm_squared")

    def test_identical_partial_correlation_passes(self):
        result = check_partial(self.run, self.partial)
        self.assertTrue(result["passed"])
        self.assertFalse(result["merged_into_final_spectrum"])
        json.dumps(result)

    def test_wrong_partial_model_rejected(self):
        self.run["metadata"]["beta"] = 0.4
        with self.assertRaises(ValueError):
            check_partial(self.run, self.partial)

    def test_partial_time_mismatch_rejected(self):
        self.data[1, 0] += 0.01
        self.write_data(self.partial / "q002_correlation.csv", self.data)
        with self.assertRaises(ValueError):
            check_partial(self.run, self.partial)

    def test_partial_correlation_difference_rejected(self):
        self.data[:, 1:3] *= 1.1
        self.write_data(self.partial / "q002_correlation.csv", self.data)
        self.assertFalse(check_partial(self.run, self.partial)["passed"])


if __name__ == "__main__":
    unittest.main()
