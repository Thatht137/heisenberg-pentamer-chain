"""测试 CV/TEBD 归一化、通过与证据不足路径。"""

from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANALYZER = ROOT / "scripts/autoresearch_v5/analyze_cv_tebd_crosscheck.py"


def write_cv(directory: Path, omegas: list[float], values: list[float], *, eta: float = 0.1) -> None:
    directory.mkdir(parents=True)
    manifest = {
        "status": "success",
        "params": {"alpha": 0.23, "beta": 0.5, "N_units": 8, "L": 40, "q_over_pi": 1.0},
        "settings": {"boundary": "OBC", "sector": "Sz=0", "eta": eta, "momentum_normalization": "1/sqrt(L)"},
        "acceptance": {"status": "pass"},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    with (directory / "spectrum.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["q_over_pi", "omega", "intensity", "relative_residual", "source_run"])
        writer.writerows((1.0, omega, value, 1e-6, "fixture") for omega, value in zip(omegas, values))


def write_tebd(directory: Path, values: list[float], *, eta: float = 0.1) -> None:
    directory.mkdir(parents=True)
    manifest = {
        "status": "success",
        "accepted": True,
        "params": {"alpha": 0.23, "beta": 0.5, "N_units": 8, "L": 40},
        "settings": {
            "boundary": "OBC",
            "q_points": 3,
            "omega_points": len(values),
            "omega_max": 0.4,
            "time_window": "exponential",
            "window_eta": eta,
        },
    }
    (directory / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    (directory / "tebd.stdout.log").write_text("Total Sz = 0.0\n", encoding="utf-8")
    matrix = [[value * math.pi * scale for value in values] for scale in (0.8, 1.0, 0.8)]
    with (directory / "spectrum_raw.csv").open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(matrix)


def run_analyzer(root: Path, *extra: str) -> tuple[subprocess.CompletedProcess[str], Path]:
    output = root / "analysis/cross-method-check.json"
    result = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf-8",
            str(ANALYZER),
            "--cv-dir",
            str(root / "cv"),
            "--tebd-dir",
            str(root / "tebd"),
            "--output",
            str(output),
            *extra,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="gbk",
        errors="replace",
        check=False,
    )
    return result, output


class CvTebdCrosscheckAnalyzerTests(unittest.TestCase):
    def test_divide_pi_and_agreement(self) -> None:
        omegas = [0.0, 0.1, 0.2, 0.3, 0.4]
        values = [0.1, 0.4, 1.0, 0.4, 0.1]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_cv(root / "cv", omegas, values)
            write_tebd(root / "tebd", values)
            result, output = run_analyzer(root, "--weight-window-max", "0.4")
            self.assertEqual(result.returncode, 0, result.stderr)
            audit = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(audit["tag"], "Agreement")
            self.assertAlmostEqual(audit["normalization"]["tebd_scale_factor"], 1.0 / math.pi)
            self.assertLess(audit["diagnostics"]["shared_window_weight_relative_delta"], 1e-12)

    def test_sparse_cv_grid_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_cv(root / "cv", [0.25, 0.3, 0.35], [0.6, 0.4, 0.3])
            write_tebd(root / "tebd", [0.1, 0.6, 0.4, 0.2, 0.1])
            result, output = run_analyzer(root)
            self.assertEqual(result.returncode, 2)
            audit = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(audit["status"], "incomplete")
            self.assertFalse(audit["coverage"]["main_peak_bracketed_by_cv_grid"])
            self.assertFalse(audit["coverage"]["major_weight_window_covered_by_cv_grid"])

    def test_accepts_julia_stdout_log(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_cv(root / "cv", [0.25, 0.3, 0.35], [0.6, 0.4, 0.3])
            write_tebd(root / "tebd", [0.1, 0.6, 0.4, 0.2, 0.1])
            (root / "tebd" / "tebd.stdout.log").rename(root / "tebd" / "julia.stdout.log")
            manifest_path = root / "tebd" / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["diagnostics"] = {"total_sz": 0.0}
            manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
            result, output = run_analyzer(root)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "incomplete")

    def test_eta_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_cv(root / "cv", [0.0, 0.2, 0.4], [0.1, 1.0, 0.1], eta=0.1)
            write_tebd(root / "tebd", [0.1, 0.5, 1.0, 0.5, 0.1], eta=0.2)
            result, _ = run_analyzer(root, "--weight-window-max", "0.4")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("eta", result.stderr)

    def test_single_cv_point_is_structured_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_cv(root / "cv", [0.25], [0.3])
            write_tebd(root / "tebd", [0.1, 0.6, 0.4, 0.2, 0.1])
            result, output = run_analyzer(root)
            self.assertEqual(result.returncode, 2)
            audit = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(audit["tag"], "NotEvaluable")


if __name__ == "__main__":
    unittest.main()
