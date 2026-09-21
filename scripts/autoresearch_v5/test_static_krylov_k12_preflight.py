#!/usr/bin/env python3
"""k12 preflight 的合成输入单测，不代表物理结果。"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
import static_krylov_k12_preflight as preflight  # noqa: E402


class K12Fixture:
    def __init__(self, raw: str) -> None:
        self.root = Path(raw)
        self.results = self.root / preflight.RESULTS_REL
        self.release = self.results / preflight.RELEASE_NAME
        self.run = self.results / preflight.RUN_NAME
        self.smoke = self.results / preflight.SMOKE_REL
        self.release.mkdir(parents=True)
        self.run.mkdir(parents=True)
        self.smoke.mkdir(parents=True)
        self.source = self.root / "src" / "synthetic.jl"
        self.source.parent.mkdir(parents=True)
        self.source.write_text("synthetic source\n", encoding="utf-8")
        self._write_smoke()
        self._write_spec()
        self._write_manifest(launch_ready=False)

    def _write_smoke(self) -> None:
        metrics = [
            ("alpha", "-0.1"), ("beta", "0.25"), ("n_units", "2"), ("L", "10"),
            ("structure_factor_q_count", "401"), ("eigsolve_krylovdim", "12"),
            ("eigsolve_maxiter", "1"), ("random_seed_base", "20260811"),
            ("nsweeps_requested", "16"), ("nsweeps_completed_sz0", "16"),
            ("nsweeps_completed_sz1", "16"), ("noise_profile", "legacy"),
            ("init_mode_sz0", "center"), ("init_mode_sz1", "center"),
            ("enriched_diagnostics", "true"),
        ]
        for name in preflight.SMOKE_ARTIFACTS:
            path = self.smoke / name
            if name == "metrics.csv":
                path.write_text(
                    "metric,value\n" + "\n".join(f"{key},{value}" for key, value in metrics) + "\n",
                    encoding="utf-8",
                )
            else:
                path.write_text(f"synthetic {name}\n", encoding="utf-8")

    def _smoke_hashes(self) -> dict[str, str]:
        return {name: self._sha(self.smoke / name) for name in preflight.SMOKE_ARTIFACTS}

    def _write_spec(self) -> None:
        source_digest = self._sha(self.source)
        source_records = {self.source.relative_to(self.root).as_posix(): source_digest}
        smoke_hashes = self._smoke_hashes()
        settings = {
            "method": "finite_dmrg_multistart_saved_state_enriched",
            "boundary": "OBC",
            "sectors": ["Sz=0", "Sz=1"],
            "maxdim_by_L": {"80": 1200},
            "nsweeps": 64,
            "cutoff": 1e-11,
            "threads": 8,
            "q_count": 401,
            "init_modes": ["center", "ferro_j2"],
            "noise_profile": "legacy",
            "random_seed": 20260811,
            "save_state": True,
            "enriched_diagnostics": True,
            "eigsolve_krylovdim": 12,
            "eigsolve_maxiter": 1,
            "eigsolve_tol": 1e-14,
            "warmstart": False,
            "retry_policy": "none",
            "maxdim_escalation": False,
            "execution": "prepared_only; concurrency=1; stop on first failed cell",
        }
        spec = {
            "schema_version": 3,
            "run_id": preflight.RUN_ID,
            "run_dir": self.run.relative_to(self.root).as_posix(),
            "cells": [{
                "cell_id": preflight.CELL_ID,
                "params": {"alpha": -0.1, "beta": 0.25, "L": 80, "n_units": 16, "eigsolve_krylovdim": 12},
                "budget": 64,
                "stage": "static-krylov-k12-single-r1",
            }],
            "settings": settings,
            "future_output_contract": {
                "parent": {
                    "cell_id": preflight.CELL_ID,
                    "required_status": "success",
                    "required_accepted": True,
                    "required_krylovdim": 12,
                    "required_modes": ["center", "ferro_j2"],
                    "required_sectors": ["Sz=0", "Sz=1"],
                },
                "children": {
                    "modes": ["center", "ferro_j2"],
                    "required_status": "success",
                    "required_accepted": True,
                    "required_krylovdim": 12,
                    "required_sectors": ["Sz=0", "Sz=1"],
                    "required_sweeps": 64,
                },
            },
            "acceptance": {
                "status": "prepared_only",
                "success_receipt": False,
                "no_warmstart": True,
                "no_128": True,
                "no_retry": True,
                "parent_child_k12_contract_required": True,
            },
            "provenance": {
                "source_hashes_path": (self.run.relative_to(self.root) / "source_hashes.sha256").as_posix(),
                "source_hashes": source_records,
                "smoke_evidence": {
                    "path": self.smoke.relative_to(self.root).as_posix(),
                    "julia_version": preflight.SMOKE_JULIA,
                    "role": "parser/execution evidence only",
                    "not_remote_validation": True,
                    "remote_julia_version_required": preflight.REMOTE_JULIA,
                    "artifact_names": list(preflight.SMOKE_ARTIFACTS),
                    "artifact_sha256": smoke_hashes,
                    "metrics_checks": {"alpha": -0.1, "beta": 0.25, "L": 10, "eigsolve_krylovdim": 12, "q_count": 401},
                },
                "remote_launch": "not_started",
                "remote_julia_version_required": preflight.REMOTE_JULIA,
            },
        }
        self.spec_path = self.run / "parameter-scan.run_spec.json"
        self.spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
        self.source_hashes_path = self.run / "source_hashes.sha256"
        self.source_hashes_path.write_text(f"{source_digest}  {source_records.keys().__iter__().__next__()}\n", encoding="utf-8")

    def _manifest_entries(self) -> list[dict[str, object]]:
        paths = [
            self.spec_path,
            self.source_hashes_path,
            self.source,
            *(self.smoke / name for name in preflight.SMOKE_ARTIFACTS),
        ]
        return [
            {
                "path": path.relative_to(self.root).as_posix(),
                "sha256": self._sha(path),
                "bytes": path.stat().st_size,
            }
            for path in paths
        ]

    def _write_manifest(self, launch_ready: bool) -> None:
        manifest = {
            "schema_version": 3,
            "release_id": preflight.RELEASE_ID,
            "release_version": 3,
            "status": "launch_ready" if launch_ready else "prepared_only",
            "launch_ready": launch_ready,
            "network_used": False,
            "target": preflight.REMOTE_TARGET,
            "remote_run_dir": preflight.REMOTE_RUN,
            "control_path": (self.release / "server_upload_manifest.json").relative_to(self.root).as_posix(),
            "cell_count": 1,
            "concurrency": 1,
            "stop_on_first_failure": True,
            "retry_policy": "none",
            "krylovdim": 12,
            "expected_remote_julia_version": preflight.REMOTE_JULIA,
            "files": self._manifest_entries(),
        }
        self.manifest_path = self.release / "server_upload_manifest.json"
        self.manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    def set_launch_ready(self, value: bool) -> None:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        manifest["launch_ready"] = value
        manifest["status"] = "launch_ready" if value else "prepared_only"
        self.manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


class StaticKrylovK12PreflightTests(unittest.TestCase):
    def test_upload_is_read_only_and_passes_prepared_release(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = K12Fixture(raw)
            result = preflight.validate_package(fixture.root, fixture.release, fixture.run, fixture.smoke, "upload")
            self.assertEqual(result["status"], "pass")
            self.assertFalse(result["network_used"])
            self.assertFalse(result["launch_ready"])
            self.assertEqual(result["settings"]["krylovdim"], 12)
            self.assertEqual(result["settings"]["nsweeps"], 64)
            self.assertEqual(result["settings"]["init_modes"], ["center", "ferro_j2"])

    def test_launch_requires_manifest_ready_then_passes(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = K12Fixture(raw)
            result = preflight.validate_package(fixture.root, fixture.release, fixture.run, fixture.smoke, "launch")
            self.assertTrue(result["launch_ready"])
            self.assertFalse(result["network_used"])
            manifest = json.loads(fixture.manifest_path.read_text(encoding="utf-8"))
            self.assertFalse(manifest["launch_ready"])

    def test_cli_accepts_manifest_prepare_and_dynamic_launch_flag(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = K12Fixture(raw)
            output = io.StringIO()
            with redirect_stdout(output):
                code = preflight.main([
                    "--mode", "prepare",
                    "--manifest", str(fixture.manifest_path),
                    "--root", str(fixture.root),
                    "--json",
                ])
            self.assertEqual(code, 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result["status"], "prepared_only")
            self.assertFalse(result["launch_ready"])
            self.assertFalse(result["network_used"])
            output = io.StringIO()
            with redirect_stdout(output):
                code = preflight.main([
                    "--mode", "launch",
                    "--manifest", str(fixture.manifest_path),
                    "--root", str(fixture.root),
                    "--json",
                ])
            self.assertEqual(code, 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result["status"], "prepared_only")
            self.assertTrue(result["launch_ready"])

    def test_v2_and_path_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = K12Fixture(raw)
            with self.assertRaises(preflight.PreflightError):
                preflight.validate_package(
                    fixture.root,
                    fixture.release.parent / "static_krylov_controls_release_v2",
                    fixture.run,
                    fixture.smoke,
                    "upload",
                )
            with self.assertRaises(preflight.PreflightError):
                preflight.validate_package(
                    fixture.root,
                    fixture.root.parent / "static_krylov_controls_release_v3",
                    fixture.run,
                    fixture.smoke,
                    "upload",
                )

    def test_manifest_file_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = K12Fixture(raw)
            fixture.source.write_text("tampered\n", encoding="utf-8")
            with self.assertRaises(preflight.PreflightError):
                preflight.validate_package(fixture.root, fixture.release, fixture.run, fixture.smoke, "upload")

    def test_source_hash_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = K12Fixture(raw)
            fixture.source_hashes_path.write_text("0" * 64 + "  src/synthetic.jl\n", encoding="utf-8")
            with self.assertRaises(preflight.PreflightError):
                preflight.validate_package(fixture.root, fixture.release, fixture.run, fixture.smoke, "upload")

    def test_smoke_krylov_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = K12Fixture(raw)
            path = fixture.smoke / "metrics.csv"
            path.write_text(path.read_text(encoding="utf-8").replace("eigsolve_krylovdim,12", "eigsolve_krylovdim,8"), encoding="utf-8")
            with self.assertRaises(preflight.PreflightError):
                preflight.validate_package(fixture.root, fixture.release, fixture.run, fixture.smoke, "upload")

    def test_run_spec_wrong_budget_is_rejected_after_manifest_refresh(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = K12Fixture(raw)
            spec = json.loads(fixture.spec_path.read_text(encoding="utf-8"))
            spec["cells"][0]["budget"] = 128
            fixture.spec_path.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
            fixture._write_manifest(launch_ready=False)
            with self.assertRaises(preflight.PreflightError):
                preflight.validate_package(fixture.root, fixture.release, fixture.run, fixture.smoke, "upload")


if __name__ == "__main__":
    unittest.main()
