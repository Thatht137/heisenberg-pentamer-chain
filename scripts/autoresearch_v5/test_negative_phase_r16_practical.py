#!/usr/bin/env python3
"""测试 R16 实用裁决的通过、篡改和核心门失败路径。"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from adjudicate_negative_phase_r16_practical import CELL, MODES, RESULTS, ROOT, adjudicate, sha256
from test_negative_phase_r16_protocol import make_fixture, write_checksums, write_json


def prepare(root: Path) -> tuple[Path, Path, Path]:
    run, spec = make_fixture(root)
    for mode in MODES:
        manifest_path = run / f"start_{mode}" / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["accepted"] = False
        manifest["diagnostics"]["final_energy_change_sz0"] = 5e-8
        manifest["acceptance"]["energy_plateau_sz0"] = False
        write_json(manifest_path, manifest)
        write_json(run / f"start_{mode}" / "status.json",
                   {"status": "success", "accepted": False, "returncode": 0})
        write_checksums(manifest_path.parent)
    parent_path = run / "manifest.json"
    parent = json.loads(parent_path.read_text(encoding="utf-8"))
    parent["status"] = "failed"
    parent["accepted"] = False
    parent["acceptance"]["children_accepted"] = False
    write_json(parent_path, parent)
    write_json(run / "status.json", {"status": "failed", "accepted": False, "returncode": 1})
    write_checksums(run)
    preview = {"schema_version": 1, "status": "pass", "cell_id": CELL,
               "local_destination": str(run.resolve()), "destination_exists": False,
               "remote_checksum_status": "pass"}
    write_json(root / "preview.json", preview)
    receipt = {"schema_version": 1, "status": "pass", "cell_id": CELL,
               "destination": str(run.resolve()), "non_clobbering": True,
               "preview_sha256": sha256(root / "preview.json"),
               "manifest_sha256": sha256(parent_path)}
    write_json(root / "receipt.json", receipt)
    strict = {"schema_version": 1, "status": "fail", "cell_id": CELL,
              "run_dir": str(run.resolve()), "run_spec": str(spec.resolve()),
              "checks": {"energy_plateau": False, "terminal_acceptance": False},
              "failures": ["synthetic strict energy plateau failure"]}
    strict_path = root / "validation.json"
    write_json(strict_path, strict)
    return run, spec, strict_path


def result_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {"status": result["status"], "checks": result["checks"], "failures": result["failures"]}


def prepare_phase(root: Path, spec_path: Path) -> Path:
    phase = root / "phase"
    actions = {"schema_version": 1, "actions": [
        {"observation_status": "success" if index < 14 else "pending"} for index in range(16)]}
    observations = {"schema_version": 1, "records": [{"status": "success"}]}
    calibration = {"schema_version": 1, "sources": [], "records": [
        {"params": {"alpha": alpha, "beta": 0.5, "L": 80}, "status": "success",
         "value": 0.2, "error": 0.01} for alpha in (-1.0, -0.75, -0.5, -0.35, -0.25, -0.1)]}
    files = {
        "action_index.json": actions, "observations.json": observations,
        "accepted_calibration_through_r9.json": calibration,
        "r15_terminal_ingestion_summary.json": {"status": "failed_calibration_final_tier"},
        "r15_terminal_ingestion_audit.json": {"status": "pass"},
        "failed_calibration_r15.json": {"status": "failed_calibration", "cell_id": "nega-r15-a0050-b0500-L080"},
    }
    for name, value in files.items():
        write_json(phase / name, value)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["provenance"].update({
        "r15_terminal_ingestion_summary_sha256": sha256(phase / "r15_terminal_ingestion_summary.json"),
        "r15_terminal_ingestion_audit_sha256": sha256(phase / "r15_terminal_ingestion_audit.json"),
        "r15_failed_calibration_sha256": sha256(phase / "failed_calibration_r15.json"),
        "accepted_calibration_through_r9_sha256": sha256(phase / "accepted_calibration_through_r9.json"),
        "observations_sha256": sha256(phase / "observations.json"),
        "action_index_sha256": sha256(phase / "action_index.json"),
    })
    write_json(spec_path, spec)
    return phase


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="r16-practical-", dir=RESULTS) as temporary:
        base = Path(temporary)
        pass_run, pass_spec, pass_strict = prepare(base / "pass")
        phase = prepare_phase(base / "pass", pass_spec)
        passed = adjudicate(pass_run.parent, pass_spec, pass_strict)
        if (passed["status"] != "pass" or passed["decision"] != "accepted_practical_calibration"
                or passed["boundary_eligible"] is not False or not all(passed["checks"].values())):
            raise AssertionError(f"实用合成 PASS 未通过: {result_summary(passed)}")
        adjudication_path = pass_run.parent / "practical_adjudication.json"
        write_json(adjudication_path, passed)
        before = {name: sha256(phase / name) for name in ("observations.json", "action_index.json")}
        completed = subprocess.run([
            sys.executable, str(ROOT / "scripts/autoresearch_v5/ingest_negative_phase_r16_practical.py"),
            "--fetch-dir", str(pass_run.parent), "--run-spec", str(pass_spec),
            "--adjudication", str(adjudication_path), "--phase-dir", str(phase),
        ], cwd=ROOT, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise AssertionError(f"实用 ingestion 失败: {completed.stderr or completed.stdout}")
        calibration = json.loads((phase / "accepted_calibration_through_r16.json").read_text(encoding="utf-8"))
        r16 = next(row for row in calibration["records"] if row["params"]["alpha"] == -0.05)
        if len(calibration["records"]) != 7 or r16.get("boundary_eligible") is not False:
            raise AssertionError("实用 ingestion 未生成 7 条 calibration 或误标边界资格")
        if any(sha256(phase / name) != digest for name, digest in before.items()):
            raise AssertionError("实用 ingestion 修改了 controller 证据")

        tamper_run, tamper_spec, tamper_strict = prepare(base / "tamper")
        target = tamper_run / "start_domain" / "manifest.json"
        tampered = json.loads(target.read_text(encoding="utf-8"))
        tampered["synthetic_tamper"] = True
        write_json(target, tampered)
        tamper = adjudicate(tamper_run.parent, tamper_spec, tamper_strict)
        if tamper["status"] != "fail" or tamper["checks"]["child_checksums"] is not False:
            raise AssertionError("实用裁决未拒绝 checksum 篡改")

        core_run, core_spec, core_strict = prepare(base / "core")
        core_path = core_run / "start_center_random" / "manifest.json"
        core = json.loads(core_path.read_text(encoding="utf-8"))
        core["diagnostics"]["variance_per_site_sz0"] = 2e-8
        core["acceptance"]["variance_sz0_per_site_le_1e-8"] = False
        write_json(core_path, core)
        write_checksums(core_path.parent)
        core_fail = adjudicate(core_run.parent, core_spec, core_strict)
        if (core_fail["status"] != "fail" or core_fail["checks"]["core_gates"] is not False
                or core_fail["checks"]["child_checksums"] is not True):
            raise AssertionError(f"实用裁决核心门失败路径错误: {result_summary(core_fail)}")
        print(json.dumps({"status": "pass", "cases": {"practical_pass": passed["status"],
              "tamper": tamper["status"], "core_gate": core_fail["status"]}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
