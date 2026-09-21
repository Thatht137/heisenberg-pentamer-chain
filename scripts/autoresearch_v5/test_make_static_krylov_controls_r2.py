"""r2 准备器的协议测试；不启动 Julia 或网络。"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import make_static_krylov_controls_r2 as r2  # noqa: E402


class StaticKrylovControlsR2Tests(unittest.TestCase):
    def test_harness_plan_and_two_cells(self):
        plan = r2.load_harness_plan(r2.DEFAULT_PLAN)
        cells = r2.build_cells(plan)
        self.assertEqual({cell["params"]["alpha"] for cell in cells}, {-0.1, -0.175})
        self.assertEqual({cell["params"]["eigsolve_krylovdim"] for cell in cells}, {8})
        self.assertTrue(all(cell["budget"] == 64 for cell in cells))

    def test_sources_include_parser_fix_and_all_pentamer_includes(self):
        names = set(r2.source_names())
        self.assertIn(r2.JULIA_SOURCE, names)
        self.assertTrue(set(r2.SRC_DEPENDENCIES).issubset(names))
        hashes = r2.validate_sources(r2.source_names())
        self.assertEqual(hashes[r2.JULIA_SOURCE], "291eb369d5441b53d4abafd36d8469e107f4c1d91622ed33478912228ed3635f")

    def test_dry_rows_require_fixed_runtime_and_outputs(self):
        row = {
            "cell_id": "probe",
            "command": [
                "python", "runner", "--maxdim", "1200", "--nsweeps", "64", "--cutoff", "1e-11",
                "--threads", "8", "--q-count", "401", "--eigsolve-krylovdim", "8",
                "--init-modes", "center,ferro_j2", "--noise-profile", "legacy", "--random-seed", "20260811",
                "--save-state", "--enriched-diagnostics",
            ],
        }
        r2.validate_dry_rows([row, {**row, "cell_id": "probe2"}])
        bad = copy.deepcopy(row)
        bad["command"][-1] = "--no-enriched-diagnostics"
        with self.assertRaises(ValueError):
            r2.validate_dry_rows([bad, {**row, "cell_id": "probe2"}])


if __name__ == "__main__":
    unittest.main()
