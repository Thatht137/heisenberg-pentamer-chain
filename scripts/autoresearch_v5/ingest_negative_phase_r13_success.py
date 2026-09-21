#!/usr/bin/env python3
"""把 R13 严格通过结果接入 accepted-only 相图状态。"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from ingest_negative_phase_r6 import load, relative, sha256, write_json
from ingest_negative_phase_r7_failure import canonical_sha256


ROOT = Path(__file__).resolve().parents[2]
CELL = "nega-r13-a0050-b0500-L060"
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


def main() -> int:
    args = parse_args()
    fetch, spec_path, phase = args.fetch_dir.resolve(), args.run_spec.resolve(), args.phase_dir.resolve()
    paths = {"handoff": fetch / "success_handoff_summary.json", "handoff_audit": fetch / "handoff_audit.json",
             "validation_summary": fetch / "validation/summary.json", "validation": fetch / "validation" / f"{CELL}.json",
             "manifest": fetch / CELL / "manifest.json", "receipt": fetch / "receipts" / f"{CELL}.json",
             "observations": phase / "observations.json", "actions": phase / "action_index.json",
             "r12_summary": phase / "r12_failure_ingestion_summary.json",
             "r12_audit": phase / "r12_failure_ingestion_audit.json",
             "calibration": phase / "accepted_calibration_through_r9.json"}
    for path in (spec_path, *paths.values()):
        if not path.is_file(): raise FileNotFoundError(path)
    spec, handoff = load(spec_path), load(paths["handoff"])
    provenance = spec.get("provenance", {})
    if (
        handoff.get("status") != "accepted" or handoff.get("cell_id") != CELL or handoff.get("budget") != 128
        or handoff.get("validation_summary", {}).get("sha256") != sha256(paths["validation_summary"])
        or handoff.get("handoff_audit", {}).get("sha256") != sha256(paths["handoff_audit"])
        or provenance.get("r12_failure_ingestion_summary_sha256") != sha256(paths["r12_summary"])
        or provenance.get("r12_failure_ingestion_audit_sha256") != sha256(paths["r12_audit"])
        or provenance.get("accepted_calibration_through_r9_sha256") != sha256(paths["calibration"])
        or provenance.get("observations_sha256") != sha256(paths["observations"])
        or provenance.get("action_index_sha256") != sha256(paths["actions"])
        or provenance.get("r6_initial_state_sensitivity_half_difference") != R6_HALF
        or provenance.get("r7_failure_provenance_preserved") is not True
        or provenance.get("r11_accepted_and_r9_r10_failure_provenance_preserved") is not True
        or provenance.get("thresholds_relaxed") is not False
    ): raise ValueError("R13 handoff、R12 基线或 provenance 不匹配")
    observations, actions = load(paths["observations"]), load(paths["actions"])
    indexed = {key(row["params"]): row for row in observations.get("records", [])}
    previous = copy.deepcopy(indexed[KEY])
    locked = {k: copy.deepcopy(indexed[k]) for k in (R11_KEY, R6_KEY, R8_KEY)}
    if (
        previous.get("status") != "failed" or previous.get("budget") != 64
        or previous.get("controller_action_id") != ACTION
        or previous.get("r12_provenance", {}).get("r11_accepted_provenance_preserved") is not True
        or locked[R11_KEY].get("r10_failure_provenance", {}).get("preserved") is not True
        or locked[R6_KEY].get("error") != R6_HALF
        or locked[R8_KEY].get("r7_failure_provenance", {}).get("preserved") is not True
    ): raise ValueError("R12 failed observation 或历史 provenance 不匹配")
    hashes = {k: canonical_sha256(v) for k, v in locked.items()}
    accepted = handoff["accepted_observable"]
    candidate = {
        "params": {"alpha": -0.05, "beta": 0.5, "L": 60}, "status": "success",
        "value": accepted["value"], "error": accepted["error"], "budget": 128,
        "artifact": relative(paths["manifest"]), "accepted_only": True, "controller_action_id": ACTION,
        "diagnostics": {"q_peak_over_pi": handoff["q_peak_over_pi"],
                        "strict_numerical_gates": handoff["strict_numerical_gates"]},
        "validation": {"status": "pass", "artifact": relative(paths["validation"]), "sha256": sha256(paths["validation"])},
        "checksum_receipt": {"artifact": relative(paths["receipt"]), "sha256": sha256(paths["receipt"])},
        "provenance": load(paths["manifest"])["provenance"],
        "r12_failure_provenance": {"previous_failed_observation": previous,
            "previous_failure_artifact_sha256": sha256(ROOT / previous["artifact"]),
            "r12_ingestion_summary": relative(paths["r12_summary"]),
            "r12_ingestion_summary_sha256": sha256(paths["r12_summary"]),
            "r11_and_r9_r10_history_preserved": True, "preserved": True},
    }
    indexed[KEY] = candidate
    records = sorted(indexed.values(), key=lambda row: (row["params"]["beta"], row["params"]["alpha"], row["params"]["L"]))
    counts = {name: sum(row.get("status") == name for row in records) for name in ("success", "failed", "pending")}
    if counts != {"success": 14, "failed": 0, "pending": 2}: raise ValueError(f"R13 接入计数异常: {counts}")
    target = [row for row in actions.get("actions", []) if row.get("action_id") == ACTION]
    if len(target) != 1 or target[0].get("observation_status") != "failed": raise ValueError("R13 action 不是唯一 failed")
    for name in ("r12_failure_handoff", "failure_evidence_sha256", "retry_recommendation"):
        target[0].pop(name, None)
    target[0].update({"observation_status": "success", "accepted": True, "artifact": candidate["artifact"],
                      "accepted_observation_budget": 128, "original_action_budget": 32, "r13_retry_handoff": True,
                      "r12_failure_provenance": {"artifact": previous["artifact"],
                                                  "sha256": canonical_sha256(previous), "preserved": True}})
    pre_obs, pre_actions, cal_hash = sha256(paths["observations"]), sha256(paths["actions"]), sha256(paths["calibration"])
    write_json(paths["observations"], {"schema_version": 1, "records": records})
    write_json(paths["actions"], actions)
    post = {key(row["params"]): row for row in load(paths["observations"])["records"]}
    invariants = {"r11_accepted_unchanged": canonical_sha256(post[R11_KEY]) == hashes[R11_KEY],
                  "r9_r10_history_preserved": post[R11_KEY].get("r10_failure_provenance", {}).get("preserved") is True,
                  "r6_unchanged": canonical_sha256(post[R6_KEY]) == hashes[R6_KEY],
                  "r6_half_difference_preserved": post[R6_KEY].get("error") == R6_HALF,
                  "r8_unchanged": canonical_sha256(post[R8_KEY]) == hashes[R8_KEY],
                  "r7_provenance_preserved": post[R8_KEY].get("r7_failure_provenance", {}).get("preserved") is True,
                  "r12_failure_provenance_embedded": post[KEY].get("r12_failure_provenance", {}).get("preserved") is True,
                  "calibration_unchanged": sha256(paths["calibration"]) == cal_hash}
    if not all(invariants.values()): raise ValueError(f"R13 provenance 不变量失败: {invariants}")
    audit_path = phase / "r13_success_ingestion_audit.json"
    write_json(audit_path, {"schema_version": 1, "status": "pass", "controller_counts": counts,
                            "calibration_accepted_total": 6, "pre_observations_sha256": pre_obs,
                            "pre_action_index_sha256": pre_actions, "post_observations_sha256": sha256(paths["observations"]),
                            "post_action_index_sha256": sha256(paths["actions"]), "invariants": invariants,
                            "thresholds_relaxed": False, "crossing_assigned": False, "phase_label_assigned": False})
    summary_path = phase / "r13_success_ingestion_summary.json"
    summary = {"schema_version": 1, "status": "accepted", "cell_id": CELL,
               "accepted_key": {"alpha": -0.05, "beta": 0.5, "L": 60},
               "counts": {"controller_success_total": 14, "controller_failed_total": 0,
                          "controller_pending_total": 2, "calibration_accepted_total": 6},
               "observable": accepted, "success_handoff": {"artifact": relative(paths["handoff"]), "sha256": sha256(paths["handoff"])},
               "ingestion_audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
               "observations": {"artifact": relative(paths["observations"]), "sha256": sha256(paths["observations"])},
               "action_index": {"artifact": relative(paths["actions"]), "sha256": sha256(paths["actions"])},
               "accepted_calibration": {"artifact": relative(paths["calibration"]), "sha256": sha256(paths["calibration"])},
               "history_provenance_preserved": True,
               "controller": {"status": "NOT_REEVALUATED", "crossing": "not_assigned", "phase_label": "not_assigned"},
               "thresholds_relaxed": False}
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
