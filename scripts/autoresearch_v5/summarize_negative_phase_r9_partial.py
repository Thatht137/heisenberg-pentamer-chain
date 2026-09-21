#!/usr/bin/env python3
"""汇总 R9 部分终态并锁定回传证据。"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from ingest_negative_phase_r6 import load, relative, sha256, verify_checksums, write_json


ROOT = Path(__file__).resolve().parents[2]
PASS_CELL = "nega-r9-a0100-b0500-L080"
FAIL_CELL = "nega-r9-a0050-b0500-L040"
PASS_KEY = (-0.1, 0.5, 80)
FAIL_KEY = (-0.05, 0.5, 40)
ACTION = "act-fffdf93a9cae183cb1c1"
MODES = ("center", "ferro_j2")
VARIANCE_FLAGS = {"variance_sz0_per_site_le_1e-8", "variance_sz1_per_site_le_1e-8"}


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


def check_transfer(fetch: Path, cell_id: str) -> tuple[Path, dict[str, int]]:
    run = fetch / cell_id
    manifest = run / "manifest.json"
    validation = fetch / "validation" / f"{cell_id}.json"
    receipt = fetch / "receipts" / f"{cell_id}.json"
    preview = fetch / "previews" / f"{cell_id}.json"
    for path in (manifest, validation, receipt, preview):
        if not path.is_file():
            raise FileNotFoundError(path)
    rec, pre = load(receipt), load(preview)
    if (
        rec.get("status") != "pass" or rec.get("non_clobbering") is not True
        or rec.get("cell_id") != cell_id or Path(rec.get("destination", "")).resolve() != run
        or rec.get("manifest_sha256") != sha256(manifest)
        or rec.get("preview_sha256") != sha256(preview)
        or pre.get("status") != "pass" or pre.get("cell_id") != cell_id
        or pre.get("destination_exists") is not False
        or pre.get("remote_checksum_status") != "pass"
        or Path(pre.get("local_destination", "")).resolve() != run
    ):
        raise ValueError(f"{cell_id} 回传身份或非覆盖门失败")
    parent = verify_checksums(run)
    children = {mode: verify_checksums(run / f"start_{mode}") for mode in MODES}
    return run, {"parent": len(parent), **{mode: len(rows) for mode, rows in children.items()}}


def check_child(run: Path, mode: str, expected: tuple[float, float, int], accepted: bool) -> dict[str, float]:
    child = load(run / f"start_{mode}" / "manifest.json")
    checks = child.get("acceptance", {})
    diagnostics = child.get("diagnostics", {})
    observables = child.get("observables", {})
    false_flags = {name for name, passed in checks.items() if passed is False}
    values = {
        "variance_per_site_sz0": finite(diagnostics.get("variance_per_site_sz0"), f"{mode}.var0"),
        "variance_per_site_sz1": finite(diagnostics.get("variance_per_site_sz1"), f"{mode}.var1"),
        "final_truncation_error_sz0": finite(diagnostics.get("final_truncation_error_sz0"), f"{mode}.trunc0"),
        "final_truncation_error_sz1": finite(diagnostics.get("final_truncation_error_sz1"), f"{mode}.trunc1"),
        "total_sz0": finite(diagnostics.get("total_sz0"), f"{mode}.sz0"),
        "total_sz1": finite(diagnostics.get("total_sz1"), f"{mode}.sz1"),
        "spin_gap": finite(observables.get("spin_gap"), f"{mode}.gap"),
    }
    common_ok = (
        child.get("status") == "success" and key(child.get("params", {})) == expected
        and child.get("settings", {}).get("q_count") == 401
        and child.get("settings", {}).get("cutoff") == 1e-11
        and max(values["final_truncation_error_sz0"], values["final_truncation_error_sz1"]) <= 1e-9
        and abs(values["total_sz0"]) <= 1e-8 and abs(values["total_sz1"] - 1.0) <= 1e-8
        and values["spin_gap"] >= -1e-8
    )
    if accepted:
        if (
            not common_ok or child.get("accepted") is not True or false_flags
            or max(values["variance_per_site_sz0"], values["variance_per_site_sz1"]) > 1e-8
        ):
            raise ValueError(f"{run.name}/{mode} 未严格通过")
    elif (
        not common_ok or child.get("accepted") is not False or false_flags != VARIANCE_FLAGS
        or min(values["variance_per_site_sz0"], values["variance_per_site_sz1"]) <= 1e-8
    ):
        raise ValueError(f"{run.name}/{mode} 不是仅方差失败")
    return values


def main() -> int:
    args = parse_args()
    fetch, spec_path, phase = args.fetch_dir.resolve(), args.run_spec.resolve(), args.phase_dir.resolve()
    r8_summary = phase / "r8_ingestion_summary.json"
    observations = phase / "observations.json"
    for path in (spec_path, r8_summary, observations):
        if not path.is_file():
            raise FileNotFoundError(path)
    spec = load(spec_path)
    cells = {row.get("cell_id"): row for row in spec.get("cells", [])}
    if len(cells) != 7:
        raise ValueError("R9 run spec 不是 7 个唯一 cell")
    passed, failed = cells.get(PASS_CELL), cells.get(FAIL_CELL)
    provenance = spec.get("provenance", {})
    if (
        not passed or key(passed.get("params", {})) != PASS_KEY or passed.get("budget") != 64
        or passed.get("calibration_only") is not True or passed.get("controller_action_id") is not None
        or not failed or key(failed.get("params", {})) != FAIL_KEY or failed.get("budget") != 32
        or failed.get("calibration_only") is not False or failed.get("controller_action_id") != ACTION
        or provenance.get("r8_ingestion_summary_sha256") != sha256(r8_summary)
        or provenance.get("observations_sha256") != sha256(observations)
        or provenance.get("r7_r8_evidence_preserved") is not True
        or provenance.get("r6_initial_state_sensitivity_half_difference") != 0.011877542575884303
        or provenance.get("thresholds_relaxed") is not False
    ):
        raise ValueError("R9 身份、R8 基线或门槛不匹配")

    pass_run, pass_hashes = check_transfer(fetch, PASS_CELL)
    fail_run, fail_hashes = check_transfer(fetch, FAIL_CELL)
    pass_validation = load(fetch / "validation" / f"{PASS_CELL}.json")
    fail_validation = load(fetch / "validation" / f"{FAIL_CELL}.json")
    if (
        pass_validation.get("status") != "pass" or not all(pass_validation.get("checks", {}).values())
        or pass_validation.get("failures")
        or fail_validation.get("status") != "fail"
        or fail_validation.get("checks", {}).get("terminal_acceptance") is not False
        or any(value is not True for name, value in fail_validation.get("checks", {}).items() if name != "terminal_acceptance")
        or not fail_validation.get("failures")
    ):
        raise ValueError("R9 validator 终态不匹配")
    pass_manifest, fail_manifest = load(pass_run / "manifest.json"), load(fail_run / "manifest.json")
    if pass_manifest.get("accepted") is not True or pass_manifest.get("status") != "success":
        raise ValueError("R9 L80 父 manifest 未通过")
    if fail_manifest.get("accepted") is not False or fail_manifest.get("status") != "failed":
        raise ValueError("R9 L40 父 manifest 不是严格失败")
    pass_diag = {mode: check_child(pass_run, mode, PASS_KEY, True) for mode in MODES}
    fail_diag = {mode: check_child(fail_run, mode, FAIL_KEY, False) for mode in MODES}

    validation_summary = fetch / "validation" / "summary.json"
    rows = []
    for cell_id, status, code in ((PASS_CELL, "pass", 0), (FAIL_CELL, "fail", 1)):
        path = fetch / "validation" / f"{cell_id}.json"
        rows.append({"cell_id": cell_id, "validator_status": status, "exit_code": code,
                     "output": str(path), "sha256": sha256(path)})
    write_json(validation_summary, {"schema_version": 1, "status": "partial_failure", "cell_count": 2,
                                    "counts": {"pass": 1, "fail": 1}, "rows": rows})
    handoff_audit = fetch / "handoff_audit.json"
    write_json(handoff_audit, {
        "schema_version": 1, "status": "pass_partial_terminal", "run_spec_sha256": sha256(spec_path),
        "remote_checksums": "parent_and_two_children_pass_for_both_cells", "local_checksums": "pass",
        "non_clobbering_fetch": True, "checksum_entries": {PASS_CELL: pass_hashes, FAIL_CELL: fail_hashes},
        "validator_counts": {"pass": 1, "fail": 1}, "accepted_calibration_cell": PASS_CELL,
        "failed_controller_cell": FAIL_CELL, "thresholds_relaxed": False,
    })
    handoff_summary = fetch / "partial_handoff_summary.json"
    write_json(handoff_summary, {
        "schema_version": 1, "status": "partial_failure", "materialized_cells": 2,
        "accepted_calibration": {
            "cell_id": PASS_CELL, "params": pass_manifest["params"], "budget": 64,
            "artifact": relative(pass_run / "manifest.json"),
            "validation": relative(fetch / "validation" / f"{PASS_CELL}.json"),
            "receipt": relative(fetch / "receipts" / f"{PASS_CELL}.json"),
            "strict_numerical_gates": pass_diag,
        },
        "failed_controller": {
            "cell_id": FAIL_CELL, "params": fail_manifest["params"], "budget": 32,
            "artifact": relative(fail_run / "manifest.json"),
            "validation": relative(fetch / "validation" / f"{FAIL_CELL}.json"),
            "receipt": relative(fetch / "receipts" / f"{FAIL_CELL}.json"),
            "failed_gates": sorted(VARIANCE_FLAGS), "strict_numerical_diagnostics": fail_diag,
            "accepted_only_eligible": False,
        },
        "validation_summary": {"artifact": relative(validation_summary), "sha256": sha256(validation_summary)},
        "handoff_audit": {"artifact": relative(handoff_audit), "sha256": sha256(handoff_audit)},
        "r7_r8_evidence_preserved": True, "r6_half_difference": 0.011877542575884303,
        "thresholds_relaxed": False,
    })
    print(json.dumps({"validation_summary": str(validation_summary), "handoff": str(handoff_summary),
                      "pass": 1, "fail": 1}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
