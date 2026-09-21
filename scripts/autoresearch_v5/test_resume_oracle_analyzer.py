#!/usr/bin/env python3
"""验证恢复 oracle 验收器的成功与损坏路径。"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("analyze_cv_resume_oracle.py")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


class AnalyzerTests(unittest.TestCase):
    def make_case(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path, Path]:
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        run_dir = root / "cell"
        points = run_dir / "points"
        outdir = root / "analysis"
        exact = root / "exact.csv"
        points.mkdir(parents=True)

        spectrum_rows = [
            (0.0, 0.5202975174476883, 4.9e-8),
            (0.05, 0.8441218039149833, 0.0),
            (0.1, 1.3222180317058003, 5.8e-7),
        ]
        header = "q_over_pi,omega,intensity,relative_residual,solve_seconds,solution_maxdim\n"
        lines = [header]
        for index, (omega, intensity, residual) in enumerate(spectrum_rows, start=1):
            row = f"1,{omega},{intensity},{residual},1.0,32\n"
            lines.append(row)
            (points / f"omega-{index:04d}.csv").write_text(header + row, encoding="utf-8")
        (run_dir / "spectrum.csv").write_text("".join(lines), encoding="utf-8")
        exact.write_text(
            "q_over_pi,omega,intensity\n"
            + "".join(f"1,{omega},{intensity}\n" for omega, intensity, _ in spectrum_rows),
            encoding="utf-8",
        )
        (run_dir / "metrics.csv").write_text(
            "metric,value\n"
            "ground_reused,true\n"
            "source_reused,true\n"
            "max_cv_residual,5.8e-7\n",
            encoding="utf-8",
        )
        write_json(run_dir / "attempt-0001.json", {
            "status": "partial", "resume": False, "completed_points": 1.0,
            "cv_seconds_this_attempt": 1.0,
        })
        write_json(run_dir / "attempt-0002.json", {
            "status": "success", "resume": True, "completed_points": 3.0,
            "cv_seconds_this_attempt": 2.0,
        })
        write_json(run_dir / "status.json", {"accepted": True})
        write_json(run_dir / "manifest.json", {"acceptance": {"status": "pass"}})
        files = sorted(path for path in run_dir.rglob("*") if path.is_file())
        (run_dir / "checksums.sha256").write_text(
            "".join(
                f"{sha256(path)}  {path.relative_to(run_dir).as_posix()}\n" for path in files
            ),
            encoding="utf-8",
        )
        return temporary, run_dir, exact, outdir

    def run_analyzer(self, run_dir: Path, exact: Path, outdir: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-X", "utf8",
                str(SCRIPT),
                "--run-dir", str(run_dir),
                "--exact", str(exact),
                "--outdir", str(outdir),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def test_valid_two_attempt_case_passes(self) -> None:
        temporary, run_dir, exact, outdir = self.make_case()
        self.addCleanup(temporary.cleanup)
        result = self.run_analyzer(run_dir, exact, outdir)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads((outdir / "resume_oracle_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["tag"], "Agreement")
        self.assertTrue(all(summary["checks"].values()))

    def test_corrupted_cell_is_rejected(self) -> None:
        temporary, run_dir, exact, outdir = self.make_case()
        self.addCleanup(temporary.cleanup)
        (run_dir / "points" / "omega-0002.csv").write_text("corrupted\n", encoding="utf-8")
        result = self.run_analyzer(run_dir, exact, outdir)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("cell 哈希失败", result.stderr)


if __name__ == "__main__":
    unittest.main()
