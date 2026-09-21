"""v2 预检回归；篡改夹具不代表物理结果。"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import static_krylov_launch_preflight_v2 as preflight  # noqa: E402


class StaticKrylovLaunchPreflightV2Tests(unittest.TestCase):
    def _copy_v4_fixture(self, target: Path) -> None:
        shutil.copytree(preflight.ROOT / preflight.V4_REL, target / preflight.V4_REL)
        metadata = json.loads((target / preflight.V4_REL / "run_metadata.json").read_text(encoding="utf-8"))
        for name in metadata["source_hashes"]:
            source = preflight.ROOT / name
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)

    def _v4_entries(self, root: Path) -> dict[str, dict[str, object]]:
        metadata = json.loads((root / preflight.V4_REL / "run_metadata.json").read_text(encoding="utf-8"))
        names = set(metadata["source_hashes"])
        names.update({
            (preflight.V4_REL / "run_metadata.json").as_posix(),
            (preflight.V4_REL / "manifest.json").as_posix(),
        })
        for case_id in preflight.CASES:
            names.add((preflight.V4_REL / case_id / "wrapper_run.json").as_posix())
            names.update((preflight.V4_REL / case_id / artifact).as_posix() for artifact in preflight.V4_ARTIFACTS)
        return {
            name: {"sha256": preflight.sha256(root / name), "bytes": (root / name).stat().st_size}
            for name in sorted(names)
        }

    def test_actual_v4_and_r2_pass_without_cached_gate(self):
        contract = preflight._validate_r2_spec(preflight.ROOT)
        evidence = preflight.validate_v4_evidence(preflight.ROOT)
        self.assertEqual(contract["cells"], 2)
        self.assertTrue(evidence["launch_ready"])
        self.assertEqual({row["cell_id"] for row in evidence["cases"]}, set(preflight.CASES))

    def test_old_source_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            self._copy_v4_fixture(target)
            metadata_path = target / preflight.V4_REL / "run_metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["source_hashes"][preflight.JULIA_SOURCE] = preflight.OLD_JULIA_SHA
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaises(preflight.PreflightError):
                preflight.validate_v4_evidence(target)

    def test_metrics_tamper_is_rejected_even_when_cached_manifest_passes(self):
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            self._copy_v4_fixture(target)
            metrics_path = target / preflight.V4_REL / "a-0100-k8" / "metrics.csv"
            text = metrics_path.read_text(encoding="utf-8").replace("state_norm_sz0,1.0", "state_norm_sz0,0.5")
            metrics_path.write_text(text, encoding="utf-8")
            with self.assertRaises(preflight.PreflightError):
                preflight.validate_v4_evidence(target)

    def test_missing_enriched_payload_hash_is_rejected(self):
        entries = self._v4_entries(preflight.ROOT)
        entries.pop((preflight.V4_REL / "a-0175-k8" / "entropy_profile_full.csv").as_posix())
        with self.assertRaises(preflight.PreflightError):
            preflight.validate_v4_evidence(preflight.ROOT, entries)

    def test_old_release_manifest_is_rejected(self):
        old = preflight.ROOT / "results/autoresearch_v5_20260919/static_krylov_controls_release_v1/server_upload_manifest.json"
        with self.assertRaises(preflight.PreflightError):
            preflight.validate_release_manifest(old, preflight.ROOT)

    def test_windows_absolute_paths_are_rejected(self):
        for value in (r"C:\bundle\file", "D:/bundle/file", "C:relative", r"\\server\share\file"):
            with self.subTest(value=value), self.assertRaises(preflight.PreflightError):
                preflight._relative_path(value, "fixture")

    def test_release_manifest_self_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path = root / preflight.RELEASE_REL / "server_upload_manifest.json"
            manifest_path.parent.mkdir(parents=True)
            relative = manifest_path.relative_to(root).as_posix()
            manifest = {
                "schema_version": 2,
                "release_id": "static-krylov-controls-release-v2",
                "status": "prepared_only",
                "launch_ready": False,
                "cell_count": 2,
                "concurrency": 1,
                "stop_on_first_failure": True,
                "remote_run_dir": preflight.R2_REL.as_posix(),
                "control_path": relative,
                "files": [{"path": relative, "sha256": "0" * 64, "bytes": 0}],
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(preflight.PreflightError, "不得纳入自身"):
                preflight.validate_release_manifest(manifest_path, root)

    def test_release_manifest_requires_v2_preflight_payload(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            manifest_path = root / preflight.RELEASE_REL / "server_upload_manifest.json"
            manifest_path.parent.mkdir(parents=True)
            payload = root / "payload.txt"
            payload.write_text("payload\n", encoding="utf-8")
            relative = manifest_path.relative_to(root).as_posix()
            payload_rel = payload.relative_to(root).as_posix()
            manifest = {
                "schema_version": 2,
                "release_id": "static-krylov-controls-release-v2",
                "status": "prepared_only",
                "launch_ready": False,
                "cell_count": 2,
                "concurrency": 1,
                "stop_on_first_failure": True,
                "remote_run_dir": preflight.R2_REL.as_posix(),
                "control_path": relative,
                "files": [{"path": payload_rel, "sha256": preflight.sha256(payload), "bytes": payload.stat().st_size}],
            }
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(preflight.PreflightError, "依赖未被 release manifest 覆盖"):
                preflight.validate_release_manifest(manifest_path, root)


if __name__ == "__main__":
    unittest.main()
