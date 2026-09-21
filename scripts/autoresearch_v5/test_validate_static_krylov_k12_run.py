"""k12 验收层的合成夹具测试。"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_static_krylov_k12_run as validator  # noqa: E402


class ValidateStaticKrylovK12RunTests(unittest.TestCase):
    def _fixture(self, root: Path, run_k: int = 12, spec_k: int = 12, child_k: int = 12) -> tuple[Path, Path]:
        run = root / "run"
        run.mkdir()
        spec = {
            "settings": {"eigsolve_krylovdim": spec_k},
            "cells": [{"cell_id": "cell-k12", "params": {"alpha": -0.1, "beta": 0.25, "L": 4, "n_units": 1, "eigsolve_krylovdim": spec_k}, "budget": 64}],
        }
        (root / "run-spec.json").write_text(json.dumps(spec), encoding="utf-8")
        parent = {"cell_id": "cell-k12", "settings": {"eigsolve_krylovdim": run_k}, "params": {"alpha": -0.1, "beta": 0.25, "L": 4, "n_units": 1}}
        (run / "manifest.json").write_text(json.dumps(parent), encoding="utf-8")
        for mode in validator.STARTS:
            child = run / f"start_{mode}"
            child.mkdir()
            manifest = {"settings": {"eigsolve_krylovdim": child_k}, "params": parent["params"]}
            (child / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return run, root / "run-spec.json"

    @staticmethod
    def _practical_pass(run: Path, spec: Path) -> dict[str, object]:
        return {"status": "pass", "failures": [], "cell_id": "cell-k12"}

    def test_contract_passes_with_practical_v2(self):
        with tempfile.TemporaryDirectory() as raw:
            run, spec = self._fixture(Path(raw))
            with patch.object(validator, "practical_validate", side_effect=self._practical_pass):
                result = validator.validate(run, spec)
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["krylov_contract"]["observed"]["parent"], 12)
            self.assertEqual(result["krylov_contract"]["observed"]["children"], {"center": 12, "ferro_j2": 12})

    def test_run_spec_k8_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            run, spec = self._fixture(Path(raw), spec_k=8)
            with patch.object(validator, "practical_validate", side_effect=self._practical_pass):
                result = validator.validate(run, spec)
            self.assertEqual(result["status"], "fail")
            self.assertTrue(any("run spec.settings" in item for item in result["failures"]))

    def test_child_k8_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            run, spec = self._fixture(Path(raw), child_k=8)
            with patch.object(validator, "practical_validate", side_effect=self._practical_pass):
                result = validator.validate(run, spec)
            self.assertEqual(result["status"], "fail")
            self.assertTrue(any("子 manifest" in item and "12" in item for item in result["failures"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
