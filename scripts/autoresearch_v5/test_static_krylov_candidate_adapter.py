"""只用合成数据测试桥接完整性；所有 fixture 都不代表物理结果。"""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parent))
import static_krylov_candidate_adapter as adapter  # noqa: E402
from compare_static_krylov_controls import compare_records  # noqa: E402


BASE_METADATA = {
    "alpha": -0.1,
    "beta": 0.25,
    "L": 80,
    "nsweeps": 64,
    "maxdim": 1200,
    "cutoff": 1e-11,
    "eigsolve_krylovdim": 3,
}
CANDIDATE_METADATA = {**BASE_METADATA, "eigsolve_krylovdim": 8}


def synthetic_records(alpha: float) -> list[dict[str, object]]:
    """小型非物理配对 fixture。"""
    return [
        {"alpha": alpha, "beta": 0.25, "L": 80, "start": "center", "observable": "gap", "index": 0, "value": 1.0},
        {"alpha": alpha, "beta": 0.25, "L": 80, "start": "ferro_j2", "observable": "gap", "index": 0, "value": 1.0},
    ]


class StaticKrylovCandidateAdapterTests(unittest.TestCase):
    def test_complete_synthetic_match_is_audit_only_with_key_deltas(self):
        baseline_points = {}
        candidate_points = {}
        baseline_metadata = {}
        candidate_metadata = {}
        for point_id, point in adapter.POINTS.items():
            baseline_points[point_id] = synthetic_records(point["alpha"])
            candidate_points[point_id] = {"records": synthetic_records(point["alpha"]), "metadata": {**CANDIDATE_METADATA, "alpha": point["alpha"]}}
            baseline_metadata[point_id] = {**BASE_METADATA, "alpha": point["alpha"]}
            candidate_metadata[point_id] = {**CANDIDATE_METADATA, "alpha": point["alpha"]}
        baseline = {"status": "baseline_verified", "points": baseline_points, "metadata": baseline_metadata, "provenance": {"artifact": "synthetic"}}
        candidate = {"status": "candidate_verified", "points": candidate_points, "provenance": {"artifact": "synthetic"}}
        with patch.object(adapter, "load_baseline_dataset", return_value=baseline), patch.object(adapter, "extract_candidate_dataset", return_value=candidate):
            result = adapter.audit(Path("synthetic-baseline"), Path("synthetic-baseline-spec"), Path("synthetic-candidate"), Path("synthetic-candidate-spec"))
        self.assertEqual(result["status"], "audit_only")
        self.assertEqual(result["claim"], "none")
        self.assertEqual(set(result["comparisons"]), set(adapter.POINTS))
        self.assertEqual(result["comparisons"][next(iter(adapter.POINTS))]["records"][0]["abs_delta"], 0.0)

    def test_candidate_missing_is_explicit(self):
        with tempfile.TemporaryDirectory() as raw:
            result = adapter.extract_candidate_dataset(Path(raw) / "not-produced", Path(raw) / "run-spec.json")
        self.assertEqual(result["status"], "candidate_missing")
        self.assertEqual(result["points"], {})

    def test_checksum_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            names = sorted(set(adapter.CHECKSUM_PARENT_FILES + adapter.CHECKSUM_CHILD_FILES))
            for name in names:
                (directory / name).write_text(f"synthetic {name}\n", encoding="utf-8")
            lines = [f"{hashlib.sha256((directory / name).read_bytes()).hexdigest()}  {name}" for name in names]
            (directory / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
            self.assertEqual(adapter.checksum_failures(directory, adapter.CHECKSUM_PARENT_FILES), [])
            self.assertEqual(adapter.checksum_failures(directory, adapter.CHECKSUM_CHILD_FILES), [])
            (directory / "checksums.sha256").write_text("\n".join(line for line in lines if not line.endswith("metrics.csv")) + "\n", encoding="utf-8")
            self.assertTrue(adapter.checksum_failures(directory, adapter.CHECKSUM_CHILD_FILES))
            (directory / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
            (directory / "entropy_profile_full.csv").write_text("tampered\n", encoding="utf-8")
            self.assertTrue(adapter.checksum_failures(directory, adapter.CHECKSUM_CHILD_FILES))

    def _write_metrics(self, directory: Path, **overrides: object) -> Path:
        values = {
            "energy_sz0": -1.0, "energy_sz1": -0.9,
            "total_sz0": 0.0, "total_sz1": 1.0,
            "state_norm_sz0": 1.0, "state_norm_sz1": 1.0,
            "nsweeps_completed_sz0": 64, "nsweeps_completed_sz1": 64,
        }
        values.update(overrides)
        path = directory / "metrics.csv"
        path.write_text("metric,value\n" + "\n".join(f"{key},{value}" for key, value in values.items()) + "\n", encoding="utf-8")
        return path

    def test_metrics_state_norm_gate_rejects(self):
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(adapter.AdapterError):
                adapter.read_metrics(self._write_metrics(Path(raw), state_norm_sz1=0.999999))

    def test_metrics_sector_gate_rejects(self):
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(adapter.AdapterError):
                adapter.read_metrics(self._write_metrics(Path(raw), total_sz1=0.0))

    def test_metrics_sweep_gate_rejects(self):
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(adapter.AdapterError):
                adapter.read_metrics(self._write_metrics(Path(raw), nsweeps_completed_sz0=63))

    def test_missing_start_and_observable_stay_unusable(self):
        with tempfile.TemporaryDirectory() as raw:
            child = Path(raw) / "start_ferro_j2"
            missing = adapter.missing_files(child, adapter.REQUIRED_CHILD_FILES)
            self.assertTrue(any(path.endswith("state_sz0.jld2") for path in missing))
            child.mkdir()
            (child / "manifest.json").write_text('{"observables": {}}', encoding="utf-8")
            with self.assertRaises(adapter.AdapterError):
                adapter._candidate_records(child, adapter.POINTS["negdiag-a01000-b02500-L080"], "ferro_j2")

    def test_wrong_krylov_and_bool_are_rejected(self):
        with self.assertRaises(adapter.AdapterError):
            adapter.require_krylov(True, 8, "synthetic.krylov")
        with self.assertRaises(adapter.AdapterError):
            adapter.require_krylov(7, 8, "synthetic.krylov")

    def test_metadata_drift_and_duplicate_key_are_rejected(self):
        records = synthetic_records(-0.1)
        with self.assertRaises(ValueError):
            compare_records(records, records, BASE_METADATA, {**CANDIDATE_METADATA, "cutoff": 1e-10})
        with self.assertRaises(ValueError):
            compare_records(records + [records[0]], records, BASE_METADATA, CANDIDATE_METADATA)

    def test_run_spec_budget_and_point_drift_are_rejected(self):
        settings = {
            "sectors": ["Sz=0", "Sz=1"], "nsweeps": 64, "maxdim_by_L": {"80": 1200}, "cutoff": 1e-11,
            "threads": 8, "q_count": 401, "init_modes": ["center", "ferro_j2"], "noise_profile": "legacy",
            "random_seed": 20260811, "variance_per_site_max": 5e-8, "save_state": True, "enriched_diagnostics": True,
            "eigsolve_krylovdim": 8, "eigsolve_maxiter": 1, "eigsolve_tol": 1e-14,
            "warmstart": False, "retry_policy": "none", "maxdim_escalation": False,
        }
        run_spec = {"settings": settings, "cells": [{"cell_id": "negdiag-a01000-b02500-L080-k08", "params": {"alpha": -0.1, "beta": 0.25, "L": 80, "n_units": 16, "eigsolve_krylovdim": 8}, "budget": 63}, {"cell_id": "negdiag-a01750-b02500-L080-k08", "params": {"alpha": -0.175, "beta": 0.25, "L": 80, "n_units": 16, "eigsolve_krylovdim": 8}, "budget": 64}]}
        expected = adapter._metadata(settings, {"alpha": -0.1, "beta": 0.25, "L": 80, "n_units": 16}, 8)
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_run_spec(run_spec, expected)
        run_spec["cells"][0]["budget"] = 64
        run_spec["cells"][1]["params"]["alpha"] = -0.1
        with self.assertRaises(adapter.AdapterError):
            adapter.validate_run_spec(run_spec, expected)


if __name__ == "__main__":
    unittest.main()
