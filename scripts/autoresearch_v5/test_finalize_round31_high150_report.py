#!/usr/bin/env python3
"""测试 round31 终态报告更新器。"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/autoresearch_v5/finalize_round31_high150_report.py"


class FinalizeRound31ReportTests(unittest.TestCase):
    def test_rejects_missing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report = root / "report.json"
            report.write_text('{"sections": []}\n', encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--report", str(report), "--validator", str(root / "missing.json"), "--anchor-dir", str(root / "anchor"), "--crosscheck", str(root / "cross.json"), "--receipt", str(root / "receipt.json")],
                capture_output=True, text=True, encoding="gbk", errors="replace", check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(report.read_text(encoding="utf-8")), {"sections": []})

    def test_updates_from_terminal_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            anchor = root / "anchor"
            anchor.mkdir()
            report = root / "report.json"
            validator = root / "validator.json"
            crosscheck = root / "cross.json"
            receipt = root / "receipt.json"
            report.write_text(json.dumps({"sections": [{"title": "2026-08-04 round31 high-150 运行状态与 ETA", "blocks": []}]}) + "\n", encoding="utf-8")
            validator.write_text(json.dumps({"status": "pass", "checks": {"all": True}}) + "\n", encoding="utf-8")
            (anchor / "manifest.json").write_text(json.dumps({"status": "success", "acceptance": {"status": "pass"}}) + "\n", encoding="utf-8")
            (anchor / "spectrum.csv").write_text("omega,intensity\n0.2,1\n", encoding="utf-8")
            crosscheck.write_text(json.dumps({"tag": "NotEvaluable", "coverage": {"main_peak_bracketed_by_cv_grid": False, "major_weight_window_covered_by_cv_grid": False}, "diagnostics": {"cv_omegas": [0.2, 1.5], "shared_point_relative_differences": [0.01, 0.02], "shared_window_weight_relative_delta": 0.03}}) + "\n", encoding="utf-8")
            receipt.write_text(json.dumps({"status": "pass", "non_clobbering": True}) + "\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--report", str(report), "--validator", str(validator), "--anchor-dir", str(anchor), "--crosscheck", str(crosscheck), "--receipt", str(receipt)],
                capture_output=True, text=True, encoding="gbk", errors="replace", check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            updated = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(updated["sections"][0]["title"], "round31 high-150 终态回传与 accepted-only 动态验收")
            self.assertNotIn("运行状态与 ETA", json.dumps(updated, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
