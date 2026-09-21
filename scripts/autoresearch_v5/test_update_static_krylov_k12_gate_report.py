"""static Krylov k12 gate 报告的最小回归测试。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.autoresearch_v5.update_static_krylov_k12_gate_report import (
    GateReportError,
    build_report,
    load_gate_source,
    write_report,
)


ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "results/research_progress/project_closeout_status_20260919.json"


def _all_text(value):
    if isinstance(value, dict):
        return " ".join([_all_text(k) + " " + _all_text(v) for k, v in value.items()])
    if isinstance(value, list):
        return " ".join(_all_text(item) for item in value)
    return str(value)


class StaticKrylovK12GateReportTests(unittest.TestCase):
    def test_prepared_only_transcribes_gate_and_boundary(self):
        gate, source = load_gate_source("prepared-only", STATUS)
        report = build_report(gate, "prepared-only", source, ROOT)
        text = _all_text(report)
        self.assertEqual(report["metadata"]["state"], "prepared-only")
        self.assertIn("eigsolve_krylovdim 12", text)
        self.assertIn("1.11.5", text)
        self.assertIn("1.12.3", text)
        self.assertIn("not_run", text)
        self.assertIn("audit_only", text)
        self.assertIn("不引入新相", text)

    def test_terminal_summary_transcribes_validator_and_comparison(self):
        future = {
            "status": "terminal_success",
            "claim": "audit_only",
            "parameters": {"eigsolve_krylovdim": 12, "L": 80},
            "manifest_sha256": "manifest-terminal",
            "run_spec_sha256": "spec-terminal",
            "validator": {"status": "pass", "records": 2, "failures": []},
            "comparison": {"status": "audit_only", "records": 648, "failures": []},
        }
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "terminal.json"
            summary.write_text(json.dumps(future), encoding="utf-8")
            gate, source = load_gate_source("terminal", STATUS, summary)
            report = build_report(gate, "terminal", source, ROOT)
        text = _all_text(report)
        self.assertIn("terminal_success", text)
        self.assertIn("manifest-terminal", text)
        self.assertIn("pass", text)
        self.assertIn("648", text)
        self.assertIn("audit_only", text)

    def test_report_write_refuses_nonempty_directory(self):
        report = {"title": "test", "sections": []}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "report_v1"
            path = write_report(report, out)
            self.assertTrue(path.is_file())
            with self.assertRaises(GateReportError):
                write_report(report, out)

    def test_terminal_requires_summary(self):
        with self.assertRaises(GateReportError):
            load_gate_source("terminal", STATUS)


if __name__ == "__main__":
    unittest.main()
