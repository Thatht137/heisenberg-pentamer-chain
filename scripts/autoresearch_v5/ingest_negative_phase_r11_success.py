#!/usr/bin/env python3
"""把 R11 严格通过结果接入 accepted-only 相图状态。"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from ingest_negative_phase_r6 import load, relative, sha256, write_json
from ingest_negative_phase_r7_failure import canonical_sha256


ROOT = Path(__file__).resolve().parents[2]
CELL = "nega-r11-a0050-b0500-L040"
KEY = (-0.05, 0.5, 40)
R6_KEY = (-0.1, 0.5, 40)
R8_KEY = (-0.1, 0.5, 60)
ACTION = "act-fffdf93a9cae183cb1c1"
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
        "handoff": fetch / "success_handoff_summary.json", "handoff_audit": fetch / "handoff_audit.json",
        "validation_summary": fetch / "validation" / "summary.json",
        "validation": fetch / "validation" / f"{CELL}.json", "manifest": fetch / CELL / "manifest.json",
        "receipt": fetch / "receipts" / f"{CELL}.json",
        "observations": phase / "observations.json", "actions": phase / "action_index.json",
        "r10_summary": phase / "r10_failure_ingestion_summary.json",
        "r10_audit": phase / "r10_failure_ingestion_audit.json",
        "calibration": phase / "accepted_calibration_through_r9.json",
    }
    for path in (spec_path, *paths.values()):
        if not path.is_file():
            raise FileNotFoundError(path)
    spec, handoff = load(spec_path), load(paths["handoff"])
    provenance = spec.get("provenance", {})
    if (
        handoff.get("status") != "accepted" or handoff.get("cell_id") != CELL or handoff.get("budget") != 128
        or handoff.get("validation_summary", {}).get("sha256") != sha256(paths["validation_summary"])
        or handoff.get("handoff_audit", {}).get("sha256") != sha256(paths["handoff_audit"])
        or provenance.get("r10_failure_ingestion_summary_sha256") != sha256(paths["r10_summary"])
        or provenance.get("r10_failure_ingestion_audit_sha256") != sha256(paths["r10_audit"])
        or provenance.get("accepted_calibration_through_r9_sha256") != sha256(paths["calibration"])
        or provenance.get("observations_sha256") != sha256(paths["observations"])
        or provenance.get("action_index_sha256") != sha256(paths["actions"])
        or provenance.get("r6_initial_state_sensitivity_half_difference") != R6_HALF
        or provenance.get("r7_failure_provenance_preserved") is not True
        or provenance.get("r9_failure_provenance_preserved") is not True
        or provenance.get("thresholds_relaxed") is not False
    ):
        raise ValueError("R11 handoff、R10 基线或 provenance 不匹配")
    observations, actions = load(paths["observations"]), load(paths["actions"])
    indexed = {key(row["params"]): row for row in observations.get("records", [])}
    previous = copy.deepcopy(indexed.get(KEY))
    r6_before, r8_before = copy.deepcopy(indexed[R6_KEY]), copy.deepcopy(indexed[R8_KEY])
    if (
        not previous or previous.get("status") != "failed" or previous.get("budget") != 64
        or previous.get("controller_action_id") != ACTION or forbidden(previous)
        or previous.get("r10_provenance", {}).get("r9_failure_provenance_preserved") is not True
        or r6_before.get("error") != R6_HALF
        or r8_before.get("r7_failure_provenance", {}).get("preserved") is not True
    ):
        raise ValueError("R10 failed observation 或历史 provenance 不匹配")
    r6_hash, r8_hash = canonical_sha256(r6_before), canonical_sha256(r8_before)
    obs = handoff["accepted_observable"]
    candidate = {
        "params": {"alpha": -0.05, "beta": 0.5, "L": 40}, "status": "success",
        "value": obs["value"], "error": obs["error"], "budget": 128,
        "artifact": relative(paths["manifest"]), "accepted_only": True, "controller_action_id": ACTION,
        "diagnostics": {"q_peak_over_pi": handoff["q_peak_over_pi"],
                        "strict_numerical_gates": handoff["strict_numerical_gates"]},
        "validation": {"status": "pass", "artifact": relative(paths["validation"]),
                       "sha256": sha256(paths["validation"])},
        "checksum_receipt": {"artifact": relative(paths["receipt"]), "sha256": sha256(paths["receipt"])},
        "provenance": load(paths["manifest"])["provenance"],
        "r10_failure_provenance": {
            "previous_failed_observation": previous,
            "previous_failure_artifact_sha256": sha256(ROOT / previous["artifact"]),
            "r10_ingestion_summary": relative(paths["r10_summary"]),
            "r10_ingestion_summary_sha256": sha256(paths["r10_summary"]),
            "r9_failure_provenance_preserved": True, "preserved": True,
        },
    }
    indexed[KEY] = candidate
    records = sorted(indexed.values(), key=lambda row: (row["params"]["beta"], row["params"]["alpha"], row["params"]["L"]))
    counts = {name: sum(row.get("status") == name for row in records) for name in ("success", "failed", "pending")}
    if counts != {"success": 13, "failed": 0, "pending": 3}:
        raise ValueError(f"R11 接入计数异常: {counts}")
    target = [row for row in actions.get("actions", []) if row.get("action_id") == ACTION]
    if len(target) != 1 or target[0].get("observation_status") != "failed":
        raise ValueError("R11 action 不是唯一 failed")
    target[0].pop("r10_failure_handoff", None)
    target[0].pop("failure_evidence_sha256", None)
    target[0].pop("retry_recommendation", None)
    target[0].update({
        "observation_status": "success", "accepted": True, "artifact": candidate["artifact"],
        "accepted_observation_budget": 128, "original_action_budget": 32, "r11_retry_handoff": True,
        "r10_failure_provenance": {"artifact": previous["artifact"],
                                   "sha256": canonical_sha256(previous), "preserved": True},
    })
    pre_obs, pre_actions, calibration_hash = sha256(paths["observations"]), sha256(paths["actions"]), sha256(paths["calibration"])
    write_json(paths["observations"], {"schema_version": 1, "records": records})
    write_json(paths["actions"], actions)
    post = {key(row["params"]): row for row in load(paths["observations"])["records"]}
    invariants = {
        "r6_observation_unchanged": canonical_sha256(post[R6_KEY]) == r6_hash,
        "r6_half_difference_preserved": post[R6_KEY].get("error") == R6_HALF,
        "r8_observation_unchanged": canonical_sha256(post[R8_KEY]) == r8_hash,
        "r7_failure_provenance_preserved": post[R8_KEY].get("r7_failure_provenance", {}).get("preserved") is True,
        "r9_r10_failure_provenance_embedded": post[KEY].get("r10_failure_provenance", {}).get("preserved") is True,
        "calibration_unchanged": sha256(paths["calibration"]) == calibration_hash,
    }
    if not all(invariants.values()):
        raise ValueError(f"R11 provenance 不变量失败: {invariants}")
    audit_path = phase / "r11_success_ingestion_audit.json"
    write_json(audit_path, {
        "schema_version": 1, "status": "pass", "controller_counts": counts, "calibration_accepted_total": 6,
        "pre_observations_sha256": pre_obs, "pre_action_index_sha256": pre_actions,
        "post_observations_sha256": sha256(paths["observations"]),
        "post_action_index_sha256": sha256(paths["actions"]), "invariants": invariants,
        "thresholds_relaxed": False, "crossing_assigned": False, "phase_label_assigned": False,
    })
    summary_path = phase / "r11_success_ingestion_summary.json"
    summary = {
        "schema_version": 1, "status": "accepted", "cell_id": CELL,
        "accepted_key": {"alpha": -0.05, "beta": 0.5, "L": 40},
        "counts": {"controller_success_total": 13, "controller_failed_total": 0,
                   "controller_pending_total": 3, "calibration_accepted_total": 6},
        "observable": obs, "success_handoff": {"artifact": relative(paths["handoff"]), "sha256": sha256(paths["handoff"])},
        "ingestion_audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
        "observations": {"artifact": relative(paths["observations"]), "sha256": sha256(paths["observations"])},
        "action_index": {"artifact": relative(paths["actions"]), "sha256": sha256(paths["actions"])},
        "accepted_calibration": {"artifact": relative(paths["calibration"]), "sha256": sha256(paths["calibration"])},
        "r9_r10_failure_provenance_preserved": True,
        "controller": {"status": "NOT_REEVALUATED", "crossing": "not_assigned", "phase_label": "not_assigned"},
        "thresholds_relaxed": False,
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
