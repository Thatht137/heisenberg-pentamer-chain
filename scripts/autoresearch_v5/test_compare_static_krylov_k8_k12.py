"""k8→k12 比较层的合成夹具测试。"""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_static_krylov_k8_k12 import compare_runs  # noqa: E402


class CompareStaticKrylovK8K12Tests(unittest.TestCase):
    def _fixture(self, root: Path, candidate_k: int = 12, same_point: bool = True) -> tuple[Path, Path]:
        old = root / "k8"
        new = root / "k12"
        point = {"alpha": -0.1, "beta": 0.25, "L": 4, "n_units": 1}
        new_point = dict(point)
        if not same_point:
            new_point["beta"] = 0.3
        for directory, krylov, values in ((old, 8, (1.0, 0.8)), (new, candidate_k, (1.1, 0.9))):
            directory.mkdir()
            parent = {"cell_id": f"cell-k{krylov}", "params": point if directory is old else new_point, "settings": {"eigsolve_krylovdim": krylov}}
            (directory / "manifest.json").write_text(json.dumps(parent), encoding="utf-8")
            for mode in ("center", "ferro_j2"):
                child = directory / f"start_{mode}"
                child.mkdir()
                manifest = {
                    "params": parent["params"],
                    "settings": {"eigsolve_krylovdim": krylov},
                    "observables": {"spin_gap": values[0], "structure_factor_peak_q_over_pi": values[1], "dominant_structure_factor_ratio": 0.2},
                    "diagnostics": {"actual_maxdim_sz0": 10 + krylov, "actual_maxdim_sz1": 11 + krylov, "final_energy_change_sz0": 1e-8 * krylov, "final_energy_change_sz1": 2e-8 * krylov},
                }
                (child / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                with (child / "entropy_profile_full.csv").open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=("bond", "log_chord", "entropy"))
                    writer.writeheader()
                    for bond in range(1, 4):
                        writer.writerow({"bond": bond, "log_chord": 0.1 * bond, "entropy": 0.2 * bond + (0.01 if krylov == 12 else 0.0)})
        return old, new

    def test_all_requested_metrics_are_audit_only(self):
        with tempfile.TemporaryDirectory() as raw:
            old, new = self._fixture(Path(raw))
            result = compare_runs(old, new)
            self.assertEqual(result["status"], "audit_only")
            self.assertEqual(result["claim"], "none")
            self.assertEqual(result["krylov_change"], {"baseline": 8, "candidate": 12})
            self.assertEqual(result["comparison_count"], 2 * (7 + 3))
            center = result["comparisons"]["center"]
            self.assertAlmostEqual(center["gap"]["candidate_k12"], 1.1)
            self.assertEqual(len(center["entropy_profile"]), 3)
            self.assertIn("actual_maxdim", center)
            self.assertIn("energy_change", center)
            self.assertNotIn("phase", result)

    def test_only_k8_to_k12_is_allowed(self):
        with tempfile.TemporaryDirectory() as raw:
            old, new = self._fixture(Path(raw), candidate_k=11)
            with self.assertRaises(ValueError):
                compare_runs(old, new)

    def test_same_physical_point_is_required(self):
        with tempfile.TemporaryDirectory() as raw:
            old, new = self._fixture(Path(raw), same_point=False)
            with self.assertRaises(ValueError):
                compare_runs(old, new)


if __name__ == "__main__":
    unittest.main(verbosity=2)
