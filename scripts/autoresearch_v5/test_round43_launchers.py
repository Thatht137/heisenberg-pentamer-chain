#!/usr/bin/env python3
"""验证 round43 两阶段启动合同。"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PHASE1 = (ROOT / "launch_round43_qpi_cv_lowfreq_desc_20260805.sh").read_text(
    encoding="utf-8"
)
PHASE2 = (ROOT / "resume_round43_qpi_cv_low000_20260805.sh").read_text(
    encoding="utf-8"
)


def option(script: str, name: str) -> str:
    match = re.search(rf"^\s*--{re.escape(name)}\s+(\S+)", script, re.MULTILINE)
    if match is None:
        raise AssertionError(f"缺少参数 --{name}")
    return match.group(1)


class Round43LauncherContractTests(unittest.TestCase):
    def test_shared_physics_and_accuracy_contract(self) -> None:
        expected = {
            "alpha": "0.23",
            "beta": "0.5",
            "n-units": "8",
            "q-over-pi": "1.0",
            "eta": "0.1",
            "omega-min": "0.0",
            "omega-max": "0.2",
            "omega-step": "0.05",
            "omega-order": "descending",
            "dmrg-maxdim": "320",
            "cv-maxdim": "1200",
            "nsweeps": "24",
            "cutoff": "1e-10",
            "cv-cutoff": "1e-16",
            "max-cv-residual": "1e-5",
            "threads": "4",
        }
        for script in (PHASE1, PHASE2):
            for name, value in expected.items():
                self.assertEqual(option(script, name), value)

    def test_phase1_stops_after_four_descending_points(self) -> None:
        self.assertEqual(option(PHASE1, "max-new-points"), "4")
        self.assertNotRegex(PHASE1, r"^\s*--resume(?:\s|$)")
        self.assertIn('"solve_order": [0.20, 0.15, 0.10, 0.05]', PHASE1)

    def test_phase2_requires_all_phase1_points_to_pass(self) -> None:
        self.assertEqual(option(PHASE2, "max-new-points"), "1")
        self.assertIsNotNone(
            re.search(r"^\s*--resume(?:\s|$)", PHASE2, re.MULTILINE)
        )
        self.assertIn("expected = [0.20, 0.15, 0.10, 0.05]", PHASE2)
        self.assertIn("if len(rows) != 4", PHASE2)
        self.assertIn("if max(residuals) > 1e-5", PHASE2)

    def test_launchers_are_offline_and_single_process(self) -> None:
        for script in (PHASE1, PHASE2):
            self.assertIn("JULIA_PKG_OFFLINE=true", script)
            self.assertIn("JULIA_PKG_SERVER=", script)
            self.assertIn("existing_julia=$(pgrep -x julia || true)", script)
            self.assertIn("existing_runner=$(ps -eo", script)

    def test_scope_excludes_unrequested_regions(self) -> None:
        self.assertIn('"negative_alpha_excluded": True', PHASE1)
        self.assertIn('"figure_9_excluded": True', PHASE1)


if __name__ == "__main__":
    unittest.main()
