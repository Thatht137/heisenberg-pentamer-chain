# -*- coding: utf-8 -*-
"""验证 CV 长任务的线性求解预算和进度输出契约。"""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class CvRuntimeContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.julia = (ROOT / "scripts/autoresearch_v5/cv_dsf_cell.jl").read_text(encoding="utf-8")
        self.runner = (ROOT / "scripts/autoresearch_v5/run_cv_dsf_cell.py").read_text(encoding="utf-8")

    def test_solver_budget_is_explicit(self) -> None:
        self.assertRegex(self.julia, r"maxiter\s*=\s*500")
        self.assertRegex(self.julia, r"krylovdim\s*=\s*100")

    def test_residual_retry_is_present(self) -> None:
        self.assertIn("if residual > 1e-5", self.julia)
        self.assertRegex(self.julia, r"maxiter\s*=\s*1000")
        self.assertRegex(self.julia, r"krylovdim\s*=\s*200")

    def test_point_outputs_are_flushed(self) -> None:
        self.assertIn("flush(file)", self.julia)
        self.assertIn("flush(stdout)", self.julia)

    def test_wrapper_has_heartbeat_probe(self) -> None:
        self.assertIn("ProgressWriter", self.runner)
        self.assertIn("progress_probe", self.runner)
        self.assertIn('phase": "julia_linsolve"', self.runner)


if __name__ == "__main__":
    unittest.main()
