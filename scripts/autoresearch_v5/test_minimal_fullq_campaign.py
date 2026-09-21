#!/usr/bin/env python3
"""测试精简全动量任务和折叠边界。"""

from __future__ import annotations

import importlib.util
import csv
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PREPARE = load_module("prepare_fullq", HERE / "prepare_minimal_fullq_campaign.py")
BRANCHES = load_module("fullq_branches", HERE / "analyze_fullq_effective_branches.py")
RUNNER = load_module("fullq_runner", HERE / "run_tebd_production.py")
VALIDATOR = load_module("fullq_validator", HERE / "validate_fullq_tebd_run.py")
FETCH = load_module("fullq_fetch", HERE / "fetch_fullq_tebd_run.py")
ROOT = HERE.parents[1]
RESULTS = ROOT / "results"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_run(path: Path, cell_id: str, alpha: float, beta: float, tstep: float) -> None:
    path.mkdir(parents=True)
    q = np.linspace(0.0, 2.0 * math.pi, 21)
    omega = np.linspace(0.0, 3.0, 31)
    center = 0.65 + 0.15 * np.abs(np.sin(q))
    matrix = np.exp(-((omega[None, :] - center[:, None]) / 0.18) ** 2)
    if tstep > 0.02:
        matrix = np.roll(matrix, 0, axis=1) * 0.998
    matrix[:, 0] -= 0.001
    np.savetxt(path / "spectrum_raw.csv", matrix, delimiter=",")
    np.savetxt(path / "spectrum.csv", np.maximum(matrix, 0.0), delimiter=",")
    (path / "correlation.jld2").write_bytes(b"synthetic-correlation")
    (path / "spectrum.jld2").write_bytes(b"synthetic-spectrum")
    (path / "run_config.json").write_text("{}\n", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "cell_id": cell_id,
        "status": "success",
        "accepted": True,
        "params": {"alpha": alpha, "beta": beta, "N_units": 8, "L": 40},
        "settings": {
            "q_points": 21,
            "omega_points": 31,
            "omega_max": 3.0,
            "time_window": "exponential",
            "window_eta": 0.1,
            "t0_included": True,
            "max_negative_weight_fraction": 0.15,
        },
        "diagnostics": {
            "tstep": tstep,
            "tmax": 30.0,
            "variance_per_site": 1e-10,
            "total_sz": 0.0,
        },
        "acceptance": {
            "tebd_execution": True,
            "fourier_execution": True,
            "t0_included": True,
            "ground_variance": True,
            "sector_sz0": True,
            "raw_negative_weight_fraction": True,
        },
    }
    (path / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (path / "status.json").write_text(json.dumps({"status": "success", "accepted": True}) + "\n", encoding="utf-8")
    files = sorted(item for item in path.iterdir() if item.is_file())
    (path / "checksums.sha256").write_text(
        "".join(f"{sha256(item)}  {item.name}\n" for item in files), encoding="ascii"
    )


class CampaignTests(unittest.TestCase):
    def test_six_positive_cells(self) -> None:
        cells = PREPARE.cells()
        self.assertEqual(len(cells), 6)
        self.assertTrue(all(0.0 <= float(cell["alpha"]) <= 1.0 for cell in cells))
        self.assertTrue(all(0.0 <= float(cell["beta"]) <= 1.0 for cell in cells))
        self.assertEqual({float(cell["tmax"]) for cell in cells}, {30.0})

    def test_folded_boundaries(self) -> None:
        q = np.array([0.0, math.pi / 5.0, 2.0 * math.pi / 5.0])
        lower, upper = BRANCHES.folded_continuum(q, 0.1)
        self.assertAlmostEqual(lower[0], 0.0)
        self.assertAlmostEqual(lower[1], 0.0, places=12)
        self.assertAlmostEqual(upper[1], math.pi * 0.1)
        self.assertAlmostEqual(upper[2], 0.0, places=12)

    def test_negative_weight_fraction(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "spectrum.csv"
            path.write_text("1,-1\n2,-2\n", encoding="utf-8")
            ok, _, _, shape, fraction = RUNNER.finite_csv(path, 2, 2)
            self.assertTrue(ok)
            self.assertEqual(shape, (2, 2))
            self.assertAlmostEqual(float(fraction), 0.5)

    def test_fetch_cell_guard(self) -> None:
        self.assertEqual(FETCH.validate_cell_id("fullq-uniform-dt025"), "fullq-uniform-dt025")
        with self.assertRaises(ValueError):
            FETCH.validate_cell_id("../fullq-uniform-dt025")

    def test_validator_handoff_and_figure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fullq-e2e-", dir=RESULTS) as temporary:
            root = Path(temporary)
            campaign = root / "campaign"
            specs = {
                "uniform": (1.0, 1.0),
                "weak": (1.0, 0.1),
                "agreement": (0.23, 0.5),
            }
            for point, (alpha, beta) in specs.items():
                write_run(campaign / f"fullq-{point}-dt025", f"fullq-{point}-dt025", alpha, beta, 0.025)
                write_run(campaign / f"fullq-{point}-dt0125", f"fullq-{point}-dt0125", alpha, beta, 0.0125)
            self.assertEqual(VALIDATOR.validate(campaign / "fullq-uniform-dt025")["status"], "pass")
            handoff = root / "handoff"
            subprocess.run(
                [sys.executable, str(HERE / "finalize_minimal_fullq_handoff.py"), "--campaign-dir", str(campaign), "--output-dir", str(handoff)],
                cwd=ROOT, check=True, capture_output=True, text=True,
            )
            summary = json.loads((handoff / "handoff_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["status"], "production_ready")
            output = root / "figure" / "fullq"
            subprocess.run(
                [sys.executable, str(HERE / "plot_minimal_fullq_campaign.py"), "--handoff-dir", str(handoff), "--output-base", str(output)],
                cwd=ROOT, check=True, capture_output=True, text=True,
            )
            self.assertTrue(all(output.with_suffix(suffix).is_file() for suffix in (".svg", ".pdf", ".png", ".tiff", ".sources.json", ".qa.json")))
            qa = json.loads(output.with_suffix(".qa.json").read_text(encoding="utf-8"))
            self.assertEqual(qa["status"], "pass")

    def test_validator_rejects_tampering(self) -> None:
        with tempfile.TemporaryDirectory(prefix="fullq-tamper-", dir=RESULTS) as temporary:
            run = Path(temporary) / "fullq-uniform-dt025"
            write_run(run, "fullq-uniform-dt025", 1.0, 1.0, 0.025)
            with (run / "spectrum_raw.csv").open("a", encoding="utf-8") as handle:
                handle.write("0,0\n")
            result = VALIDATOR.validate(run)
            self.assertEqual(result["status"], "fail")
            self.assertFalse(result["checks"]["checksums"])


if __name__ == "__main__":
    unittest.main()
