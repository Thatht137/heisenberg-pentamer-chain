"""检验负区 eigsolve 参数的默认、透传和拒绝路径。"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from negative_dmrg_options import (
    EIGSOLVE_KRYLOVDIM_DEFAULT,
    EIGSOLVE_KRYLOVDIM_MAX,
    EIGSOLVE_KRYLOVDIM_MIN,
    parse_krylovdim_arg,
    validate_krylovdim,
)


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
PYTHON = Path(r"D:\Python3.12.4\python.exe")
JULIA = Path(r"D:\program\Julia-1.11.5\bin\julia.exe")
MANIFEST_SHA256 = hashlib.sha256((ROOT / "Manifest.toml").read_bytes()).hexdigest()


def run_static(*extra: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix=".krylov-static-", dir=RESULTS) as temp:
        output = Path(temp) / "cell"
        command = [
            str(PYTHON), "-B", str(ROOT / "scripts/autoresearch_v5/run_negative_static_cell.py"),
            "--cell-id", "smoke-krylov", "--outdir", str(output), "--path-id", "smoke-krylov",
            "--group", "0", "--role", "ridge", "--alpha", "-0.1", "--beta", "0.25",
            "--n-units", "2", "--maxdim", "64", "--nsweeps", "16", "--cutoff", "1e-11",
            "--threads", "1", "--standard-sha256", "a" * 64,
            "--expected-manifest-sha256", MANIFEST_SHA256, "--expected-julia-version", "1.11.5",
            "--julia", str(JULIA), "--dry-run", *extra,
        ]
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise AssertionError(completed.stderr or completed.stdout)
        return json.loads(completed.stdout)


class NegativeKrylovHookTests(unittest.TestCase):
    def test_default_and_explicit_values(self):
        self.assertEqual(EIGSOLVE_KRYLOVDIM_DEFAULT, 3)
        self.assertEqual(validate_krylovdim(EIGSOLVE_KRYLOVDIM_MIN), 3)
        self.assertEqual(validate_krylovdim(EIGSOLVE_KRYLOVDIM_MAX), 32)
        self.assertEqual(parse_krylovdim_arg("8"), 8)

    def test_invalid_python_values(self):
        for value in (True, False, 2, 33, 3.0, "3.0", "true"):
            with self.subTest(value=value):
                with self.assertRaises((ValueError, argparse.ArgumentTypeError)):
                    validate_krylovdim(value) if not isinstance(value, str) else parse_krylovdim_arg(value)

    def test_legacy_static_call_defaults_to_three(self):
        payload = run_static()
        self.assertEqual(payload["command"][-1], "3")

    def test_explicit_eight_is_final_julia_argument(self):
        payload = run_static("--eigsolve-krylovdim", "8")
        self.assertEqual(payload["command"][-1], "8")

    def test_batch_dry_run_forwards_eight(self):
        batch = ROOT / "scripts/autoresearch_v5/run_negative_phase_structure_batch.py"
        with tempfile.TemporaryDirectory(prefix=".krylov-batch-", dir=RESULTS) as temp:
            base = Path(temp)
            run_spec = base / "run.json"
            run_spec.write_text(json.dumps({
                "run_id": "krylov-test",
                "cells": [{"cell_id": "smoke-krylov", "params": {"alpha": -0.1, "beta": 0.25, "L": 10, "n_units": 2}, "budget": 16}],
                "settings": {"maxdim_by_L": {"10": 64}, "nsweeps": 16, "cutoff": 1e-11, "threads": 1, "q_count": 401},
                "provenance": {"negative_alpha_included": True},
            }, indent=2), encoding="utf-8")
            command = [
                str(PYTHON), "-B", str(batch), "--run-spec", str(run_spec), "--outdir", str(base / "out"),
                "--standard-sha256", "a" * 64, "--expected-manifest-sha256", MANIFEST_SHA256,
                "--expected-julia-version", "1.11.5", "--julia", str(JULIA),
                "--eigsolve-krylovdim", "8", "--dry-run",
            ]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            first = json.loads(completed.stdout.splitlines()[0])
            self.assertEqual(first["command"][first["command"].index("--eigsolve-krylovdim") + 1], "8")

    def test_julia_validator(self):
        if not JULIA.is_file():
            self.skipTest("本机 Julia 不可用")
        code = (
            'include(raw"scripts/autoresearch_v5/negative_static_cell.jl"); '
            'for token in ARGS; valid = token in ("3", "8", "32"); ok = try parse_krylovdim(token); true catch; false end; '
            'ok == valid || error("校验错误: ", token); end; println("JULIA_KRYLOV_VALIDATION_OK")'
        )
        completed = subprocess.run(
            [str(JULIA), "--startup-file=no", "--project=.", "-e", code, "--", "3", "8", "32", "2", "33", "3.0", "true"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("JULIA_KRYLOV_VALIDATION_OK", completed.stdout)


if __name__ == "__main__":
    unittest.main()
