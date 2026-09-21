#!/usr/bin/env python3
"""测试严格 q=pi 论文图的动态门槛分支。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


HERE = Path(__file__).resolve().parent
PLOTTER = HERE / "plot_qpi_tebd_production.py"


class QpiProductionPlotTests(unittest.TestCase):
    def test_plot_with_maxdim_and_complete_cv(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            analysis = root / "analysis"
            cv_dir = root / "cv"
            analysis.mkdir()
            cv_dir.mkdir()
            summary = {
                "tebd_qpi_tag": "Agreement",
                "cross_method_tag": "Agreement",
                "full_dynamic_status": "incomplete",
                "coverage": {"cv_main_peak": True, "cv_major_weight": True},
                "params": {
                    "alpha": 0.23,
                    "beta": 0.5,
                    "L": 40,
                    "q_over_pi": 1.0,
                    "eta": 0.1,
                    "boundary": "OBC",
                    "sector": "Sz=0",
                },
                "budgets": {
                    "dt_peak_omega": 0.05,
                    "dt_integrated_weight_relative": 0.05,
                    "tmax_peak_omega": 0.05,
                    "maxdim_peak_omega": 0.05,
                    "maxdim_integrated_weight_relative": 0.05,
                    "cv_peak_omega": 0.1,
                    "cv_integrated_weight_relative": 0.15,
                },
                "diagnostics": {
                    "dt_peak_delta": 0.01,
                    "dt_weight_relative_delta": 0.01,
                    "time_window_peak_delta": 0.02,
                    "maxdim": {"peak_delta": 0.01, "weight_relative_delta": 0.02},
                    "cv": {
                        "peak_delta": 0.05,
                        "integrated_weight_relative_delta": 0.10,
                    },
                },
            }
            (analysis / "summary.json").write_text(
                json.dumps(summary), encoding="utf-8"
            )
            with (analysis / "spectrum_comparison.csv").open(
                "w", encoding="utf-8", newline=""
            ) as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    ["omega", "coarse", "refined", "refined_tmax_25", "maxdim_96"]
                )
                writer.writerows(
                    [
                        [0.0, 0.1, 0.1, 0.1, 0.1],
                        [0.5, 0.8, 0.82, 0.79, 0.81],
                        [1.0, 0.4, 0.41, 0.39, 0.40],
                        [1.5, 0.1, 0.1, 0.09, 0.1],
                    ]
                )
            cv_manifest = {
                "params": {"alpha": 0.23, "beta": 0.5, "L": 40, "q_over_pi": 1.0},
                "settings": {
                    "eta": 0.1,
                    "boundary": "OBC",
                    "sector": "Sz=0",
                },
            }
            (cv_dir / "manifest.json").write_text(
                json.dumps(cv_manifest), encoding="utf-8"
            )
            with (cv_dir / "spectrum.csv").open(
                "w", encoding="utf-8", newline=""
            ) as handle:
                writer = csv.writer(handle)
                writer.writerow(["omega", "intensity"])
                writer.writerows([[0.0, 0.1], [0.5, 0.8], [1.0, 0.4], [1.5, 0.1]])
            output = root / "qpi_contract"
            result = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    str(PLOTTER),
                    "--analysis-dir",
                    str(analysis),
                    "--cv-dir",
                    str(cv_dir),
                    "--output-base",
                    str(output),
                ],
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            for suffix in (".svg", ".pdf", ".tiff", ".png", ".sources.json"):
                self.assertTrue(output.with_suffix(suffix).is_file())
            svg = output.with_suffix(".svg").read_text(encoding="utf-8")
            self.assertIn("maxdim=96", svg)
            self.assertIn("CV-DMRG grid", svg)
            self.assertNotIn("<path id=\"DejaVuSans", svg)
            with Image.open(output.with_suffix(".png")) as image:
                self.assertEqual(image.size, (2161, 1240))


if __name__ == "__main__":
    unittest.main()
