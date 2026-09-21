#!/usr/bin/env python3
"""把 R9 部分终态接入 accepted-only 相图状态。"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from ingest_negative_phase_r6 import load, relative, sha256, write_json
from ingest_negative_phase_r7_failure import canonical_sha256


ROOT = Path(__file__).resolve().parents[2]
PASS_CELL = "nega-r9-a0100-b0500-L080"
FAIL_CELL = "nega-r9-a0050-b0500-L040"
PASS_KEY = (-0.1, 0.5, 80)
FAIL_KEY = (-0.05, 0.5, 40)
ACTION = "act-fffdf93a9cae183cb1c1"
R6_KEY = (-0.1, 0.5, 40)
R8_KEY = (-0.1, 0.5, 60)
R6_HALF = 0.011877542575884303


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-dir", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--phase-dir", type=Path, required=True)
    return parser.parse_args()


def key(params: dict[str, Any]) -> tuple[float, float, int]:
    return float(params["alpha"]), float(params["beta"]), int(params["L"])


def has_forbidden_measurement_keys(value: Any) -> bool:
    if isinstance(value, dict):
        return any(name in {"value", "error"} or has_forbidden_measurement_keys(item)
                   for name, item in value.items())
    if isinstance(value, list):
        return any(has_forbidden_measurement_keys(item) for item in value)
    return False


def main() -> int:
    args = parse_args()
    fetch, spec_path, phase = args.fetch_dir.resolve(), args.run_spec.resolve(), args.phase_dir.resolve()
    paths = {
        "handoff": fetch / "partial_handoff_summary.json",
        "handoff_audit": fetch / "handoff_audit.json",
        "validation_summary": fetch / "validation" / "summary.json",
        "observations": phase / "observations.json",
        "actions": phase / "action_index.json",
        "r8_summary": phase / "r8_ingestion_summary.json",
        "calibration_r5": phase / "accepted_calibration_through_r5.json",
    }
    for path in (spec_path, *paths.values()):
        if not path.is_file():
            raise FileNotFoundError(path)

    spec, handoff = load(spec_path), load(paths["handoff"])
    audit, validation_summary = load(paths["handoff_audit"]), load(paths["validation_summary"])
    r8_summary = load(paths["r8_summary"])
    provenance = spec.get("provenance", {})
    if (
        sha256(spec_path) != "7290e48b615d2d27ac20cbf36c1939bf9d488f97a374b5bfd94729c81742bf3b"
        or provenance.get("r8_ingestion_summary_sha256") != sha256(paths["r8_summary"])
        or provenance.get("observations_sha256") != sha256(paths["observations"])
        or provenance.get("r6_initial_state_sensitivity_half_difference") != R6_HALF
        or provenance.get("thresholds_relaxed") is not False
        or handoff.get("status") != "partial_failure"
        or handoff.get("accepted_calibration", {}).get("cell_id") != PASS_CELL
        or handoff.get("failed_controller", {}).get("cell_id") != FAIL_CELL
        or handoff.get("failed_controller", {}).get("accepted_only_eligible") is not False
        or handoff.get("validation_summary", {}).get("sha256") != sha256(paths["validation_summary"])
        or handoff.get("handoff_audit", {}).get("sha256") != sha256(paths["handoff_audit"])
        or validation_summary.get("counts") != {"pass": 1, "fail": 1}
        or audit.get("status") != "pass_partial_terminal"
        or audit.get("thresholds_relaxed") is not False
    ):
        raise ValueError("R9 handoff、R8 基线或严格门不匹配")
    if has_forbidden_measurement_keys(handoff["failed_controller"]):
        raise ValueError("R9 failed handoff 含 value/error")

    observations = load(paths["observations"])
    actions = load(paths["actions"])
    indexed = {key(row["params"]): row for row in observations.get("records", [])}
    r6_before, r8_before = copy.deepcopy(indexed[R6_KEY]), copy.deepcopy(indexed[R8_KEY])
    pending = indexed.get(FAIL_KEY)
    if (
        r8_summary.get("counts", {}).get("controller_success_total") != 12
        or r8_summary.get("counts", {}).get("controller_failed_total") != 0
        or r8_summary.get("counts", {}).get("controller_pending_total") != 4
        or r8_summary.get("counts", {}).get("calibration_accepted_total") != 5
        or r6_before.get("error") != R6_HALF
        or r8_before.get("r7_failure_provenance", {}).get("preserved") is not True
        or not pending or pending.get("status") != "pending"
    ):
        raise ValueError("R8 observations 基线不匹配")
    r6_hash, r8_hash = canonical_sha256(r6_before), canonical_sha256(r8_before)

    fail_validation = fetch / "validation" / f"{FAIL_CELL}.json"
    fail_manifest = fetch / FAIL_CELL / "manifest.json"
    fail_receipt = fetch / "receipts" / f"{FAIL_CELL}.json"
    failure = {
        "params": {"alpha": -0.05, "beta": 0.5, "L": 40},
        "status": "failed", "budget": 32, "accepted_only": False,
        "artifact": relative(fail_validation), "controller_action_id": ACTION,
        "failure_evidence": {
            "validator_status": "fail", "validator_artifact": relative(fail_validation),
            "validator_sha256": sha256(fail_validation),
            "manifest_artifact": relative(fail_manifest), "manifest_sha256": sha256(fail_manifest),
            "receipt_artifact": relative(fail_receipt), "receipt_sha256": sha256(fail_receipt),
            "failed_gates": handoff["failed_controller"]["failed_gates"],
            "strict_numerical_diagnostics": handoff["failed_controller"]["strict_numerical_diagnostics"],
            "thresholds": {"variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9,
                           "sector_tolerance": 1e-8, "spin_gap_min": -1e-8},
            "thresholds_relaxed": False,
        },
        "r9_provenance": {
            "previous_pending_observation": pending,
            "run_spec": {"artifact": relative(spec_path), "sha256": sha256(spec_path)},
            "partial_handoff": {"artifact": relative(paths["handoff"]), "sha256": sha256(paths["handoff"])},
            "r7_failure_provenance_preserved": True,
            "r6_half_difference_preserved": R6_HALF,
        },
    }
    if has_forbidden_measurement_keys(failure):
        raise ValueError("R9 failed observation 含 value/error")
    indexed[FAIL_KEY] = failure
    records = sorted(indexed.values(), key=lambda row: (row["params"]["beta"], row["params"]["alpha"], row["params"]["L"]))
    counts = {name: sum(row.get("status") == name for row in records) for name in ("success", "failed", "pending")}
    if counts != {"success": 12, "failed": 1, "pending": 3}:
        raise ValueError(f"R9 接入计数异常: {counts}")

    target = [row for row in actions.get("actions", []) if row.get("action_id") == ACTION]
    if len(target) != 1 or target[0].get("observation_status") != "pending":
        raise ValueError("R9 action 不是唯一 pending")
    target[0].update({
        "observation_status": "failed", "accepted": False, "artifact": failure["artifact"],
        "r9_failure_handoff": True, "failure_evidence_sha256": canonical_sha256(failure["failure_evidence"]),
        "retry_recommendation": {"next_budget": 64, "thresholds_relaxed": False},
    })

    calibration = load(paths["calibration_r5"])
    if len(calibration.get("records", [])) != 5:
        raise ValueError("R5 calibration 数量不是 5")
    pass_manifest = fetch / PASS_CELL / "manifest.json"
    pass_validation = fetch / "validation" / f"{PASS_CELL}.json"
    pass_receipt = fetch / "receipts" / f"{PASS_CELL}.json"
    manifest = load(pass_manifest)
    observable = manifest["observables"]["dominant_structure_factor_ratio"]
    new_calibration = {
        "params": {"alpha": -0.1, "beta": 0.5, "L": 80},
        "status": "success", "value": observable["value"], "error": observable["error"],
        "budget": 64, "artifact": relative(pass_manifest), "accepted_only": True,
        "controller_action_id": None, "calibration_only": True,
        "diagnostics": {
            "q_peak_over_pi": manifest["observables"]["structure_factor_peak_q_over_pi"],
            "strict_numerical_gates": handoff["accepted_calibration"]["strict_numerical_gates"],
        },
        "validation": {"status": "pass", "artifact": relative(pass_validation), "sha256": sha256(pass_validation)},
        "checksum_receipt": {"artifact": relative(pass_receipt), "sha256": sha256(pass_receipt)},
        "provenance": manifest["provenance"],
    }
    calibration_index = {key(row["params"]): row for row in calibration["records"]}
    if PASS_KEY in calibration_index:
        raise ValueError("R9 calibration 已存在，拒绝覆盖")
    calibration_index[PASS_KEY] = new_calibration
    calibration_out = phase / "accepted_calibration_through_r9.json"
    calibration_doc = {
        "schema_version": 1,
        "purpose": "R1、R3、R5、R9 的 L80 calibration-only accepted evidence；不进入 controller observations",
        "sources": calibration.get("sources", []) + [
            {"artifact": relative(paths["calibration_r5"]), "sha256": sha256(paths["calibration_r5"])},
            {"artifact": relative(paths["handoff"]), "sha256": sha256(paths["handoff"])},
        ],
        "records": sorted(calibration_index.values(), key=lambda row: key(row["params"])),
    }
    if len(calibration_doc["records"]) != 6:
        raise ValueError("R9 calibration 总数不是 6")

    pre_obs, pre_actions = sha256(paths["observations"]), sha256(paths["actions"])
    write_json(paths["observations"], {"schema_version": 1, "records": records})
    write_json(paths["actions"], actions)
    write_json(calibration_out, calibration_doc)
    post_index = {key(row["params"]): row for row in load(paths["observations"])["records"]}
    invariants = {
        "r6_observation_unchanged": canonical_sha256(post_index[R6_KEY]) == r6_hash,
        "r6_half_difference_preserved": post_index[R6_KEY].get("error") == R6_HALF,
        "r8_observation_unchanged": canonical_sha256(post_index[R8_KEY]) == r8_hash,
        "r7_failure_provenance_preserved": post_index[R8_KEY].get("r7_failure_provenance", {}).get("preserved") is True,
        "failed_observation_has_no_value_or_error": not has_forbidden_measurement_keys(post_index[FAIL_KEY]),
    }
    if not all(invariants.values()):
        raise ValueError(f"R9 provenance 不变量失败: {invariants}")

    audit_path = phase / "r9_partial_ingestion_audit.json"
    write_json(audit_path, {
        "schema_version": 1, "status": "pass_partial_failure", "controller_counts": counts,
        "calibration_accepted_total": 6, "pre_observations_sha256": pre_obs,
        "pre_action_index_sha256": pre_actions, "post_observations_sha256": sha256(paths["observations"]),
        "post_action_index_sha256": sha256(paths["actions"]), "invariants": invariants,
        "thresholds_relaxed": False, "crossing_assigned": False, "phase_label_assigned": False,
    })
    summary_path = phase / "r9_partial_ingestion_summary.json"
    summary = {
        "schema_version": 1, "status": "partial_failure_ingested",
        "accepted_calibration_cell": PASS_CELL, "failed_controller_cell": FAIL_CELL,
        "counts": {"controller_success_total": 12, "controller_failed_total": 1,
                   "controller_pending_total": 3, "calibration_accepted_total": 6},
        "failed_observation_contains_value_or_error": False,
        "accepted_calibration": {"artifact": relative(calibration_out), "sha256": sha256(calibration_out)},
        "handoff": {"artifact": relative(paths["handoff"]), "sha256": sha256(paths["handoff"])},
        "ingestion_audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
        "observations": {"artifact": relative(paths["observations"]), "sha256": sha256(paths["observations"])},
        "action_index": {"artifact": relative(paths["actions"]), "sha256": sha256(paths["actions"])},
        "controller": {"status": "NOT_REEVALUATED", "crossing": "not_assigned", "phase_label": "not_assigned"},
        "thresholds_relaxed": False,
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
