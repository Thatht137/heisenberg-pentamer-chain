#!/usr/bin/env python3
"""测试严格 q=pi 生产验收器的数值核心。"""

from __future__ import annotations

import importlib.util
import csv
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "qpi_production_analysis", HERE / "analyze_qpi_tebd_production.py"
)
ANALYZER = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(ANALYZER)


class QpiProductionAnalysisTests(unittest.TestCase):
    @staticmethod
    def write_run(
        path: Path,
        tstep: float,
        maxdim: int,
        actual_maxdim: float,
        times: list[float],
        correlations: list[complex],
        omegas: list[float],
    ) -> None:
        path.mkdir()
        values = ANALYZER.fourier_spectrum(times, correlations, omegas, 0.1)
        manifest = {
            "status": "success",
            "accepted": True,
            "params": {"alpha": 0.23, "beta": 0.5, "L": 40, "q_over_pi": 1.0},
            "settings": {
                "boundary": "OBC",
                "sector": "Sz=0",
                "momentum_source": "O_q|GS>",
                "momentum_normalization": "1/sqrt(L)",
                "fourier_normalization": "one_sided_trapezoid/pi",
                "time_window": "exponential",
                "window_eta": 0.1,
                "t0_included": True,
                "trotter_order": 2,
                "tstep": tstep,
                "tmax": 2.0,
                "omega_min": 0.0,
                "omega_max": 1.5,
                "omega_step": 0.5,
                "tebd_cutoff": 1e-10,
                "tebd_maxdim": maxdim,
            },
            "diagnostics": {"tebd_actual_maxdim": actual_maxdim},
            "acceptance": {"execution": True, "artifacts": True},
        }
        (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (path / "status.json").write_text(
            json.dumps({"status": "success", "accepted": True}), encoding="utf-8"
        )
        with (path / "spectrum.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["omega", "intensity"])
            writer.writerows(zip(omegas, values))
        with (path / "correlation.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.writer(handle)
            writer.writerow(["time", "real_corr", "imag_corr"])
            writer.writerows(
                (time, value.real, value.imag)
                for time, value in zip(times, correlations)
            )
        files = ["manifest.json", "status.json", "spectrum.csv", "correlation.csv"]
        (path / "checksums.sha256").write_text(
            "".join(f"{ANALYZER.sha256(path / name)}  {name}\n" for name in files),
            encoding="utf-8",
        )

    def test_fourier_constant_signal(self) -> None:
        times = [0.0, 0.5, 1.0]
        values = ANALYZER.fourier_spectrum(times, [1 + 0j] * 3, [0.0], 0.0)
        self.assertAlmostEqual(values[0], 1.0 / math.pi)

    def test_time_truncation_requires_exact_grid_point(self) -> None:
        times = [0.0, 0.25, 0.5, 0.75, 1.0]
        short_times, short_values = ANALYZER.truncate_time(times, [0j] * 5, 0.5)
        self.assertEqual(short_times, [0.0, 0.25, 0.5])
        self.assertEqual(len(short_values), 3)
        with self.assertRaises(ValueError):
            ANALYZER.truncate_time(times, [0j] * 5, 0.6)

    def test_checksum_rejects_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            (run / "checksums.sha256").write_text(
                f"{'0' * 64}  ../outside.txt\n", encoding="utf-8"
            )
            ok, failures = ANALYZER.verify_checksums(run)
            self.assertFalse(ok)
            self.assertTrue(any("路径越界" in item for item in failures))

    def test_linear_interpolation_and_window_clip(self) -> None:
        grid = [0.0, 0.5, 1.0, 1.5]
        values = [0.0, 1.0, 0.0, 1.0]
        self.assertEqual(ANALYZER.interpolate(grid, values, [0.25, 1.25]), [0.5, 0.5])
        clipped_grid, clipped_values = ANALYZER.clip_to_window(
            grid, values, 0.25, 1.25
        )
        self.assertEqual(clipped_grid, [0.25, 0.5, 1.0, 1.25])
        self.assertEqual(clipped_values, [0.5, 1.0, 0.0, 0.5])

    def test_cross_method_budget_tags(self) -> None:
        tag, checks = ANALYZER.comparison_tag(True, 0.05, 0.10, 0.1, 0.15)
        self.assertEqual(tag, "Agreement")
        self.assertTrue(all(checks.values()))
        tag, _ = ANALYZER.comparison_tag(True, 0.11, 0.10, 0.1, 0.15)
        self.assertEqual(tag, "Disagreement")
        tag, _ = ANALYZER.comparison_tag(False, None, None, 0.1, 0.15)
        self.assertEqual(tag, "NotEvaluable")

    def test_maxdim_cap_must_be_exercised(self) -> None:
        self.assertFalse(ANALYZER.maxdim_cap_exercised(117.0, 160))
        self.assertTrue(ANALYZER.maxdim_cap_exercised(96.0, 96))

    def test_comparison_csv_includes_maxdim_column(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "comparison.csv"
            ANALYZER.write_spectrum_comparison(
                path,
                [0.0, 0.5],
                [1.0, 0.5],
                [1.0, 0.4],
                [0.9, 0.4],
                25.0,
                [1.0, 0.41],
                96,
            )
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(list(rows[0]), [
                "omega",
                "coarse",
                "refined",
                "refined_tmax_25",
                "maxdim_96",
            ])
            self.assertEqual(float(rows[1]["maxdim_96"]), 0.41)

    def test_complete_pipeline_promotes_cv_and_maxdim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            times = [0.0, 0.5, 1.0, 1.5, 2.0]
            correlations = [
                complex(math.cos(-0.5 * time), math.sin(-0.5 * time))
                for time in times
            ]
            omegas = [0.0, 0.5, 1.0, 1.5]
            coarse = root / "coarse"
            refined = root / "refined"
            maxdim = root / "maxdim"
            self.write_run(coarse, 0.5, 320, 117.0, times, correlations, omegas)
            self.write_run(refined, 0.25, 320, 117.0, times, correlations, omegas)
            self.write_run(maxdim, 0.25, 96, 96.0, times, correlations, omegas)
            cv_dir = root / "cv"
            cv_dir.mkdir()
            _, cv_values = ANALYZER.read_spectrum(refined / "spectrum.csv")
            cv_manifest = {
                "status": "success",
                "accepted": True,
                "params": {"alpha": 0.23, "beta": 0.5, "L": 40, "q_over_pi": 1.0},
                "settings": {
                    "eta": 0.1,
                    "boundary": "OBC",
                    "sector": "Sz=0",
                    "momentum_normalization": "1/sqrt(L)",
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
                writer.writerows(zip(omegas, cv_values))
            (cv_dir / "checksums.sha256").write_text(
                "".join(
                    f"{ANALYZER.sha256(cv_dir / name)}  {name}\n"
                    for name in ("manifest.json", "spectrum.csv")
                ),
                encoding="utf-8",
            )
            output = root / "output"
            result = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    str(HERE / "analyze_qpi_tebd_production.py"),
                    "--coarse-dir",
                    str(coarse),
                    "--refined-dir",
                    str(refined),
                    "--maxdim-dir",
                    str(maxdim),
                    "--cv-dir",
                    str(cv_dir),
                    "--output-dir",
                    str(output),
                    "--short-tmax",
                    "1.5",
                ],
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["qpi_production_status"], "pass")
            self.assertEqual(summary["cross_method_tag"], "Agreement")
            self.assertTrue(summary["coverage"]["two_maxdim"])
            with (output / "spectrum_comparison.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                self.assertIn("maxdim_96", next(csv.reader(handle)))

    def test_smoke_fourier_round_trip(self) -> None:
        root = HERE.parents[1]
        run = (
            root
            / "results/autoresearch_v5_20260803/round25_qpi_tebd_smoke/L10-qpi-dt0025-t30"
        )
        if not run.is_dir():
            self.skipTest("本地 smoke 数据不存在")
        omegas, stored = ANALYZER.read_spectrum(run / "spectrum.csv")
        times, correlations = ANALYZER.read_correlation(run / "correlation.csv")
        recomputed = ANALYZER.fourier_spectrum(times, correlations, omegas, 0.1)
        self.assertLess(ANALYZER.relative_l2(stored, recomputed), 1e-10)

    def test_smoke_t25_window_is_nonnegative(self) -> None:
        root = HERE.parents[1]
        run = (
            root
            / "results/autoresearch_v5_20260803/round25_qpi_tebd_smoke/L10-qpi-dt0025-t30"
        )
        if not run.is_dir():
            self.skipTest("本地 smoke 数据不存在")
        omegas, _ = ANALYZER.read_spectrum(run / "spectrum.csv")
        times, correlations = ANALYZER.read_correlation(run / "correlation.csv")
        short = ANALYZER.fourier_spectrum(
            *ANALYZER.truncate_time(times, correlations, 25.0), omegas, 0.1
        )
        self.assertGreaterEqual(min(short), 0.0)

    def test_assembled_cv_anchors_are_checksum_verified(self) -> None:
        root = HERE.parents[1]
        run = root / "results/autoresearch_v5_20260803/round27_qpi_cv_anchor_assembly"
        if not run.is_dir():
            self.skipTest("本地 CV anchor 集不存在")
        _, points = ANALYZER.read_cv_points(run)
        self.assertEqual([point[0] for point in points], [0.2, 0.25, 0.3, 0.35])


if __name__ == "__main__":
    unittest.main()
