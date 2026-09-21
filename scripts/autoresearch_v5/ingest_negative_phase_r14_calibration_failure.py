#!/usr/bin/env python3
"""接入 R14 L80 校准失败证据，不改 controller。"""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any

from ingest_negative_phase_r6 import load, relative, sha256, verify_checksums, write_json
from ingest_negative_phase_r7_failure import canonical_sha256


CELL = "nega-r14-a0050-b0500-L080"
KEY = (-0.05, 0.5, 80)
MODES = ("center", "ferro_j2")
FLAGS = {"center": {"variance_sz1_per_site_le_1e-8"},
         "ferro_j2": {"variance_sz0_per_site_le_1e-8", "variance_sz1_per_site_le_1e-8"}}
R6_HALF = 0.011877542575884303


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-dir", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--phase-dir", type=Path, required=True)
    return parser.parse_args()


def key(params: dict[str, Any]) -> tuple[float, float, int]:
    return float(params["alpha"]), float(params["beta"]), int(params["L"])


def finite(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{label} 不是有限数")
    return float(value)


def forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return any(name in {"value", "error"} or forbidden(item) for name, item in value.items())
    if isinstance(value, list):
        return any(forbidden(item) for item in value)
    return False


def main() -> int:
    args = parse_args()
    fetch, spec_path, phase = args.fetch_dir.resolve(), args.run_spec.resolve(), args.phase_dir.resolve()
    run = fetch / CELL
    paths = {"manifest": run / "manifest.json", "validation": fetch / "validation.json",
             "receipt": fetch / "fetch-receipt.json", "preview": fetch / "fetch-preview.json",
             "r13_summary": phase / "r13_success_ingestion_summary.json",
             "r13_audit": phase / "r13_success_ingestion_audit.json",
             "calibration": phase / "accepted_calibration_through_r9.json",
             "observations": phase / "observations.json", "actions": phase / "action_index.json"}
    for path in (spec_path, *paths.values()):
        if not path.is_file(): raise FileNotFoundError(path)
    spec = load(spec_path)
    cells, settings, provenance = spec.get("cells", []), spec.get("settings", {}), spec.get("provenance", {})
    target = next((row for row in cells if row.get("cell_id") == CELL), None)
    if (
        len(cells) != 4 or not target or key(target.get("params", {})) != KEY or target.get("budget") != 64
        or target.get("calibration_only") is not True or target.get("controller_action_id") is not None
        or settings.get("maxdim_by_L", {}).get("80") != 1200 or settings.get("q_count") != 401
        or settings.get("acceptance", {}).get("variance_per_site_max") != 1e-8
        or provenance.get("r13_success_ingestion_summary_sha256") != sha256(paths["r13_summary"])
        or provenance.get("r13_success_ingestion_audit_sha256") != sha256(paths["r13_audit"])
        or provenance.get("accepted_calibration_through_r9_sha256") != sha256(paths["calibration"])
        or provenance.get("observations_sha256") != sha256(paths["observations"])
        or provenance.get("action_index_sha256") != sha256(paths["actions"])
        or provenance.get("r6_initial_state_sensitivity_half_difference") != R6_HALF
        or provenance.get("r7_failure_provenance_preserved") is not True
        or provenance.get("r12_and_earlier_history_preserved") is not True
        or provenance.get("thresholds_relaxed") is not False
    ): raise ValueError("R14 身份、R13 基线或严格门不匹配")
    receipt, preview = load(paths["receipt"]), load(paths["preview"])
    if (
        receipt.get("status") != "pass" or receipt.get("non_clobbering") is not True
        or receipt.get("cell_id") != CELL or Path(receipt.get("destination", "")).resolve() != run
        or receipt.get("manifest_sha256") != sha256(paths["manifest"])
        or receipt.get("preview_sha256") != sha256(paths["preview"])
        or preview.get("status") != "pass" or preview.get("remote_checksum_status") != "pass"
        or preview.get("destination_exists") is not False
        or Path(preview.get("local_destination", "")).resolve() != run
    ): raise ValueError("R14 回传身份或非覆盖门失败")
    parent_hashes = verify_checksums(run)
    child_hashes = {mode: verify_checksums(run / f"start_{mode}") for mode in MODES}
    validation, manifest = load(paths["validation"]), load(paths["manifest"])
    if (
        validation.get("status") != "fail" or validation.get("cell_id") != CELL
        or validation.get("checks", {}).get("terminal_acceptance") is not False
        or any(passed is not True for name, passed in validation.get("checks", {}).items() if name != "terminal_acceptance")
        or manifest.get("status") != "failed" or manifest.get("accepted") is not False
    ): raise ValueError("R14 validator 或父终态不匹配")
    diagnostics = {}
    for mode in MODES:
        child = load(run / f"start_{mode}/manifest.json")
        false_flags = {name for name, passed in child.get("acceptance", {}).items() if passed is False}
        diag, obs = child.get("diagnostics", {}), child.get("observables", {})
        values = {"variance_per_site_sz0": finite(diag.get("variance_per_site_sz0"), f"{mode}.var0"),
                  "variance_per_site_sz1": finite(diag.get("variance_per_site_sz1"), f"{mode}.var1"),
                  "final_truncation_error_sz0": finite(diag.get("final_truncation_error_sz0"), f"{mode}.trunc0"),
                  "final_truncation_error_sz1": finite(diag.get("final_truncation_error_sz1"), f"{mode}.trunc1"),
                  "total_sz0": finite(diag.get("total_sz0"), f"{mode}.sz0"),
                  "total_sz1": finite(diag.get("total_sz1"), f"{mode}.sz1"),
                  "spin_gap": finite(obs.get("spin_gap"), f"{mode}.gap")}
        if (
            child.get("accepted") is not False or false_flags != FLAGS[mode]
            or max(values["final_truncation_error_sz0"], values["final_truncation_error_sz1"]) > 1e-9
            or abs(values["total_sz0"]) > 1e-8 or abs(values["total_sz1"] - 1) > 1e-8
            or values["spin_gap"] < -1e-8
        ): raise ValueError(f"R14 {mode} 失败模式不匹配")
        diagnostics[mode] = values
    pre_obs, pre_actions, cal_hash = sha256(paths["observations"]), sha256(paths["actions"]), sha256(paths["calibration"])
    validation_summary = fetch / "validation" / "summary.json"
    write_json(validation_summary, {"schema_version": 1, "status": "fail", "cell_count": 1,
        "counts": {"pass": 0, "fail": 1}, "unmaterialized_cells": 3,
        "rows": [{"cell_id": CELL, "validator_status": "fail", "exit_code": 1,
                  "output": str(paths["validation"]), "sha256": sha256(paths["validation"])}]})
    handoff_audit = fetch / "handoff_audit.json"
    write_json(handoff_audit, {"schema_version": 1, "status": "pass_failure_only", "cell_id": CELL,
        "remote_checksums": "parent_and_two_children_pass", "local_checksums": "pass", "non_clobbering_fetch": True,
        "checksum_entries": {"parent": len(parent_hashes), "children": {k: len(v) for k, v in child_hashes.items()}},
        "validator": {"status": "fail", "sha256": sha256(paths["validation"])},
        "accepted_only_eligible": False, "thresholds_relaxed": False})
    failure = {"schema_version": 1, "status": "failed_calibration", "cell_id": CELL,
        "params": {"alpha": -0.05, "beta": 0.5, "L": 80}, "budget": 64,
        "artifact": relative(paths["validation"]), "manifest": relative(paths["manifest"]),
        "receipt": relative(paths["receipt"]), "failed_gates": {k: sorted(v) for k, v in FLAGS.items()},
        "strict_numerical_diagnostics": diagnostics, "accepted_only_eligible": False,
        "validation_summary": {"artifact": relative(validation_summary), "sha256": sha256(validation_summary)},
        "handoff_audit": {"artifact": relative(handoff_audit), "sha256": sha256(handoff_audit)},
        "r13_and_earlier_provenance_preserved": True, "r6_half_difference": R6_HALF,
        "thresholds_relaxed": False}
    if forbidden(failure): raise ValueError("R14 calibration failure 含 value/error")
    handoff = fetch / "failure_handoff_summary.json"
    write_json(handoff, failure)
    failed_calibration = phase / "failed_calibration_r14.json"
    write_json(failed_calibration, failure | {"failure_handoff": {"artifact": relative(handoff), "sha256": sha256(handoff)}})
    if sha256(paths["observations"]) != pre_obs or sha256(paths["actions"]) != pre_actions or sha256(paths["calibration"]) != cal_hash:
        raise ValueError("R14 calibration failure 意外修改 controller 或 accepted calibration")
    audit_path = phase / "r14_failure_ingestion_audit.json"
    write_json(audit_path, {"schema_version": 1, "status": "pass_calibration_failure_only",
        "controller_counts": {"success": 14, "failed": 0, "pending": 2}, "calibration_accepted_total": 6,
        "observations_unchanged": True, "action_index_unchanged": True, "accepted_calibration_unchanged": True,
        "r13_and_earlier_provenance_preserved": True, "thresholds_relaxed": False,
        "crossing_assigned": False, "phase_label_assigned": False})
    summary_path = phase / "r14_failure_ingestion_summary.json"
    summary = {"schema_version": 1, "status": "blocked_calibration_failure", "cell_id": CELL,
        "counts": {"controller_success_total": 14, "controller_failed_total": 0,
                   "controller_pending_total": 2, "calibration_accepted_total": 6},
        "failed_calibration": {"artifact": relative(failed_calibration), "sha256": sha256(failed_calibration)},
        "failure_handoff": {"artifact": relative(handoff), "sha256": sha256(handoff)},
        "ingestion_audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
        "observations": {"artifact": relative(paths["observations"]), "sha256": sha256(paths["observations"])},
        "action_index": {"artifact": relative(paths["actions"]), "sha256": sha256(paths["actions"])},
        "accepted_calibration": {"artifact": relative(paths["calibration"]), "sha256": sha256(paths["calibration"])},
        "thresholds_relaxed": False}
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
