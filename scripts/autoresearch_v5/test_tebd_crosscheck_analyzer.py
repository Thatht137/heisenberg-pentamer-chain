"""测试 TEBD dt/dt2 交叉验收器的通过与硬拒绝路径。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ANALYZER = ROOT / "scripts/autoresearch_v5/analyze_tebd_crosscheck.py"


def write_run(
    directory: Path,
    *,
    tstep: float,
    matrix: list[list[float]],
    alpha: float = 0.23,
    window_eta: float = 0.1,
) -> None:
    directory.mkdir(parents=True)
    manifest = {
        "status": "success",
        "accepted": True,
        "params": {"alpha": alpha, "beta": 0.5, "N_units": 8, "L": 40},
        "settings": {
            "q_points": 3,
            "omega_points": 4,
            "omega_max": 3.0,
            "time_window": "exponential",
            "window_eta": window_eta,
        },
        "diagnostics": {"tstep": tstep, "tmax": 15.0},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    with (directory / "spectrum_raw.csv").open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(matrix)


class TebdCrosscheckAnalyzerTests(unittest.TestCase):
    def test_dt_half_passes_with_small_changes(self) -> None:
        coarse = [[0.1, 0.2, 0.8, 0.1], [0.2, 0.3, 0.9, 0.2], [0.1, 0.2, 0.7, 0.1]]
        refined = [[value * 1.001 for value in row] for row in coarse]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_run(root / "coarse", tstep=0.05, matrix=coarse)
            write_run(root / "refined", tstep=0.025, matrix=refined)
            output = root / "crosscheck.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf-8",
                    str(ANALYZER),
                    "--coarse-dir",
                    str(root / "coarse"),
                    "--refined-dir",
                    str(root / "refined"),
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["status"], "pass")

    def test_negative_alpha_is_rejected(self) -> None:
        matrix = [[0.1, 0.2, 0.8, 0.1], [0.2, 0.3, 0.9, 0.2], [0.1, 0.2, 0.7, 0.1]]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_run(root / "coarse", tstep=0.05, matrix=matrix, alpha=-0.1)
            write_run(root / "refined", tstep=0.025, matrix=matrix, alpha=-0.1)
            result = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf-8",
                    str(ANALYZER),
                    "--coarse-dir",
                    str(root / "coarse"),
                    "--refined-dir",
                    str(root / "refined"),
                    "--output",
                    str(root / "blocked.json"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("alpha", result.stderr)

    def test_window_eta_mismatch_is_rejected(self) -> None:
        matrix = [[0.1, 0.2, 0.8, 0.1], [0.2, 0.3, 0.9, 0.2], [0.1, 0.2, 0.7, 0.1]]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_run(root / "coarse", tstep=0.05, matrix=matrix, window_eta=0.1)
            write_run(root / "refined", tstep=0.025, matrix=matrix, window_eta=0.2)
            result = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf-8",
                    str(ANALYZER),
                    "--coarse-dir",
                    str(root / "coarse"),
                    "--refined-dir",
                    str(root / "refined"),
                    "--output",
                    str(root / "blocked.json"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("eta", result.stderr)


if __name__ == "__main__":
    unittest.main()
