"""测试 round43 交接的分流与网格合同。"""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.autoresearch_v5 import finalize_round43_handoff as target


class Round43HandoffTests(unittest.TestCase):
    def write_spectrum(self, directory: Path, omegas: list[float], residual: float = 1e-6) -> None:
        directory.mkdir(parents=True)
        with (directory / "spectrum.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["q_over_pi", "omega", "intensity", "relative_residual"])
            writer.writerows((1.0, omega, 0.1 + omega, residual) for omega in omegas)

    def test_exact_round43_grid_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "run"
            self.write_spectrum(run, [0.2, 0.15, 0.1, 0.05, 0.0])
            self.assertEqual(target.read_round43_omegas(run), target.EXPECTED_ROUND43_OMEGAS)

    def test_missing_round43_point_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "run"
            self.write_spectrum(run, [0.2, 0.15, 0.1, 0.05])
            with self.assertRaises(ValueError):
                target.read_round43_omegas(run)

    def test_residual_gate_is_not_relaxed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "run"
            self.write_spectrum(run, target.EXPECTED_ROUND43_OMEGAS, residual=1.01e-5)
            with self.assertRaises(ValueError):
                target.read_round43_omegas(run)

    def test_only_agreement_is_production_ready(self) -> None:
        self.assertEqual(
            target.classify_crosscheck({"status": "pass", "tag": "Agreement"}),
            ("production_ready", True, 0),
        )
        self.assertEqual(
            target.classify_crosscheck({"status": "incomplete", "tag": "NotEvaluable"}),
            ("bounded", False, 2),
        )
        self.assertEqual(
            target.classify_crosscheck({"status": "fail", "tag": "Disagreement"}),
            ("bounded_disagreement", False, 1),
        )

    def test_default_base_runs_exclude_old_omega020(self) -> None:
        joined = "\n".join(target.DEFAULT_BASE_RUNS)
        self.assertNotIn("round3_cv_L40_probe", joined)
        self.assertEqual(len(target.DEFAULT_BASE_RUNS), 4)


if __name__ == "__main__":
    unittest.main()
