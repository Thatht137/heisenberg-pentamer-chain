"""静态 Krylov 准备器的计划与依赖拒绝测试。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_static_krylov_controls as maker  # noqa: E402


class StaticKrylovPreparationTests(unittest.TestCase):
    def test_two_cells_and_fixed_settings(self):
        plan_path = maker.RUN / "harness_parameter_scan_preflight" / "run_spec.json"
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        cells = maker.build_cells_from_harness(maker.load_harness_plan(plan_path))
        self.assertEqual(len(cells), 2)
        self.assertEqual([cell["params"]["alpha"] for cell in cells], [-0.1, -0.175])
        self.assertTrue(all(cell["budget"] == 64 for cell in cells))
        self.assertTrue(all(cell["params"]["eigsolve_krylovdim"] == 8 for cell in cells))
        self.assertEqual(plan["settings"]["nsweeps"], 64)

    def test_missing_helper_is_rejected(self):
        names = tuple(name for name in maker.source_names() if name != maker.HELPER)
        with self.assertRaises(ValueError):
            maker.validate_sources(names)

    def test_source_count_and_helper(self):
        names = maker.source_names()
        self.assertIn(maker.HELPER, names)
        self.assertEqual(len(names), 15)

    def test_generated_preflight_is_not_launch_receipt(self):
        if not maker.RUN.is_dir():
            self.skipTest("准备目录尚未生成")
        preflight = json.loads((maker.RUN / "preflight.json").read_text(encoding="utf-8"))
        upload = json.loads((maker.RUN / "server_upload_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(preflight["status"], "prepared_only")
        self.assertFalse(preflight["launch_started"])
        self.assertEqual(len(upload["files"]), 18)
        self.assertFalse(upload["launch_allowed"])


if __name__ == "__main__":
    unittest.main()
