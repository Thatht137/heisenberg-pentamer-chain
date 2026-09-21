"""发布/启动预检测试；fixture 只复制既有证据，不运行 Julia 或网络。"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
import static_krylov_launch_preflight as preflight  # noqa: E402


class StaticKrylovLaunchPreflightTests(unittest.TestCase):
    def test_upload_preview_is_local_and_keeps_exact_18_inputs(self):
        result = preflight.build_preflight(
            "upload", preflight.ROOT / preflight.RELEASE_REL / "server_upload_manifest.json"
        )
        self.assertFalse(result["network_used"])
        self.assertEqual(result["base_input_count"], 18)
        self.assertEqual(result["additional_file_count"], 10)
        self.assertFalse(result["launch_ready"])

    def test_current_v3_k8_evidence_is_launch_ready(self):
        result = preflight.build_preflight(
            "launch", preflight.ROOT / preflight.RELEASE_REL / "server_upload_manifest.json"
        )
        self.assertTrue(result["launch_ready"])
        self.assertEqual(result["evidence"]["k8_cases"], ["a-0100-k8", "a-0175-k8"])
        self.assertFalse(result["evidence"]["historical_all_cases_gate"])
        self.assertTrue(result["evidence"]["historical_k3_gate_nonblocking"])

    def _copy_evidence(self, target: Path) -> None:
        shutil.copytree(preflight.ROOT / preflight.V2_REL, target / preflight.V2_REL)
        shutil.copytree(preflight.ROOT / preflight.V3_REL, target / preflight.V3_REL)
        for relative in preflight.REQUIRED_SOURCES:
            source = preflight.ROOT / relative
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def test_missing_k8_wrapper_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            self._copy_evidence(target)
            (target / preflight.V3_REL / "a-0175-k8" / "wrapper_run.json").unlink()
            with self.assertRaises(preflight.PreflightError):
                preflight.validate_k8_evidence(target)

    def test_non_boolean_gate_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            self._copy_evidence(target)
            # 缓存门本身不再作为数值证据；篡改原始指标应被拒绝。
            metrics_path = target / preflight.V3_REL / "a-0175-k8" / "metrics.csv"
            text = metrics_path.read_text(encoding="utf-8").replace("total_sz1,0.9999999999999999", "total_sz1,0.0")
            metrics_path.write_text(text, encoding="utf-8")
            with self.assertRaises(preflight.PreflightError):
                preflight.validate_k8_evidence(target)

    def test_v2_v3_source_hash_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            self._copy_evidence(target)
            metadata_path = target / preflight.V3_REL / "run_metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["source_hashes_before"]["src/hamiltonian.jl"] = "0" * 64
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaises(preflight.PreflightError):
                preflight.validate_k8_evidence(target)

    def test_ed_source_hash_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            self._copy_evidence(target)
            metadata_path = target / preflight.V3_REL / "run_metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["source_hashes_before"]["scripts/autoresearch_v5/static_krylov_ed_reference.py"] = "0" * 64
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaises(preflight.PreflightError):
                preflight.validate_k8_evidence(target)

    def test_metrics_tamper_rejected_even_when_wrapper_cached_pass(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            self._copy_evidence(target)
            metrics_path = target / preflight.V3_REL / "a-0175-k8" / "metrics.csv"
            text = metrics_path.read_text(encoding="utf-8").replace("state_norm_sz0,1.0", "state_norm_sz0,0.5")
            metrics_path.write_text(text, encoding="utf-8")
            with self.assertRaises(preflight.PreflightError):
                preflight.validate_k8_evidence(target)

    def test_actual_sweep_norm_and_sz_errors_rejected(self):
        mutations = (
            (preflight.V2_REL, "nsweeps_completed_sz1,16", "nsweeps_completed_sz1,15"),
            (preflight.V2_REL, "state_norm_sz1,1.0", "state_norm_sz1,0.9"),
            (preflight.V3_REL, "total_sz1,0.9999999999999999", "total_sz1,0.0"),
        )
        for relative, old, new in mutations:
            with self.subTest(field=old.split(",", 1)[0]), tempfile.TemporaryDirectory() as raw:
                target = Path(raw)
                self._copy_evidence(target)
                metrics_path = target / relative / ("a-0100-k8" if relative == preflight.V2_REL else "a-0175-k8") / "metrics.csv"
                text = metrics_path.read_text(encoding="utf-8").replace(old, new)
                metrics_path.write_text(text, encoding="utf-8")
                with self.assertRaises(preflight.PreflightError):
                    preflight.validate_k8_evidence(target)

    def test_missing_nan_and_bool_metrics_or_wrapper_rejected(self):
        cases = ("missing", "nan", "bool")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as raw:
                target = Path(raw)
                self._copy_evidence(target)
                metrics_path = target / preflight.V3_REL / "a-0175-k8" / "metrics.csv"
                text = metrics_path.read_text(encoding="utf-8")
                if case == "missing":
                    text = "\n".join(line for line in text.splitlines() if not line.startswith("eigsolve_krylovdim,")) + "\n"
                elif case == "nan":
                    text = text.replace("energy_sz0,-2.2741417761716782", "energy_sz0,nan")
                else:
                    wrapper_path = target / preflight.V3_REL / "a-0175-k8" / "wrapper_run.json"
                    wrapper = json.loads(wrapper_path.read_text(encoding="utf-8"))
                    wrapper["alpha"] = True
                    wrapper_path.write_text(json.dumps(wrapper), encoding="utf-8")
                metrics_path.write_text(text, encoding="utf-8")
                with self.assertRaises(preflight.PreflightError):
                    preflight.validate_k8_evidence(target)

    def test_wrapper_command_protocol_drift_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            self._copy_evidence(target)
            wrapper_path = target / preflight.V2_REL / "a-0100-k8" / "wrapper_run.json"
            wrapper = json.loads(wrapper_path.read_text(encoding="utf-8"))
            wrapper["command"][20] = "7"
            wrapper_path.write_text(json.dumps(wrapper), encoding="utf-8")
            with self.assertRaises(preflight.PreflightError):
                preflight.validate_k8_evidence(target)

    def test_launcher_contains_single_factor_runtime_guards(self):
        launcher = (preflight.ROOT / "scripts/autoresearch_v5/launch_static_krylov_controls.sh").read_text(encoding="utf-8")
        self.assertIn('python3 "$PREFLIGHT" --mode launch', launcher)
        self.assertIn("flock -n 9", launcher)
        self.assertIn("JULIA_NUM_THREADS=8", launcher)
        self.assertIn("TOTAL_WALL=7200", launcher)
        self.assertIn("TERM_GRACE=60", launcher)
        self.assertIn("kill -KILL --", launcher)


if __name__ == "__main__":
    unittest.main()
