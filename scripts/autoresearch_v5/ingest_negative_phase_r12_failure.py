#!/usr/bin/env python3
"""把 R12 首单元严格失败接入本地相图状态。"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from ingest_negative_phase_r6 import load, relative, sha256, write_json
from ingest_negative_phase_r7_failure import canonical_sha256


CELL = "nega-r12-a0050-b0500-L060"
KEY = (-0.05, 0.5, 60)
R11_KEY = (-0.05, 0.5, 40)
R6_KEY = (-0.1, 0.5, 40)
R8_KEY = (-0.1, 0.5, 60)
ACTION = "act-7016420e7cbf8fc354b7"
R6_HALF = 0.011877542575884303


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-dir", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--phase-dir", type=Path, required=True)
    return parser.parse_args()


def key(params: dict[str, Any]) -> tuple[float, float, int]:
    return float(params["alpha"]), float(params["beta"]), int(params["L"])


def forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return any(name in {"value", "error"} or forbidden(item) for name, item in value.items())
    if isinstance(value, list):
        return any(forbidden(item) for item in value)
    return False


def main() -> int:
    args = parse_args()
    fetch, spec_path, phase = args.fetch_dir.resolve(), args.run_spec.resolve(), args.phase_dir.resolve()
    paths = {
        "handoff": fetch / "failure_handoff_summary.json", "handoff_audit": fetch / "handoff_audit.json",
        "validation_summary": fetch / "validation" / "summary.json",
        "validation": fetch / "validation" / f"{CELL}.json", "manifest": fetch / CELL / "manifest.json",
        "receipt": fetch / "receipts" / f"{CELL}.json",
        "observations": phase / "observations.json", "actions": phase / "action_index.json",
        "r11_summary": phase / "r11_success_ingestion_summary.json",
        "r11_audit": phase / "r11_success_ingestion_audit.json",
        "calibration": phase / "accepted_calibration_through_r9.json",
    }
    for path in (spec_path, *paths.values()):
        if not path.is_file():
            raise FileNotFoundError(path)
    spec, handoff = load(spec_path), load(paths["handoff"])
    provenance = spec.get("provenance", {})
    if (
        handoff.get("status") != "failed_validation" or handoff.get("cell_id") != CELL
        or handoff.get("budget") != 64 or handoff.get("accepted_only_eligible") is not False
        or handoff.get("unmaterialized_cells") != 4 or forbidden(handoff)
        or handoff.get("validation_summary", {}).get("sha256") != sha256(paths["validation_summary"])
        or handoff.get("handoff_audit", {}).get("sha256") != sha256(paths["handoff_audit"])
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
        raise ValueError("R12 handoff、R11 基线或 provenance 不匹配")
    observations, actions = load(paths["observations"]), load(paths["actions"])
    indexed = {key(row["params"]): row for row in observations.get("records", [])}
    previous = copy.deepcopy(indexed.get(KEY))
    r11_before, r6_before, r8_before = copy.deepcopy(indexed[R11_KEY]), copy.deepcopy(indexed[R6_KEY]), copy.deepcopy(indexed[R8_KEY])
    if (
        not previous or previous.get("status") != "pending" or previous.get("budget") != 32
        or r11_before.get("status") != "success" or r11_before.get("budget") != 128
        or r11_before.get("r10_failure_provenance", {}).get("preserved") is not True
        or r6_before.get("error") != R6_HALF
        or r8_before.get("r7_failure_provenance", {}).get("preserved") is not True
    ):
        raise ValueError("R12 pending target 或历史 provenance 不匹配")
    r11_hash, r6_hash, r8_hash = map(canonical_sha256, (r11_before, r6_before, r8_before))
    failure = {
        "params": {"alpha": -0.05, "beta": 0.5, "L": 60}, "status": "failed", "budget": 64,
        "accepted_only": False, "artifact": relative(paths["validation"]), "controller_action_id": ACTION,
        "failure_evidence": {
            "validator_status": "fail", "validator_artifact": relative(paths["validation"]),
            "validator_sha256": sha256(paths["validation"]), "manifest_artifact": relative(paths["manifest"]),
            "manifest_sha256": sha256(paths["manifest"]), "receipt_artifact": relative(paths["receipt"]),
            "receipt_sha256": sha256(paths["receipt"]), "failed_gates": handoff["failed_gates"],
            "strict_numerical_diagnostics": handoff["strict_numerical_diagnostics"],
            "thresholds": {"variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9,
                           "sector_tolerance": 1e-8, "spin_gap_min": -1e-8},
            "thresholds_relaxed": False,
        },
        "r12_provenance": {
            "previous_pending_observation": previous, "original_action_budget": 32,
            "run_spec": {"artifact": relative(spec_path), "sha256": sha256(spec_path)},
            "failure_handoff": {"artifact": relative(paths["handoff"]), "sha256": sha256(paths["handoff"])},
            "r11_accepted_observation_sha256": r11_hash, "r11_accepted_provenance_preserved": True,
            "r9_r10_failure_provenance_preserved": True, "r6_half_difference_preserved": R6_HALF,
            "r7_failure_provenance_preserved": True,
        },
    }
    if forbidden(failure):
        raise ValueError("R12 failed observation 含 value/error")
    indexed[KEY] = failure
    records = sorted(indexed.values(), key=lambda row: (row["params"]["beta"], row["params"]["alpha"], row["params"]["L"]))
    counts = {name: sum(row.get("status") == name for row in records) for name in ("success", "failed", "pending")}
    if counts != {"success": 13, "failed": 1, "pending": 2}:
        raise ValueError(f"R12 接入计数异常: {counts}")
    target = [row for row in actions.get("actions", []) if row.get("action_id") == ACTION]
    if len(target) != 1 or target[0].get("observation_status") != "pending":
        raise ValueError("R12 action 不是唯一 pending")
    target[0].update({
        "observation_status": "failed", "accepted": False, "artifact": failure["artifact"],
        "r12_failure_handoff": True, "accepted_attempt_budget": 64, "original_action_budget": 32,
        "failure_evidence_sha256": canonical_sha256(failure["failure_evidence"]),
        "retry_recommendation": {"next_budget": 128, "thresholds_relaxed": False},
    })
    pre_obs, pre_actions, calibration_hash = sha256(paths["observations"]), sha256(paths["actions"]), sha256(paths["calibration"])
    write_json(paths["observations"], {"schema_version": 1, "records": records})
    write_json(paths["actions"], actions)
    post = {key(row["params"]): row for row in load(paths["observations"])["records"]}
    invariants = {
        "r11_accepted_observation_unchanged": canonical_sha256(post[R11_KEY]) == r11_hash,
        "r9_r10_failure_provenance_preserved": post[R11_KEY].get("r10_failure_provenance", {}).get("preserved") is True,
        "r6_observation_unchanged": canonical_sha256(post[R6_KEY]) == r6_hash,
        "r6_half_difference_preserved": post[R6_KEY].get("error") == R6_HALF,
        "r8_observation_unchanged": canonical_sha256(post[R8_KEY]) == r8_hash,
        "r7_failure_provenance_preserved": post[R8_KEY].get("r7_failure_provenance", {}).get("preserved") is True,
        "failed_observation_has_no_value_or_error": not forbidden(post[KEY]),
        "calibration_unchanged": sha256(paths["calibration"]) == calibration_hash,
    }
    if not all(invariants.values()):
        raise ValueError(f"R12 provenance 不变量失败: {invariants}")
    audit_path = phase / "r12_failure_ingestion_audit.json"
    write_json(audit_path, {
        "schema_version": 1, "status": "pass_failure_only", "controller_counts": counts,
        "calibration_accepted_total": 6, "unmaterialized_cells": 4,
        "pre_observations_sha256": pre_obs, "pre_action_index_sha256": pre_actions,
        "post_observations_sha256": sha256(paths["observations"]),
        "post_action_index_sha256": sha256(paths["actions"]), "invariants": invariants,
        "thresholds_relaxed": False, "crossing_assigned": False, "phase_label_assigned": False,
    })
    summary_path = phase / "r12_failure_ingestion_summary.json"
    summary = {
        "schema_version": 1, "status": "blocked_by_validation_failure", "cell_id": CELL,
        "failed_key": {"alpha": -0.05, "beta": 0.5, "L": 60},
        "counts": {"controller_success_total": 13, "controller_failed_total": 1,
                   "controller_pending_total": 2, "calibration_accepted_total": 6},
        "unmaterialized_cells": 4, "failed_observation_contains_value_or_error": False,
        "failure_handoff": {"artifact": relative(paths["handoff"]), "sha256": sha256(paths["handoff"])},
        "ingestion_audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
        "observations": {"artifact": relative(paths["observations"]), "sha256": sha256(paths["observations"])},
        "action_index": {"artifact": relative(paths["actions"]), "sha256": sha256(paths["actions"])},
        "accepted_calibration": {"artifact": relative(paths["calibration"]), "sha256": sha256(paths["calibration"])},
        "controller": {"status": "HUMAN_REQUIRED_RETRY_PREPARED", "crossing": "not_assigned", "phase_label": "not_assigned"},
        "thresholds_relaxed": False,
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
