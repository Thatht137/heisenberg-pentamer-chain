#!/usr/bin/env python3
"""汇总 R12 首单元失败并锁定回传证据。"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from ingest_negative_phase_r6 import load, relative, sha256, verify_checksums, write_json


CELL = "nega-r12-a0050-b0500-L060"
KEY = (-0.05, 0.5, 60)
ACTION = "act-7016420e7cbf8fc354b7"
MODES = ("center", "ferro_j2")
FAILED_FLAG = {"variance_sz1_per_site_le_1e-8"}
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


def child(run: Path, mode: str) -> dict[str, float]:
    manifest = load(run / f"start_{mode}" / "manifest.json")
    checks, diag, obs = manifest.get("acceptance", {}), manifest.get("diagnostics", {}), manifest.get("observables", {})
    false_flags = {name for name, passed in checks.items() if passed is False}
    values = {
        "variance_per_site_sz0": finite(diag.get("variance_per_site_sz0"), f"{mode}.var0"),
        "variance_per_site_sz1": finite(diag.get("variance_per_site_sz1"), f"{mode}.var1"),
        "final_truncation_error_sz0": finite(diag.get("final_truncation_error_sz0"), f"{mode}.trunc0"),
        "final_truncation_error_sz1": finite(diag.get("final_truncation_error_sz1"), f"{mode}.trunc1"),
        "total_sz0": finite(diag.get("total_sz0"), f"{mode}.sz0"),
        "total_sz1": finite(diag.get("total_sz1"), f"{mode}.sz1"),
        "spin_gap": finite(obs.get("spin_gap"), f"{mode}.gap"),
    }
    if (
        manifest.get("status") != "success" or manifest.get("accepted") is not False
        or key(manifest.get("params", {})) != KEY or manifest.get("settings", {}).get("nsweeps") != 64
        or manifest.get("settings", {}).get("q_count") != 401 or false_flags != FAILED_FLAG
        or values["variance_per_site_sz0"] > 1e-8 or values["variance_per_site_sz1"] <= 1e-8
        or max(values["final_truncation_error_sz0"], values["final_truncation_error_sz1"]) > 1e-9
        or abs(values["total_sz0"]) > 1e-8 or abs(values["total_sz1"] - 1.0) > 1e-8
        or values["spin_gap"] < -1e-8
    ):
        raise ValueError(f"R12 {mode} 不是仅 Sz1 方差失败")
    return values


def main() -> int:
    args = parse_args()
    fetch, spec_path, phase = args.fetch_dir.resolve(), args.run_spec.resolve(), args.phase_dir.resolve()
    run = fetch / CELL
    paths = {
        "manifest": run / "manifest.json", "validation": fetch / "validation" / f"{CELL}.json",
        "receipt": fetch / "receipts" / f"{CELL}.json", "preview": fetch / "previews" / f"{CELL}.json",
        "r11_summary": phase / "r11_success_ingestion_summary.json",
        "r11_audit": phase / "r11_success_ingestion_audit.json",
        "calibration": phase / "accepted_calibration_through_r9.json",
        "observations": phase / "observations.json", "actions": phase / "action_index.json",
    }
    for path in (spec_path, *paths.values()):
        if not path.is_file():
            raise FileNotFoundError(path)
    spec = load(spec_path)
    cells, settings, provenance = spec.get("cells", []), spec.get("settings", {}), spec.get("provenance", {})
    target = next((row for row in cells if row.get("cell_id") == CELL), None)
    if (
        len(cells) != 5 or not target or key(target.get("params", {})) != KEY or target.get("budget") != 64
        or target.get("controller_action_id") != ACTION or target.get("budget_promotion_reason") is None
        or settings.get("maxdim_by_L", {}).get("60") != 1000 or settings.get("threads") != 8
        or settings.get("q_count") != 401 or settings.get("acceptance", {}).get("variance_per_site_max") != 1e-8
        or settings.get("acceptance", {}).get("spin_gap_min") != -1e-8
        or provenance.get("r11_success_ingestion_summary_sha256") != sha256(paths["r11_summary"])
        or provenance.get("r11_success_ingestion_audit_sha256") != sha256(paths["r11_audit"])
        or provenance.get("accepted_calibration_through_r9_sha256") != sha256(paths["calibration"])
        or provenance.get("observations_sha256") != sha256(paths["observations"])
        or provenance.get("action_index_sha256") != sha256(paths["actions"])
        or provenance.get("r6_initial_state_sensitivity_half_difference") != R6_HALF
        or provenance.get("r7_failure_provenance_preserved") is not True
        or provenance.get("r9_r10_failure_provenance_preserved") is not True
        or provenance.get("thresholds_relaxed") is not False
    ):
        raise ValueError("R12 身份、R11 基线或严格门不匹配")
    receipt, preview = load(paths["receipt"]), load(paths["preview"])
    if (
        receipt.get("status") != "pass" or receipt.get("non_clobbering") is not True
        or receipt.get("cell_id") != CELL or Path(receipt.get("destination", "")).resolve() != run
        or receipt.get("manifest_sha256") != sha256(paths["manifest"])
        or receipt.get("preview_sha256") != sha256(paths["preview"])
        or preview.get("status") != "pass" or preview.get("remote_checksum_status") != "pass"
        or preview.get("destination_exists") is not False
        or Path(preview.get("local_destination", "")).resolve() != run
    ):
        raise ValueError("R12 回传身份或非覆盖门失败")
    parent_hashes = verify_checksums(run)
    child_hashes = {mode: verify_checksums(run / f"start_{mode}") for mode in MODES}
    validation, manifest = load(paths["validation"]), load(paths["manifest"])
    if (
        validation.get("status") != "fail" or validation.get("cell_id") != CELL
        or validation.get("checks", {}).get("terminal_acceptance") is not False
        or any(passed is not True for name, passed in validation.get("checks", {}).items() if name != "terminal_acceptance")
        or not validation.get("failures") or manifest.get("status") != "failed" or manifest.get("accepted") is not False
    ):
        raise ValueError("R12 validator 或父终态不匹配")
    diagnostics = {mode: child(run, mode) for mode in MODES}
    validation_summary = fetch / "validation" / "summary.json"
    write_json(validation_summary, {
        "schema_version": 1, "status": "fail", "cell_count": 1, "counts": {"pass": 0, "fail": 1},
        "unmaterialized_cells": 4,
        "rows": [{"cell_id": CELL, "validator_status": "fail", "exit_code": 1,
                  "output": str(paths["validation"]), "sha256": sha256(paths["validation"])}],
    })
    handoff_audit = fetch / "handoff_audit.json"
    write_json(handoff_audit, {
        "schema_version": 1, "status": "pass_failure_only", "cell_id": CELL,
        "remote_checksums": "parent_and_two_children_pass", "local_checksums": "pass",
        "non_clobbering_fetch": True,
        "checksum_entries": {"parent": len(parent_hashes), "children": {k: len(v) for k, v in child_hashes.items()}},
        "validator": {"status": "fail", "sha256": sha256(paths["validation"])},
        "accepted_only_eligible": False, "thresholds_relaxed": False,
    })
    failure_summary = fetch / "failure_handoff_summary.json"
    failure = {
        "schema_version": 1, "status": "failed_validation", "cell_id": CELL,
        "params": {"alpha": -0.05, "beta": 0.5, "L": 60}, "budget": 64,
        "artifact": relative(paths["validation"]), "manifest": relative(paths["manifest"]),
        "receipt": relative(paths["receipt"]), "failed_gates": {mode: sorted(FAILED_FLAG) for mode in MODES},
        "strict_numerical_diagnostics": diagnostics, "accepted_only_eligible": False,
        "unmaterialized_cells": 4,
        "validation_summary": {"artifact": relative(validation_summary), "sha256": sha256(validation_summary)},
        "handoff_audit": {"artifact": relative(handoff_audit), "sha256": sha256(handoff_audit)},
        "r11_accepted_provenance_required": True, "r6_half_difference": R6_HALF,
        "r7_r9_r10_provenance_preserved": True, "thresholds_relaxed": False,
    }
    if forbidden(failure):
        raise ValueError("R12 failure handoff 含 value/error")
    write_json(failure_summary, failure)
    print(json.dumps({"status": "fail", "cell": CELL, "unmaterialized": 4}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
