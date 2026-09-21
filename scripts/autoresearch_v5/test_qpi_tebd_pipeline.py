#!/usr/bin/env python3
"""测试严格 q=pi TEBD 封装和验收器。"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ANALYZER = load_module("qpi_analyzer", HERE / "analyze_qpi_tebd_smoke.py")
RUNNER = load_module("qpi_runner", HERE / "run_tebd_qpi_autocorr.py")


class QpiAnalyzerTests(unittest.TestCase):
    def test_trapezoid_and_peak(self) -> None:
        grid = [0.0, 0.5, 1.0]
        values = [0.0, 1.0, 0.0]
        self.assertAlmostEqual(ANALYZER.trapezoid(grid, values), 0.5)
        self.assertEqual(ANALYZER.peak(grid, values), 0.5)

    def test_relative_l2(self) -> None:
        self.assertEqual(ANALYZER.relative_l2([1.0, 2.0], [1.0, 2.0]), 0.0)
        self.assertGreater(ANALYZER.relative_l2([1.0, 2.0], [1.1, 1.8]), 0.0)

    def test_same_instance_locks_definition(self) -> None:
        manifest = {
            "params": {"alpha": 0.23, "beta": 0.5, "L": 10, "q_over_pi": 1.0},
            "settings": {
                "boundary": "OBC",
                "sector": "Sz=0",
                "momentum_source": "O_q|GS>",
                "momentum_normalization": "1/sqrt(L)",
                "fourier_normalization": "one_sided_trapezoid/pi",
                "t0_included": True,
            },
        }
        expected = {"alpha": 0.23, "beta": 0.5, "L": 10.0, "q_over_pi": 1.0}
        self.assertTrue(ANALYZER.same_instance(manifest, expected))
        manifest["settings"]["momentum_source"] = "center Sz"
        self.assertFalse(ANALYZER.same_instance(manifest, expected))

    def test_checksum_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            artifact = run / "artifact.txt"
            artifact.write_text("qpi\n", encoding="utf-8")
            (run / "checksums.sha256").write_text(
                f"{ANALYZER.sha256(artifact)}  artifact.txt\n", encoding="utf-8"
            )
            self.assertTrue(ANALYZER.verify_checksums(run))
            artifact.write_text("changed\n", encoding="utf-8")
            self.assertFalse(ANALYZER.verify_checksums(run))


class QpiRunnerTests(unittest.TestCase):
    def test_progress_probe_reads_latest_step(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outdir = Path(temporary)
            (outdir / "julia.stdout.log").write_text(
                "step 1/10 (10.0%) t=0.1 linkdim=4 elapsed=1s ETA=9.0s\n"
                "step 5/10 (50.0%) t=0.5 linkdim=8 elapsed=5s ETA=5.0s\n",
                encoding="utf-8",
            )
            state = RUNNER.progress_probe(outdir)
            self.assertEqual(state["completed_steps"], 5)
            self.assertEqual(state["total_steps"], 10)
            self.assertEqual(state["eta_seconds"], 5.0)

    def test_write_json_is_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.json"
            RUNNER.write_json(path, {"status": "ok"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"status": "ok"})
            self.assertFalse(path.with_name("state.json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
