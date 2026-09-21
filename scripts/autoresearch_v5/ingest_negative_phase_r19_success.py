#!/usr/bin/env python3
"""接入 R19 的 L60 控制点和 L80 校准点。"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from ingest_negative_phase_r6 import load, relative, sha256, write_json
from ingest_negative_phase_r7_failure import canonical_sha256


CELLS = {
    60: ("nega-r19-a0025-b0500-L060", "act-3d1ab066156655e22ec8", False),
    80: ("nega-r19-a0025-b0500-L080", None, True),
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
    fetch, spec_path, phase = args.fetch_dir.resolve(), args.run_spec.resolve(), args.phase_dir.resolve()
    contract_path = spec_path.parent / "launch-contract.json"
    paths = {
        "observations": phase / "observations.json",
        "actions": phase / "action_index.json",
        "r18_summary": phase / "r18_success_ingestion_summary.json",
        "r18_audit": phase / "r18_success_ingestion_audit.json",
        "calibration": phase / "accepted_calibration_through_r16.json",
        "validation_summary": fetch / "validation/summary.json",
    }
    for path in (spec_path, contract_path, *paths.values()):
        if not path.is_file():
            raise FileNotFoundError(path)
    spec, contract = load(spec_path), load(contract_path)
    provenance = spec.get("provenance", {})
    r18_summary, r18_audit = load(paths["r18_summary"]), load(paths["r18_audit"])
    validation_summary = load(paths["validation_summary"])
    if (
        spec.get("run_id") != "pentamer-negative-phase-stage-a-r19-remaining2-20260812"
        or contract.get("run_spec_sha256") != sha256(spec_path)
        or contract.get("cell_count") != 2 or contract.get("concurrency") != 1
        or contract.get("boundary_thresholds_relaxed") is not False
        or provenance.get("r18_success_summary_sha256") != sha256(paths["r18_summary"])
        or provenance.get("r18_success_audit_sha256") != sha256(paths["r18_audit"])
        or provenance.get("accepted_calibration_through_r16_sha256") != sha256(paths["calibration"])
        or provenance.get("observations_sha256") != sha256(paths["observations"])
        or provenance.get("action_index_sha256") != sha256(paths["actions"])
        or provenance.get("boundary_acceptance_thresholds_relaxed") is not False
        or r18_summary.get("counts") != {"controller_success_total": 15,
                                          "controller_failed_total": 0,
                                          "controller_pending_total": 1,
                                          "calibration_accepted_total": 7}
        or r18_audit.get("status") != "pass"
        or validation_summary.get("counts") != {"pass": 2, "fail": 0}
    ):
        raise ValueError("R19 run spec、R18 基线或 validator 汇总不匹配")

    observations, actions = load(paths["observations"]), load(paths["actions"])
    calibration = load(paths["calibration"])
    indexed = {key(row["params"]): row for row in observations.get("records", [])}
    calibration_index = {key(row["params"]): row for row in calibration.get("records", [])}
    target_key = (-0.025, 0.5, 60)
    previous = copy.deepcopy(indexed.get(target_key))
    if not previous or previous.get("status") != "pending" or previous.get("budget") != 32:
        raise ValueError("R19 L60 来源不是 pending")
    untouched = {item_key: canonical_sha256(row) for item_key, row in indexed.items()
                 if item_key != target_key}
    calibration_new = None

    for length, (cell_id, action_id, calibration_only) in CELLS.items():
        manifest_path = fetch / cell_id / "manifest.json"
        validation_path = fetch / "validation" / f"{cell_id}.json"
        receipt_path = fetch / "receipts" / f"{cell_id}.json"
        for path in (manifest_path, validation_path, receipt_path):
            if not path.is_file():
                raise FileNotFoundError(path)
        manifest, validation, receipt = load(manifest_path), load(validation_path), load(receipt_path)
        if (
            manifest.get("cell_id") != cell_id or manifest.get("status") != "success"
            or manifest.get("accepted") is not True
            or key(manifest.get("params", {})) != (-0.025, 0.5, length)
            or manifest.get("settings", {}).get("budget") != 64
            or validation.get("cell_id") != cell_id or validation.get("status") != "pass"
            or not all(validation.get("checks", {}).values())
            or receipt.get("cell_id") != cell_id or receipt.get("status") != "pass"
            or receipt.get("non_clobbering") is not True
        ):
            raise ValueError(f"{cell_id} 未通过严格终态门")
        observable = manifest["observables"]["dominant_structure_factor_ratio"]
        row = {
            "params": {"alpha": -0.025, "beta": 0.5, "L": length},
            "status": "success", "value": observable["value"], "error": observable["error"],
            "budget": 64, "artifact": relative(manifest_path), "accepted_only": True,
            "controller_action_id": action_id, "calibration_only": calibration_only,
            "boundary_eligible": True,
            "diagnostics": {
                "q_peak_over_pi": manifest["observables"]["structure_factor_peak_q_over_pi"]["value"],
                "strict_numerical_gates": validation["checks"],
            },
            "validation": {"status": "pass", "artifact": relative(validation_path),
                           "sha256": sha256(validation_path)},
            "checksum_receipt": {"artifact": relative(receipt_path), "sha256": sha256(receipt_path)},
            "provenance": manifest["provenance"],
            "r19_provenance": {"run_spec": relative(spec_path), "run_spec_sha256": sha256(spec_path),
                               "r18_failure_history_preserved": True,
                               "thresholds_relaxed": False},
        }
        if calibration_only:
            calibration_new = row
            continue
        row["r19_provenance"]["previous_pending_observation"] = previous
        indexed[target_key] = row
        target = [item for item in actions.get("actions", []) if item.get("action_id") == action_id]
        if len(target) != 1 or target[0].get("observation_status") != "pending":
            raise ValueError("R19 L60 action 不是唯一 pending")
        target[0].update({"observation_status": "success", "accepted": True,
                          "artifact": row["artifact"], "accepted_observation_budget": 64,
                          "r19_success_handoff": True})

    if calibration_new is None or key(calibration_new["params"]) in calibration_index:
        raise ValueError("R19 L80 calibration 缺失或重复")
    calibration_index[key(calibration_new["params"])] = calibration_new
    records = sorted(indexed.values(), key=lambda row: key(row["params"]))
    counts = {name: sum(row.get("status") == name for row in records)
              for name in ("success", "failed", "pending")}
    if counts != {"success": 16, "failed": 0, "pending": 0}:
        raise ValueError(f"R19 controller 计数异常: {counts}")
    calibration_records = sorted(calibration_index.values(), key=lambda row: key(row["params"]))
    if len(calibration_records) != 8:
        raise ValueError("R19 calibration 总数不是8")

    pre_obs, pre_actions = sha256(paths["observations"]), sha256(paths["actions"])
    calibration_out = phase / "accepted_calibration_through_r19.json"
    write_json(paths["observations"], {"schema_version": 1, "records": records})
    write_json(paths["actions"], actions)
    write_json(calibration_out, {
        "schema_version": 1,
        "purpose": "Stage A beta=0.5 的 L80 accepted calibration；R16为boundary-ineligible实用点",
        "sources": calibration.get("sources", []) + [
            {"artifact": relative(paths["calibration"]), "sha256": sha256(paths["calibration"])},
            {"artifact": relative(paths["validation_summary"]), "sha256": sha256(paths["validation_summary"])},
        ],
        "records": calibration_records,
    })
    post = {key(row["params"]): row for row in load(paths["observations"])["records"]}
    invariants = {
        "non_target_controller_unchanged": all(canonical_sha256(post[item_key]) == digest
                                                for item_key, digest in untouched.items()),
        "r16_boundary_ineligible_preserved": any(
            key(row["params"]) == (-0.05, 0.5, 80) and row.get("boundary_eligible") is False
            for row in load(calibration_out)["records"]
        ),
        "r18_failure_history_preserved": post[(-0.025, 0.5, 40)].get(
            "r17_failure_provenance", {}).get("preserved") is True,
    }
    if not all(invariants.values()):
        raise ValueError(f"R19 provenance 不变量失败: {invariants}")

    audit_path = phase / "r19_success_ingestion_audit.json"
    write_json(audit_path, {
        "schema_version": 1, "status": "pass", "controller_counts": counts,
        "calibration_accepted_total": 8, "pre_observations_sha256": pre_obs,
        "pre_action_index_sha256": pre_actions, "post_observations_sha256": sha256(paths["observations"]),
        "post_action_index_sha256": sha256(paths["actions"]), "invariants": invariants,
        "thresholds_relaxed": False, "crossing_assigned": False, "phase_label_assigned": False,
    })
    summary_path = phase / "r19_success_ingestion_summary.json"
    summary = {
        "schema_version": 1, "status": "accepted_stage_a_complete",
        "cells": [item[0] for item in CELLS.values()],
        "counts": {"controller_success_total": 16, "controller_failed_total": 0,
                   "controller_pending_total": 0, "calibration_accepted_total": 8},
        "accepted_calibration": {"artifact": relative(calibration_out), "sha256": sha256(calibration_out)},
        "ingestion_audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
        "observations": {"artifact": relative(paths["observations"]),
                         "sha256": sha256(paths["observations"])},
        "action_index": {"artifact": relative(paths["actions"]), "sha256": sha256(paths["actions"])},
        "controller": {"status": "READY_FOR_STAGE_A_ANALYSIS", "crossing": "not_assigned",
                       "phase_label": "not_assigned"},
        "boundary_thresholds_relaxed": False,
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
