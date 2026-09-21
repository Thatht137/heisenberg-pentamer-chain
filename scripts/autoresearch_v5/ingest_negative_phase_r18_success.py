#!/usr/bin/env python3
"""把 R18 最终预算通过结果接入 accepted-only 状态。"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from ingest_negative_phase_r6 import load, relative, sha256, write_json
from ingest_negative_phase_r7_failure import canonical_sha256


RUN_SPEC_SHA256 = "b63ab1bf415596ce8c4e5807537847d5777ab5e020812043852ce82d8126448b"
CELL = "nega-r18-a0025-b0500-L040"
KEY = (-0.025, 0.5, 40)
PENDING_KEY = (-0.025, 0.5, 60)
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
        "validation_summary": fetch / "validation" / "summary.json",
        "validation": fetch / "validation" / f"{CELL}.json",
        "manifest": fetch / CELL / "manifest.json",
        "receipt": fetch / "receipts" / f"{CELL}.json",
        "observations": phase / "observations.json",
        "actions": phase / "action_index.json",
        "r17_summary": phase / "r17_failure_ingestion_summary.json",
        "r17_audit": phase / "r17_failure_ingestion_audit.json",
        "calibration": phase / "accepted_calibration_through_r16.json",
    }
    for path in (spec_path, *paths.values()):
        if not path.is_file():
            raise FileNotFoundError(path)

    spec = load(spec_path)
    provenance = spec.get("provenance", {})
    validation_summary = load(paths["validation_summary"])
    validation = load(paths["validation"])
    manifest = load(paths["manifest"])
    receipt = load(paths["receipt"])
    if (
        sha256(spec_path) != RUN_SPEC_SHA256
        or provenance.get("r17_failure_ingestion_summary_sha256") != sha256(paths["r17_summary"])
        or provenance.get("r17_failure_ingestion_audit_sha256") != sha256(paths["r17_audit"])
        or provenance.get("accepted_calibration_through_r16_sha256") != sha256(paths["calibration"])
        or provenance.get("observations_sha256") != sha256(paths["observations"])
        or provenance.get("action_index_sha256") != sha256(paths["actions"])
        or provenance.get("thresholds_relaxed") is not False
        or provenance.get("last_budget") is not True
        or validation_summary.get("counts") != {"pass": 1, "fail": 0}
        or validation.get("status") != "pass"
        or validation.get("cell_id") != CELL
        or not all(validation.get("checks", {}).values())
        or receipt.get("status") != "pass"
        or receipt.get("cell_id") != CELL
        or receipt.get("non_clobbering") is not True
        or manifest.get("status") != "success"
        or manifest.get("accepted") is not True
        or manifest.get("cell_id") != CELL
        or key(manifest.get("params", {})) != KEY
        or manifest.get("settings", {}).get("budget") != 128
    ):
        raise ValueError("R18 validator、回传、run spec 或 R17 基线不匹配")

    observations, actions = load(paths["observations"]), load(paths["actions"])
    indexed = {key(row["params"]): row for row in observations.get("records", [])}
    previous = copy.deepcopy(indexed.get(KEY))
    pending = copy.deepcopy(indexed.get(PENDING_KEY))
    if (
        not previous or previous.get("status") != "failed" or previous.get("budget") != 64
        or previous.get("controller_action_id") != ACTION or forbidden(previous)
        or not pending or pending.get("status") != "pending"
    ):
        raise ValueError("R17 failed observation 或 L60 pending 基线异常")
    pending_hash = canonical_sha256(pending)
    observable = manifest["observables"]["dominant_structure_factor_ratio"]
    candidate = {
        "params": {"alpha": -0.025, "beta": 0.5, "L": 40},
        "status": "success",
        "value": observable["value"],
        "error": observable["error"],
        "budget": 128,
        "artifact": relative(paths["manifest"]),
        "accepted_only": True,
        "controller_action_id": ACTION,
        "boundary_eligible": True,
        "diagnostics": {
            "q_peak_over_pi": manifest["observables"]["structure_factor_peak_q_over_pi"]["value"],
            "strict_numerical_gates": validation["checks"],
        },
        "validation": {"status": "pass", "artifact": relative(paths["validation"]),
                       "sha256": sha256(paths["validation"])},
        "checksum_receipt": {"artifact": relative(paths["receipt"]),
                             "sha256": sha256(paths["receipt"])},
        "provenance": manifest["provenance"],
        "r17_failure_provenance": {
            "previous_failed_observation": previous,
            "ingestion_summary": relative(paths["r17_summary"]),
            "ingestion_summary_sha256": sha256(paths["r17_summary"]),
            "preserved": True,
        },
        "r18_provenance": {"run_spec": relative(spec_path), "run_spec_sha256": sha256(spec_path),
                           "last_budget": True, "thresholds_relaxed": False},
    }
    indexed[KEY] = candidate
    records = sorted(indexed.values(), key=lambda row: key(row["params"]))
    counts = {name: sum(row.get("status") == name for row in records)
              for name in ("success", "failed", "pending")}
    if counts != {"success": 15, "failed": 0, "pending": 1}:
        raise ValueError(f"R18 接入计数异常: {counts}")

    target = [row for row in actions.get("actions", []) if row.get("action_id") == ACTION]
    if len(target) != 1 or target[0].get("observation_status") != "failed":
        raise ValueError("R18 action 不是唯一 failed")
    target[0].pop("r17_failure_handoff", None)
    target[0].pop("retry_recommendation", None)
    target[0].update({
        "observation_status": "success", "accepted": True, "artifact": candidate["artifact"],
        "accepted_observation_budget": 128, "r18_retry_handoff": True,
        "r17_failure_provenance": {"artifact": previous["artifact"],
                                   "sha256": canonical_sha256(previous), "preserved": True},
    })

    pre_obs, pre_actions = sha256(paths["observations"]), sha256(paths["actions"])
    calibration_hash = sha256(paths["calibration"])
    write_json(paths["observations"], {"schema_version": 1, "records": records})
    write_json(paths["actions"], actions)
    post = {key(row["params"]): row for row in load(paths["observations"])["records"]}
    invariants = {
        "l60_pending_unchanged": canonical_sha256(post[PENDING_KEY]) == pending_hash,
        "r17_failure_provenance_preserved": post[KEY].get("r17_failure_provenance", {}).get("preserved") is True,
        "r16_calibration_unchanged": sha256(paths["calibration"]) == calibration_hash,
        "r16_boundary_ineligible_preserved": any(
            key(row["params"]) == (-0.05, 0.5, 80) and row.get("boundary_eligible") is False
            for row in load(paths["calibration"])["records"]
        ),
    }
    if not all(invariants.values()):
        raise ValueError(f"R18 provenance 不变量失败: {invariants}")

    audit_path = phase / "r18_success_ingestion_audit.json"
    write_json(audit_path, {
        "schema_version": 1, "status": "pass", "controller_counts": counts,
        "calibration_accepted_total": 7, "pre_observations_sha256": pre_obs,
        "pre_action_index_sha256": pre_actions, "post_observations_sha256": sha256(paths["observations"]),
        "post_action_index_sha256": sha256(paths["actions"]), "invariants": invariants,
        "thresholds_relaxed": False, "crossing_assigned": False, "phase_label_assigned": False,
    })
    summary_path = phase / "r18_success_ingestion_summary.json"
    summary = {
        "schema_version": 1, "status": "accepted", "cell_id": CELL,
        "accepted_key": {"alpha": -0.025, "beta": 0.5, "L": 40},
        "counts": {"controller_success_total": 15, "controller_failed_total": 0,
                   "controller_pending_total": 1, "calibration_accepted_total": 7},
        "observable": observable,
        "ingestion_audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
        "observations": {"artifact": relative(paths["observations"]),
                         "sha256": sha256(paths["observations"])},
        "action_index": {"artifact": relative(paths["actions"]), "sha256": sha256(paths["actions"])},
        "accepted_calibration": {"artifact": relative(paths["calibration"]),
                                 "sha256": sha256(paths["calibration"])},
        "r17_failure_provenance_preserved": True,
        "controller": {"status": "WAITING_FOR_L60", "crossing": "not_assigned",
                       "phase_label": "not_assigned"},
        "thresholds_relaxed": False,
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
