"""静态 Krylov 影响审计的最小完整性测试。"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import analyze_static_krylov_impact as analysis
import static_krylov_candidate_adapter as adapter


CANDIDATE = ROOT / "results/autoresearch_v5_20260920/static_krylov_controls_r2_fetch_0945"
BASELINE = ROOT / "results/autoresearch_v5_20260920/static_krylov_baseline_v3"
BASELINE_SPEC = ROOT / "results/autoresearch_v5_20260913/negative_phase_independent_pilot_r1/parameter-scan.run_spec.json"
CANDIDATE_SPEC = ROOT / "results/autoresearch_v5_20260919/static_krylov_controls_r2/parameter-scan.run_spec.json"
COMPARISON = ROOT / "results/autoresearch_v5_20260920/static_krylov_controls_r2_comparison_20260920/comparison.json"


class StaticKrylovImpactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.audit = adapter.audit(BASELINE, BASELINE_SPEC, CANDIDATE, CANDIDATE_SPEC)
        _, cls.records = analysis.validate_comparison(COMPARISON)

    def test_real_cells_and_mixed_metrics(self):
        point = "negdiag-a01000-b02500-L080"
        child = analysis.candidate_cell_dir(CANDIDATE, point) / "start_center"
        values = analysis.load_manifest_metrics(child / "manifest.json", child / "metrics.csv")
        self.assertEqual(values["krylov"], 8)
        self.assertEqual(values["requested_maxdim"], 1200.0)
        self.assertEqual(values["manifest"]["settings"]["noise_profile"], "legacy")

    def test_adapter_audit_smoke_compares_648_records(self):
        self.assertEqual(self.audit["status"], "audit_only")
        self.assertEqual(self.audit["candidate"], "candidate_verified")
        self.assertEqual(analysis.validate_adapter_audit(self.audit, self.records), 648)

    def test_missing_cell_is_rejected(self):
        with self.assertRaises(ValueError):
            analysis.candidate_cell_dir(CANDIDATE / "missing", "negdiag-a01000-b02500-L080")

    def test_tampered_comparison_is_rejected(self):
        tampered = copy.deepcopy(self.records)
        key = next(iter(tampered))
        tampered[key]["candidate_value"] = float(tampered[key]["candidate_value"]) + 1e-6
        with self.assertRaises(ValueError):
            analysis.validate_adapter_audit(self.audit, tampered)

    def test_generated_v2_outputs_are_audit_only(self):
        output = ROOT / "results/autoresearch_v5_20260920/static_krylov_impact_v2"
        if not output.is_dir():
            self.skipTest("先运行分析脚本生成 v2 输出")
        summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["status"], "audit_only")
        self.assertEqual(summary["validator_provenance"]["comparison_records"], 648)
        self.assertFalse(any(item["role"] == "project_status" for item in json.loads((output / "source_provenance.json").read_text(encoding="utf-8"))["files"]))
        for name in ("entropy_profiles.csv", "static_krylov_impact_v1.svg", "static_krylov_impact_v1.pdf", "static_krylov_impact_v1.png"):
            self.assertTrue((output / name).is_file(), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
