#!/usr/bin/env python3
"""接入 R17 首单元严格失败并保留 R16 基线。"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from ingest_negative_phase_r6 import load, relative, sha256, write_json
from ingest_negative_phase_r7_failure import canonical_sha256


RUN_SPEC_SHA256 = "bfa8fe99ab277533e8c94ad90009c4995bbc66e279f77db8ff5885097df7ebc7"
CELL = "nega-r17-a0025-b0500-L040"
KEY = (-0.025, 0.5, 40)
UNTOUCHED_KEY = (-0.025, 0.5, 60)
ACTION = "act-4503b7acb169c6a5092f"


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
        "validation": fetch / "validation" / f"{CELL}.json",
        "receipt": fetch / "receipts" / f"{CELL}.json",
        "manifest": fetch / CELL / "manifest.json",
        "center": fetch / CELL / "start_center" / "manifest.json",
        "ferro": fetch / CELL / "start_ferro_j2" / "manifest.json",
        "observations": phase / "observations.json", "actions": phase / "action_index.json",
        "r16_summary": phase / "r16_practical_ingestion_summary.json",
        "r16_calibration": phase / "accepted_calibration_through_r16.json",
    }
    for path in (spec_path, *paths.values()):
        if not path.is_file():
            raise FileNotFoundError(path)
    spec, validation, receipt = load(spec_path), load(paths["validation"]), load(paths["receipt"])
    provenance = spec.get("provenance", {})
    center, ferro = load(paths["center"]), load(paths["ferro"])
    variances = [center["diagnostics"]["variance_per_site_sz1"],
                 ferro["diagnostics"]["variance_per_site_sz1"]]
    allowed_failures = {
        "父 manifest: 非 accepted success", "父 status: 非 accepted success",
        "父 manifest: children_accepted 未通过", "子 manifest center: 非 accepted success",
        "子 status center: 非 accepted success", "子 manifest center: variance/site sz1 超门",
        "子 manifest center: variance_sz1_per_site_le_1e-8 未通过",
        "子 manifest ferro_j2: 非 accepted success", "子 status ferro_j2: 非 accepted success",
        "子 manifest ferro_j2: variance/site sz1 超门",
        "子 manifest ferro_j2: variance_sz1_per_site_le_1e-8 未通过",
    }
    if (
        sha256(spec_path) != RUN_SPEC_SHA256
        or provenance.get("r16_practical_summary_sha256") != sha256(paths["r16_summary"])
        or provenance.get("accepted_calibration_through_r16_sha256") != sha256(paths["r16_calibration"])
        or provenance.get("observations_sha256") != sha256(paths["observations"])
        or provenance.get("action_index_sha256") != sha256(paths["actions"])
        or provenance.get("r16_boundary_eligible") is not False
        or provenance.get("r16_strict_failure_preserved") is not True
        or provenance.get("boundary_acceptance_thresholds_relaxed") is not False
        or validation.get("status") != "fail" or validation.get("cell_id") != CELL
        or set(validation.get("failures", [])) != allowed_failures
        or receipt.get("status") != "pass" or receipt.get("cell_id") != CELL
        or receipt.get("non_clobbering") is not True
        or not all(1e-8 < float(value) <= 2e-8 for value in variances)
    ):
        raise ValueError("R17 失败证据、R16 基线或严格门不匹配")

    observations, actions = load(paths["observations"]), load(paths["actions"])
    indexed = {key(row["params"]): row for row in observations.get("records", [])}
    previous, untouched = copy.deepcopy(indexed.get(KEY)), copy.deepcopy(indexed.get(UNTOUCHED_KEY))
    if not previous or previous.get("status") != "pending" or previous.get("budget") != 32:
        raise ValueError("R17 L40 来源不是原始 pending")
    if not untouched or untouched.get("status") != "pending":
        raise ValueError("R17 L60 pending 基线异常")
    untouched_hash = canonical_sha256(untouched)
    failure = {
        "params": {"alpha": -0.025, "beta": 0.5, "L": 40},
        "status": "failed", "budget": 64, "accepted_only": False,
        "artifact": relative(paths["validation"]), "controller_action_id": ACTION,
        "failure_evidence": {
            "validator_artifact": relative(paths["validation"]), "validator_sha256": sha256(paths["validation"]),
            "manifest_artifact": relative(paths["manifest"]), "manifest_sha256": sha256(paths["manifest"]),
            "receipt_artifact": relative(paths["receipt"]), "receipt_sha256": sha256(paths["receipt"]),
            "failed_gates": validation["failures"],
            "strict_numerical_diagnostics": {
                "center_variance_sz1": variances[0], "ferro_j2_variance_sz1": variances[1],
                "threshold": 1e-8,
            },
            "thresholds_relaxed": False,
        },
        "r17_provenance": {
            "previous_pending_observation": previous,
            "run_spec": {"artifact": relative(spec_path), "sha256": sha256(spec_path)},
            "r16_strict_failure_preserved": True, "r16_boundary_ineligible_preserved": True,
        },
    }
    if forbidden(failure):
        raise ValueError("R17 failed observation 含 value/error")
    indexed[KEY] = failure
    records = sorted(indexed.values(), key=lambda row: key(row["params"]))
    counts = {name: sum(row.get("status") == name for row in records)
              for name in ("success", "failed", "pending")}
    if counts != {"success": 14, "failed": 1, "pending": 1}:
        raise ValueError(f"R17 controller 计数异常: {counts}")
    target = [row for row in actions.get("actions", []) if row.get("action_id") == ACTION]
    if len(target) != 1 or target[0].get("observation_status") != "pending":
        raise ValueError("R17 action 不是唯一 pending")
    target[0].update({"observation_status": "failed", "accepted": False,
                      "artifact": failure["artifact"], "r17_failure_handoff": True,
                      "retry_recommendation": {"next_budget": 128, "thresholds_relaxed": False}})

    pre_obs, pre_actions = sha256(paths["observations"]), sha256(paths["actions"])
    write_json(paths["observations"], {"schema_version": 1, "records": records})
    write_json(paths["actions"], actions)
    post = {key(row["params"]): row for row in load(paths["observations"])["records"]}
    invariants = {
        "l60_pending_unchanged": canonical_sha256(post[UNTOUCHED_KEY]) == untouched_hash,
        "failed_has_no_value_or_error": not forbidden(post[KEY]),
        "r16_boundary_ineligible_preserved": any(
            key(row["params"]) == (-0.05, 0.5, 80) and row.get("boundary_eligible") is False
            for row in load(paths["r16_calibration"])["records"]
        ),
    }
    if not all(invariants.values()):
        raise ValueError(f"R17 provenance 不变量失败: {invariants}")
    audit_path = phase / "r17_failure_ingestion_audit.json"
    write_json(audit_path, {
        "schema_version": 1, "status": "pass_failure", "controller_counts": counts,
        "pre_observations_sha256": pre_obs, "pre_action_index_sha256": pre_actions,
        "post_observations_sha256": sha256(paths["observations"]),
        "post_action_index_sha256": sha256(paths["actions"]), "invariants": invariants,
        "thresholds_relaxed": False, "phase_label_assigned": False,
    })
    summary_path = phase / "r17_failure_ingestion_summary.json"
    summary = {
        "schema_version": 1, "status": "failed_first_cell_ingested", "failed_cell": CELL,
        "counts": {"controller_success_total": 14, "controller_failed_total": 1,
                   "controller_pending_total": 1, "calibration_accepted_total": 7},
        "retry": {"cell": CELL, "budget": 128, "last_budget": True, "thresholds_relaxed": False},
        "ingestion_audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
        "observations": {"artifact": relative(paths["observations"]), "sha256": sha256(paths["observations"])},
        "action_index": {"artifact": relative(paths["actions"]), "sha256": sha256(paths["actions"])},
        "accepted_calibration": {"artifact": relative(paths["r16_calibration"]),
                                 "sha256": sha256(paths["r16_calibration"])},
        "boundary_thresholds_relaxed": False, "stage_b_ready": False,
    }
    write_json(summary_path, summary)
    validation_summary = fetch / "validation" / "summary.json"
    write_json(validation_summary, {"schema_version": 1, "counts": {"pass": 0, "fail": 1},
                                    "cells": [{"cell_id": CELL, "status": "fail",
                                               "artifact": relative(paths["validation"]),
                                               "sha256": sha256(paths["validation"])}]})
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
