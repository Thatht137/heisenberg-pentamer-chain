#!/usr/bin/env python3
"""把 R8 严格重试接入 accepted-only 相图状态。"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from ingest_negative_phase_r6 import load, relative, sha256, verify_checksums, write_json


ROOT = Path(__file__).resolve().parents[2]
KEY = (-0.1, 0.5, 60)
CELL = "nega-r8-a0100-b0500-L060"
ACTION = "act-6a4963c3064243f17ed8"


def args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-dir", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--phase-dir", type=Path, required=True)
    return parser.parse_args()


def params_key(value: dict) -> tuple[float, float, int]:
    return float(value["alpha"]), float(value["beta"]), int(value["L"])


def finite(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{label} 不是有限数")
    return float(value)


def main() -> int:
    parsed = args()
    fetch = parsed.fetch_dir.resolve()
    spec_path = parsed.run_spec.resolve()
    phase = parsed.phase_dir.resolve()
    run = fetch / "cells" / CELL
    manifest_path = run / "manifest.json"
    validation_path = fetch / "validation" / f"{CELL}.json"
    receipt_path = fetch / "receipts" / f"{CELL}.json"
    preview_path = fetch / "previews" / f"{CELL}.json"
    observations_path = phase / "observations.json"
    action_path = phase / "action_index.json"
    r7_summary_path = phase / "r7_failure_ingestion_summary.json"
    r7_audit_path = phase / "r7_failure_ingestion_audit.json"
    required = [spec_path, manifest_path, validation_path, receipt_path, preview_path,
                observations_path, action_path, r7_summary_path, r7_audit_path]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)

    spec = load(spec_path)
    cells = spec.get("cells", [])
    settings = spec.get("settings", {})
    if (
        len(cells) != 1 or cells[0].get("cell_id") != CELL
        or params_key(cells[0]["params"]) != KEY or cells[0].get("budget") != 64
        or cells[0].get("controller_action_id") != ACTION
        or cells[0].get("retry_of") != "nega-r7-a0100-b0500-L060"
        or settings.get("nsweeps") != 64 or settings.get("threads") != 8
        or settings.get("q_count") != 401 or settings.get("cutoff") != 1e-11
        or settings.get("acceptance", {}).get("spin_gap_min") != -1e-8
        or spec.get("provenance", {}).get("thresholds_relaxed") is not False
    ):
        raise ValueError("R8 身份或严格门槛不匹配")

    validation, receipt, preview, manifest = map(load, [validation_path, receipt_path, preview_path, manifest_path])
    checks = validation.get("checks", {})
    if validation.get("status") != "pass" or not checks or not all(checks.values()) or validation.get("failures"):
        raise ValueError("R8 validator 未严格通过")
    if (
        validation.get("cell_id") != CELL or Path(validation["run_dir"]).resolve() != run
        or Path(validation["run_spec"]).resolve() != spec_path
        or receipt.get("status") != "pass" or receipt.get("non_clobbering") is not True
        or receipt.get("cell_id") != CELL or Path(receipt["destination"]).resolve() != run
        or preview.get("status") != "pass" or preview.get("destination_exists") is not False
        or preview.get("remote_checksum_status") != "pass"
        or receipt.get("preview_sha256") != sha256(preview_path)
        or receipt.get("manifest_sha256") != sha256(manifest_path)
    ):
        raise ValueError("R8 回传身份或 checksum 门失败")
    parent_hashes = verify_checksums(run)
    child_hashes = {mode: verify_checksums(run / f"start_{mode}") for mode in ("center", "ferro_j2")}
    if manifest.get("status") != "success" or manifest.get("accepted") is not True or manifest.get("cell_id") != CELL:
        raise ValueError("R8 父 manifest 未通过")

    ratios: dict[str, float] = {}
    numerical: dict[str, dict] = {}
    for mode in ("center", "ferro_j2"):
        child = load(run / f"start_{mode}" / "manifest.json")
        diag, obs, gates = child.get("diagnostics", {}), child.get("observables", {}), child.get("acceptance", {})
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
            child.get("status") != "success" or child.get("accepted") is not True
            or params_key(child["params"]) != KEY or child.get("settings", {}).get("nsweeps") != 64
            or not gates or not all(gates.values())
            or max(values["variance_per_site_sz0"], values["variance_per_site_sz1"]) > 1e-8
            or max(values["final_truncation_error_sz0"], values["final_truncation_error_sz1"]) > 1e-9
            or abs(values["total_sz0"]) > 1e-8 or abs(values["total_sz1"] - 1) > 1e-8
            or values["spin_gap"] < -1e-8
        ):
            raise ValueError(f"R8 子结果 {mode} 未通过既定门")
        ratios[mode] = finite(obs.get("dominant_structure_factor_ratio"), f"{mode}.R")
        numerical[mode] = values

    mean = 0.5 * (ratios["center"] + ratios["ferro_j2"])
    half = 0.5 * abs(ratios["center"] - ratios["ferro_j2"])
    parent_obs = manifest.get("observables", {})
    if not math.isclose(parent_obs["dominant_structure_factor_ratio"]["value"], mean, abs_tol=1e-14):
        raise ValueError("R8 父观测量不是双初态均值")
    if not math.isclose(parent_obs["dominant_structure_factor_ratio"]["error"], half, abs_tol=1e-14):
        raise ValueError("R8 父误差不是双初态半差")

    r7_summary, r7_audit = load(r7_summary_path), load(r7_audit_path)
    if (
        r7_summary.get("status") != "blocked_by_validation_failure"
        or r7_summary.get("failed_key") != {"alpha": -0.1, "beta": 0.5, "L": 60}
        or r7_audit.get("status") != "pass_failure_only"
        or spec.get("provenance", {}).get("r7_failure_ingestion_summary_sha256") != sha256(r7_summary_path)
        or spec.get("provenance", {}).get("r7_failure_provenance") != r7_summary.get("failure_evidence")
    ):
        raise ValueError("R7 失败 provenance 基线不匹配")

    observations = load(observations_path)
    indexed = {params_key(row["params"]): row for row in observations.get("records", [])}
    previous = indexed.get(KEY)
    if not previous or previous.get("status") != "failed" or previous.get("controller_action_id") != ACTION:
        raise ValueError("R8 只能替换当前 R7 failed observation")
    previous_artifact = ROOT / previous["artifact"]
    if not previous_artifact.is_file():
        raise FileNotFoundError(previous_artifact)
    candidate = {
        "params": {"alpha": -0.1, "beta": 0.5, "L": 60},
        "status": "success", "value": mean, "error": half, "budget": 64,
        "artifact": relative(manifest_path), "accepted_only": True,
        "controller_action_id": ACTION,
        "diagnostics": {
            "q_peak_over_pi": parent_obs["structure_factor_peak_q_over_pi"],
            "initial_state_sensitivity": {
                "center_rpi": ratios["center"], "ferro_j2_rpi": ratios["ferro_j2"],
                "half_difference": half, "systematic_caution_required": half > 1e-3,
            },
            "strict_numerical_gates": numerical,
        },
        "validation": {"status": "pass", "artifact": relative(validation_path), "sha256": sha256(validation_path)},
        "checksum_receipt": {"artifact": relative(receipt_path), "sha256": sha256(receipt_path)},
        "provenance": manifest["provenance"],
        "r7_failure_provenance": {
            "previous_failed_observation": previous,
            "previous_failure_artifact_sha256": sha256(previous_artifact),
            "r7_ingestion_summary": relative(r7_summary_path),
            "r7_ingestion_summary_sha256": sha256(r7_summary_path), "preserved": True,
        },
    }
    indexed[KEY] = candidate
    records = sorted(indexed.values(), key=lambda row: (row["params"]["beta"], row["params"]["alpha"], row["params"]["L"]))
    counts = {name: sum(row.get("status") == name for row in records) for name in ("success", "failed", "pending")}
    if counts != {"success": 12, "failed": 0, "pending": 4}:
        raise ValueError(f"R8 接入计数异常: {counts}")
    actions = load(action_path)
    target = [row for row in actions.get("actions", []) if row.get("action_id") == ACTION]
    if len(target) != 1 or target[0].get("observation_status") != "failed":
        raise ValueError("R8 action_index 不是唯一 failed action")
    target[0].pop("r7_failure_handoff", None)
    target[0].pop("failure_evidence_sha256", None)
    target[0].update({
        "observation_status": "success", "accepted": True, "artifact": candidate["artifact"],
        "accepted_observation_budget": 64, "original_action_budget": 32,
        "r8_retry_handoff": True,
        "r7_failure_provenance": {"artifact": previous["artifact"], "sha256": sha256(previous_artifact), "preserved": True},
    })

    pre_obs, pre_actions = sha256(observations_path), sha256(action_path)
    write_json(observations_path, {"schema_version": 1, "records": records})
    write_json(action_path, actions)
    validation_summary = fetch / "validation" / "summary.json"
    write_json(validation_summary, {"schema_version": 1, "status": "pass", "cell_count": 1,
                                    "counts": {"pass": 1, "fail": 0},
                                    "rows": [{"cell_id": CELL, "validator_status": "pass", "exit_code": 0,
                                              "output": str(validation_path), "sha256": sha256(validation_path)}]})
    handoff = fetch / "handoff_audit.json"
    write_json(handoff, {"schema_version": 1, "status": "pass", "cell_id": CELL,
                         "remote_checksum": "parent_and_children_pass", "non_clobbering_fetch": True,
                         "local_checksum_entries": {"parent": len(parent_hashes), "children": {k: len(v) for k, v in child_hashes.items()}},
                         "validator": {"status": "pass", "sha256": sha256(validation_path)},
                         "accepted_observable": {"value": mean, "error": half},
                         "r7_failure_provenance_preserved": True})
    audit_path = phase / "r8_ingestion_audit.json"
    write_json(audit_path, {"schema_version": 1, "status": "pass", "pre_observations_sha256": pre_obs,
                            "pre_action_index_sha256": pre_actions, "post_observations_sha256": sha256(observations_path),
                            "post_action_index_sha256": sha256(action_path), "controller_counts": counts,
                            "r7_failure_provenance_preserved": True, "crossing_assigned": False, "phase_label_assigned": False})
    summary_path = phase / "r8_ingestion_summary.json"
    summary = {"schema_version": 1, "status": "accepted", "cell_id": CELL,
               "accepted_key": {"alpha": -0.1, "beta": 0.5, "L": 60},
               "counts": {"validator_pass": 1, "controller_success_total": 12,
                          "controller_failed_total": 0, "controller_pending_total": 4,
                          "calibration_accepted_total": 5},
               "observable": {"value": mean, "error": half},
               "strict_numerical_gates": numerical,
               "handoff_audit": {"artifact": relative(handoff), "sha256": sha256(handoff)},
               "ingestion_audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
               "observations": {"artifact": relative(observations_path), "sha256": sha256(observations_path)},
               "action_index": {"artifact": relative(action_path), "sha256": sha256(action_path)},
               "r7_failure_preserved": True,
               "controller": {"status": "WAITING", "pending": 4, "crossing": "not_assigned", "phase_label": "not_assigned"}}
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
