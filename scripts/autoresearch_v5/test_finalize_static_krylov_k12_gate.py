"""finalize gate 的只读输入与失败留证测试。"""

from __future__ import annotations

import json
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock


sys.path.insert(0, str(Path(__file__).resolve().parent))
import finalize_static_krylov_k12_gate as finalize  # noqa: E402


class FinalizeStaticKrylovK12GateTests(unittest.TestCase):
    def _inputs(self, root: Path) -> tuple[Path, Path, Path]:
        k12 = root / "k12-cell"
        k8 = root / "k8-cell"
        for directory, krylov in ((k12, 12), (k8, 8)):
            (directory / "start_center").mkdir(parents=True)
            (directory / "start_ferro_j2").mkdir()
            manifest = {"settings": {"eigsolve_krylovdim": krylov}, "params": {"alpha": -0.1, "beta": 0.25, "L": 4, "n_units": 1}}
            (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            for mode in ("center", "ferro_j2"):
                (directory / f"start_{mode}" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        spec = root / "k12-run-spec.json"
        spec.write_text(json.dumps({"settings": {"eigsolve_krylovdim": 12}, "cells": [{"cell_id": "cell-k12", "params": {"eigsolve_krylovdim": 12}}]}), encoding="utf-8")
        return k12, spec, k8

    def test_pass_runs_comparison_and_writes_nonoverwriting_bundle(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            k12, spec, k8 = self._inputs(root)
            validator = Mock(return_value={"status": "pass", "failures": []})
            comparator = Mock(return_value={"status": "audit_only", "claim": "none", "records": []})
            result = finalize.finalize(k12, spec, k8, root / "out", validator, comparator)
            self.assertEqual(result["summary"]["gate_status"], "pass")
            validator.assert_called_once_with(k12.resolve(), spec.resolve())
            comparator.assert_called_once_with(k8.resolve(), k12.resolve())
            self.assertTrue(comparator.called)
            self.assertEqual(result["comparison"]["claim"], "none")
            self.assertTrue((root / "out" / "summary.json").is_file())
            self.assertTrue((root / "out" / "comparison.json").is_file())
            self.assertTrue((root / "out" / "checksums.sha256").is_file())
            self.assertTrue(result["summary"]["input_sha256"])
            checksums = (root / "out" / "checksums.sha256").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(checksums), 2)
            for line in checksums:
                digest, name = line.split(maxsplit=1)
                self.assertEqual(digest, hashlib.sha256((root / "out" / name).read_bytes()).hexdigest())
            with self.assertRaises(ValueError):
                finalize.finalize(k12, spec, k8, root / "out", validator, comparator)

    def test_validator_failure_is_preserved_and_blocks_comparison(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            k12, spec, k8 = self._inputs(root)
            validator = Mock(return_value={"status": "fail", "failures": ["synthetic k12 mismatch"]})
            comparator = Mock()
            result = finalize.finalize(k12, spec, k8, root / "failed", validator, comparator)
            self.assertEqual(result["summary"]["gate_status"], "blocked_by_validator")
            self.assertEqual(result["comparison"]["gate_status"], "blocked_by_validator")
            self.assertFalse(result["comparison"]["comparison_ran"])
            comparator.assert_not_called()
            self.assertIn("synthetic k12 mismatch", result["summary"]["failures"])
            self.assertEqual(result["summary"]["claim"], "none")
            self.assertEqual(result["summary"]["physical_stability_conclusion"], "not_generated")


if __name__ == "__main__":
    unittest.main(verbosity=2)
