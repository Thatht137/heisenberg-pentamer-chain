#!/usr/bin/env python3
"""接入 R17 三个严格通过的 Stage A 终态。"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from ingest_negative_phase_r6 import load, relative, sha256, write_json
from ingest_negative_phase_r7_failure import canonical_sha256


ROOT = Path(__file__).resolve().parents[2]
RUN_SPEC_SHA256 = "bfa8fe99ab277533e8c94ad90009c4995bbc66e279f77db8ff5885097df7ebc7"
CELLS = {
    40: ("nega-r17-a0025-b0500-L040", "act-4503b7acb169c6a5092f", False),
    60: ("nega-r17-a0025-b0500-L060", "act-3d1ab066156655e22ec8", False),
    80: ("nega-r17-a0025-b0500-L080", None, True),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-dir", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--phase-dir", type=Path, required=True)
    return parser.parse_args()


def key(params: dict[str, Any]) -> tuple[float, float, int]:
    return float(params["alpha"]), float(params["beta"]), int(params["L"])


def main() -> int:
    args = parse_args()
    fetch = args.fetch_dir.resolve()
    spec_path = args.run_spec.resolve()
    phase = args.phase_dir.resolve()
    observations_path = phase / "observations.json"
    actions_path = phase / "action_index.json"
    calibration_before = phase / "accepted_calibration_through_r16.json"
    r16_summary_path = phase / "r16_practical_ingestion_summary.json"
    validation_summary_path = fetch / "validation" / "summary.json"
    for path in (spec_path, observations_path, actions_path, calibration_before,
                 r16_summary_path, validation_summary_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    spec = load(spec_path)
    validation_summary = load(validation_summary_path)
    r16_summary = load(r16_summary_path)
    provenance = spec.get("provenance", {})
    if (
        sha256(spec_path) != RUN_SPEC_SHA256
        or provenance.get("r16_practical_summary_sha256") != sha256(r16_summary_path)
        or provenance.get("accepted_calibration_through_r16_sha256") != sha256(calibration_before)
        or provenance.get("observations_sha256") != sha256(observations_path)
        or provenance.get("action_index_sha256") != sha256(actions_path)
        or provenance.get("r16_boundary_eligible") is not False
        or provenance.get("r16_strict_failure_preserved") is not True
        or provenance.get("boundary_acceptance_thresholds_relaxed") is not False
        or validation_summary.get("counts") != {"pass": 3, "fail": 0}
        or r16_summary.get("counts") != {
            "controller_success_total": 14, "controller_failed_total": 0,
            "controller_pending_total": 2, "calibration_accepted_total": 7,
        }
    ):
        raise ValueError("R17 输入、validator 或 R16 accepted-only 基线不匹配")

    observations = load(observations_path)
    actions = load(actions_path)
    calibration = load(calibration_before)
    indexed = {key(row["params"]): row for row in observations.get("records", [])}
    action_index = {row["action_id"]: row for row in actions.get("actions", [])}
    untouched = {item_key: canonical_sha256(row) for item_key, row in indexed.items()
                 if item_key not in {(-0.025, 0.5, 40), (-0.025, 0.5, 60)}}
    new_records = []

    for length, (cell_id, action_id, calibration_only) in CELLS.items():
        manifest_path = fetch / cell_id / "manifest.json"
        validation_path = fetch / "validation" / f"{cell_id}.json"
        receipt_path = fetch / "receipts" / f"{cell_id}.json"
        for path in (manifest_path, validation_path, receipt_path):
            if not path.is_file():
                raise FileNotFoundError(path)
        validation = load(validation_path)
        manifest = load(manifest_path)
        receipt = load(receipt_path)
        if (
            validation.get("status") != "pass" or validation.get("cell_id") != cell_id
            or not all(validation.get("checks", {}).values())
            or receipt.get("status") != "pass" or receipt.get("cell_id") != cell_id
            or manifest.get("cell_id") != cell_id or manifest.get("status") != "success"
            or manifest.get("accepted") is not True
            or key(manifest.get("params", {})) != (-0.025, 0.5, length)
            or manifest.get("settings", {}).get("budget") != 64
        ):
            raise ValueError(f"{cell_id} 未通过 validator 或回传校验")
        observable = manifest["observables"]["dominant_structure_factor_ratio"]
        row = {
            "params": {"alpha": -0.025, "beta": 0.5, "L": length},
            "status": "success", "value": observable["value"], "error": observable["error"],
            "budget": 64, "artifact": relative(manifest_path), "accepted_only": True,
            "controller_action_id": action_id, "calibration_only": calibration_only,
            "boundary_eligible": True,
            "diagnostics": {
                "q_peak_over_pi": manifest["observables"]["structure_factor_peak_q_over_pi"],
                "strict_numerical_gates": validation.get("checks", {}),
            },
            "validation": {"status": "pass", "artifact": relative(validation_path),
                           "sha256": sha256(validation_path)},
            "checksum_receipt": {"artifact": relative(receipt_path), "sha256": sha256(receipt_path)},
            "provenance": manifest["provenance"],
            "r17_provenance": {"run_spec": relative(spec_path), "run_spec_sha256": sha256(spec_path),
                               "r16_strict_failure_preserved": True,
                               "r16_boundary_ineligible_preserved": True},
        }
        if calibration_only:
            new_records.append(row)
            continue
        target_key = (-0.025, 0.5, length)
        pending = indexed.get(target_key)
        action = action_index.get(action_id)
        if not pending or pending.get("status") != "pending":
            raise ValueError(f"L={length} controller 来源不是 pending")
        if not action or action.get("observation_status") != "pending" or action.get("accepted") is not False:
            raise ValueError(f"L={length} action 来源不是 pending")
        row["r17_provenance"]["previous_pending_observation"] = copy.deepcopy(pending)
        indexed[target_key] = row
        action.update({"observation_status": "success", "accepted": True,
                       "artifact": row["artifact"], "r17_success_handoff": True})

    calibration_index = {key(row["params"]): row for row in calibration.get("records", [])}
    l80 = new_records[0]
    if key(l80["params"]) in calibration_index:
        raise ValueError("R17 L80 calibration 已存在")
    calibration_index[key(l80["params"])] = l80
    records = sorted(indexed.values(), key=lambda row: key(row["params"]))
    counts = {name: sum(row.get("status") == name for row in records)
              for name in ("success", "failed", "pending")}
    if counts != {"success": 16, "failed": 0, "pending": 0}:
        raise ValueError(f"R17 controller 计数异常: {counts}")
    calibration_records = sorted(calibration_index.values(), key=lambda row: key(row["params"]))
    if len(calibration_records) != 8:
        raise ValueError("R17 calibration 总数不是8")

    pre_obs, pre_actions = sha256(observations_path), sha256(actions_path)
    calibration_out = phase / "accepted_calibration_through_r17.json"
    write_json(observations_path, {"schema_version": 1, "records": records})
    write_json(actions_path, actions)
    write_json(calibration_out, {
        "schema_version": 1,
        "purpose": "Stage A beta=0.5 的 L80 accepted calibration；R16为boundary-ineligible实用点",
        "sources": calibration.get("sources", []) + [
            {"artifact": relative(calibration_before), "sha256": sha256(calibration_before)},
            {"artifact": relative(validation_summary_path), "sha256": sha256(validation_summary_path)},
        ],
        "records": calibration_records,
    })
    post_index = {key(row["params"]): row for row in load(observations_path)["records"]}
    invariants = {
        "non_target_controller_unchanged": all(canonical_sha256(post_index[item_key]) == digest
                                                for item_key, digest in untouched.items()),
        "r16_calibration_preserved_boundary_ineligible": any(
            key(row["params"]) == (-0.05, 0.5, 80) and row.get("boundary_eligible") is False
            for row in load(calibration_out)["records"]
        ),
        "thresholds_relaxed_for_boundary": False,
        "crossing_assigned": False,
        "phase_label_assigned": False,
    }
    if not all(value is True for name, value in invariants.items()
               if name not in {"thresholds_relaxed_for_boundary", "crossing_assigned", "phase_label_assigned"}):
        raise ValueError(f"R17 provenance 不变量失败: {invariants}")

    audit_path = phase / "r17_success_ingestion_audit.json"
    write_json(audit_path, {
        "schema_version": 1, "status": "pass", "controller_counts": counts,
        "calibration_accepted_total": 8, "pre_observations_sha256": pre_obs,
        "pre_action_index_sha256": pre_actions, "post_observations_sha256": sha256(observations_path),
        "post_action_index_sha256": sha256(actions_path), "invariants": invariants,
    })
    summary_path = phase / "r17_success_ingestion_summary.json"
    summary = {
        "schema_version": 1, "status": "accepted_stage_a_complete",
        "cells": [item[0] for item in CELLS.values()],
        "counts": {"controller_success_total": 16, "controller_failed_total": 0,
                   "controller_pending_total": 0, "calibration_accepted_total": 8},
        "accepted_calibration": {"artifact": relative(calibration_out), "sha256": sha256(calibration_out)},
        "ingestion_audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
        "observations": {"artifact": relative(observations_path), "sha256": sha256(observations_path)},
        "action_index": {"artifact": relative(actions_path), "sha256": sha256(actions_path)},
        "controller": {"status": "READY_FOR_STAGE_A_ANALYSIS", "crossing": "not_assigned",
                       "phase_label": "not_assigned"},
        "boundary_thresholds_relaxed": False,
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
