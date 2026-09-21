#!/usr/bin/env python3
"""接入 R15 校准成功或失败终态，不改 controller。"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from ingest_negative_phase_r6 import load, relative, sha256, verify_checksums, write_json


ROOT = Path(__file__).resolve().parents[2]
CELL = "nega-r15-a0050-b0500-L080"
KEY = (-0.05, 0.5, 80)
MODES = ("center", "ferro_j2")
R6_HALF = 0.011877542575884303


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-dir", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--phase-dir", type=Path, required=True)
    return parser.parse_args()


def choose(*paths: Path) -> Path:
    found = [path for path in paths if path.is_file()]
    if len(found) != 1:
        raise ValueError(f"证据路径不唯一: {[str(path) for path in paths]}")
    return found[0]


def finite(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{label} 不是有限数")
    return float(value)


def forbidden(value: Any) -> bool:
    if isinstance(value, dict):
        return any(name in {"value", "error"} or forbidden(item) for name, item in value.items())
    if isinstance(value, list):
        return any(forbidden(item) for item in value)
    return False


def main() -> int:
    args = parse_args()
    fetch, spec_path, phase = args.fetch_dir.resolve(), args.run_spec.resolve(), args.phase_dir.resolve()
    run = fetch / CELL
    manifest_path = run / "manifest.json"
    validation_path = choose(fetch / "validation" / f"{CELL}.json", fetch / "validation.json")
    receipt_path = choose(fetch / "receipts" / f"{CELL}.json", fetch / "fetch-receipt.json")
    preview_path = choose(fetch / "previews" / f"{CELL}.json", fetch / "fetch-preview.json")
    paths = {"r14_summary": phase / "r14_failure_ingestion_summary.json",
             "r14_audit": phase / "r14_failure_ingestion_audit.json",
             "r14_failed": phase / "failed_calibration_r14.json",
             "calibration": phase / "accepted_calibration_through_r9.json",
             "observations": phase / "observations.json", "actions": phase / "action_index.json"}
    for path in (spec_path, manifest_path, validation_path, receipt_path, preview_path, *paths.values()):
        if not path.is_file(): raise FileNotFoundError(path)
    spec = load(spec_path)
    cells, settings, provenance = spec.get("cells", []), spec.get("settings", {}), spec.get("provenance", {})
    if (
        len(cells) != 1 or cells[0].get("cell_id") != CELL or cells[0].get("budget") != 128
        or cells[0].get("retry_of") != "nega-r14-a0050-b0500-L080"
        or cells[0].get("calibration_only") is not True or cells[0].get("controller_action_id") is not None
        or cells[0].get("params") != {"alpha": -0.05, "beta": 0.5, "L": 80, "n_units": 16}
        or settings.get("nsweeps") != 128 or settings.get("maxdim_by_L", {}).get("80") != 1200
        or settings.get("acceptance", {}).get("variance_per_site_max") != 1e-8
        or settings.get("acceptance", {}).get("spin_gap_min") != -1e-8
        or provenance.get("r14_failure_ingestion_summary_sha256") != sha256(paths["r14_summary"])
        or provenance.get("r14_failure_ingestion_audit_sha256") != sha256(paths["r14_audit"])
        or provenance.get("r14_failed_calibration_sha256") != sha256(paths["r14_failed"])
        or provenance.get("accepted_calibration_through_r9_sha256") != sha256(paths["calibration"])
        or provenance.get("observations_sha256") != sha256(paths["observations"])
        or provenance.get("action_index_sha256") != sha256(paths["actions"])
        or provenance.get("r6_initial_state_sensitivity_half_difference") != R6_HALF
        or provenance.get("thresholds_relaxed") is not False
    ): raise ValueError("R15 身份、R14 基线或严格门不匹配")
    receipt, preview = load(receipt_path), load(preview_path)
    if (
        receipt.get("status") != "pass" or receipt.get("non_clobbering") is not True
        or receipt.get("cell_id") != CELL or Path(receipt.get("destination", "")).resolve() != run
        or receipt.get("manifest_sha256") != sha256(manifest_path)
        or receipt.get("preview_sha256") != sha256(preview_path)
        or preview.get("status") != "pass" or preview.get("remote_checksum_status") != "pass"
        or preview.get("destination_exists") is not False
        or Path(preview.get("local_destination", "")).resolve() != run
    ): raise ValueError("R15 回传身份或非覆盖门失败")
    parent_hashes = verify_checksums(run)
    child_hashes = {mode: verify_checksums(run / f"start_{mode}") for mode in MODES}
    validation, manifest = load(validation_path), load(manifest_path)
    if (
        validation.get("cell_id") != CELL or Path(validation.get("run_dir", "")).resolve() != run
        or Path(validation.get("run_spec", "")).resolve() != spec_path
        or manifest.get("cell_id") != CELL
        or manifest.get("params") != {"alpha": -0.05, "beta": 0.5, "L": 80, "n_units": 16}
        or manifest.get("settings", {}).get("nsweeps") != 128
        or manifest.get("settings", {}).get("q_count") != 401
    ):
        raise ValueError("R15 validator 或父 manifest 身份不匹配")
    diagnostics, ratios, child_accept = {}, {}, {}
    for mode in MODES:
        child = load(run / f"start_{mode}/manifest.json")
        diag, obs, checks = child.get("diagnostics", {}), child.get("observables", {}), child.get("acceptance", {})
        values = {"variance_per_site_sz0": finite(diag.get("variance_per_site_sz0"), f"{mode}.var0"),
                  "variance_per_site_sz1": finite(diag.get("variance_per_site_sz1"), f"{mode}.var1"),
                  "final_truncation_error_sz0": finite(diag.get("final_truncation_error_sz0"), f"{mode}.trunc0"),
                  "final_truncation_error_sz1": finite(diag.get("final_truncation_error_sz1"), f"{mode}.trunc1"),
                  "total_sz0": finite(diag.get("total_sz0"), f"{mode}.sz0"),
                  "total_sz1": finite(diag.get("total_sz1"), f"{mode}.sz1"),
                  "spin_gap": finite(obs.get("spin_gap"), f"{mode}.gap")}
        common = (child.get("status") == "success" and child.get("settings", {}).get("nsweeps") == 128
                  and child.get("settings", {}).get("q_count") == 401
                  and max(values["final_truncation_error_sz0"], values["final_truncation_error_sz1"]) <= 1e-9
                  and abs(values["total_sz0"]) <= 1e-8 and abs(values["total_sz1"] - 1) <= 1e-8)
        if not common: raise ValueError(f"R15 {mode} 基础门失败")
        child_accept[mode] = (child.get("accepted") is True and checks and all(checks.values())
                              and max(values["variance_per_site_sz0"], values["variance_per_site_sz1"]) <= 1e-8
                              and values["spin_gap"] >= -1e-8)
        diagnostics[mode] = values
        ratios[mode] = finite(obs.get("dominant_structure_factor_ratio"), f"{mode}.R")
    checks = validation.get("checks", {})
    accepted = (validation.get("status") == "pass" and not validation.get("failures")
                and validation.get("checks") and all(validation["checks"].values())
                and manifest.get("status") == "success" and manifest.get("accepted") is True
                and all(child_accept.values()))
    failed = (validation.get("status") == "fail" and manifest.get("status") == "failed"
              and manifest.get("accepted") is False and checks.get("terminal_acceptance") is False
              and all(passed is True for name, passed in checks.items() if name != "terminal_acceptance")
              and validation.get("failures") and not all(child_accept.values()))
    if accepted == failed: raise ValueError("R15 终态不唯一")
    pre_obs, pre_actions, cal_hash = sha256(paths["observations"]), sha256(paths["actions"]), sha256(paths["calibration"])
    validation_summary = fetch / "validation" / "summary.json"
    write_json(validation_summary, {"schema_version": 1, "status": "pass" if accepted else "fail",
        "cell_count": 1, "counts": {"pass": int(accepted), "fail": int(failed)},
        "rows": [{"cell_id": CELL, "validator_status": "pass" if accepted else "fail",
                  "exit_code": 0 if accepted else 1, "output": str(validation_path), "sha256": sha256(validation_path)}]})
    handoff_audit = fetch / "handoff_audit.json"
    write_json(handoff_audit, {"schema_version": 1, "status": "pass" if accepted else "pass_failure_only",
        "cell_id": CELL, "remote_checksums": "parent_and_two_children_pass", "local_checksums": "pass",
        "non_clobbering_fetch": True,
        "checksum_entries": {"parent": len(parent_hashes), "children": {k: len(v) for k, v in child_hashes.items()}},
        "validator": {"status": "pass" if accepted else "fail", "sha256": sha256(validation_path)},
        "accepted_only_eligible": accepted, "thresholds_relaxed": False})
    r14_failure = load(paths["r14_failed"])
    if accepted:
        mean, half = 0.5 * sum(ratios.values()), 0.5 * abs(ratios["center"] - ratios["ferro_j2"])
        parent_obs = manifest["observables"]["dominant_structure_factor_ratio"]
        if not math.isclose(parent_obs["value"], mean, abs_tol=1e-14) or not math.isclose(parent_obs["error"], half, abs_tol=1e-14):
            raise ValueError("R15 父观测量不是双初态均值与半差")
        record = {"params": {"alpha": -0.05, "beta": 0.5, "L": 80}, "status": "success",
            "value": mean, "error": half, "budget": 128, "artifact": relative(manifest_path),
            "accepted_only": True, "controller_action_id": None, "calibration_only": True,
            "diagnostics": {"q_peak_over_pi": manifest["observables"]["structure_factor_peak_q_over_pi"],
                            "strict_numerical_gates": diagnostics},
            "validation": {"status": "pass", "artifact": relative(validation_path), "sha256": sha256(validation_path)},
            "checksum_receipt": {"artifact": relative(receipt_path), "sha256": sha256(receipt_path)},
            "provenance": manifest["provenance"],
            "r14_failure_provenance": {"record": r14_failure, "sha256": sha256(paths["r14_failed"]), "preserved": True}}
        calibration = load(paths["calibration"])
        indexed = {(row["params"]["alpha"], row["params"]["beta"], row["params"]["L"]): row for row in calibration["records"]}
        if KEY in indexed: raise ValueError("R15 calibration 已存在")
        indexed[KEY] = record
        calibration_out = phase / "accepted_calibration_through_r15.json"
        write_json(calibration_out, {"schema_version": 1,
            "purpose": "R1、R3、R5、R9、R15 的 L80 calibration-only accepted evidence；不进入 controller observations",
            "sources": calibration.get("sources", []) + [{"artifact": relative(paths["calibration"]), "sha256": cal_hash},
                {"artifact": relative(paths["r14_failed"]), "sha256": sha256(paths["r14_failed"])}],
            "records": sorted(indexed.values(), key=lambda row: (row["params"]["alpha"], row["params"]["L"]))})
        result_ref = {"artifact": relative(calibration_out), "sha256": sha256(calibration_out)}
        status, calibration_total = "accepted_calibration", 7
    else:
        failure = {"schema_version": 1, "status": "failed_calibration", "cell_id": CELL,
            "params": {"alpha": -0.05, "beta": 0.5, "L": 80}, "budget": 128,
            "artifact": relative(validation_path), "manifest": relative(manifest_path),
            "receipt": relative(receipt_path), "strict_numerical_diagnostics": diagnostics,
            "child_acceptance": child_accept, "accepted_only_eligible": False,
            "r14_failure_provenance": {"record": r14_failure, "sha256": sha256(paths["r14_failed"]), "preserved": True},
            "thresholds_relaxed": False}
        if forbidden(failure): raise ValueError("R15 failure 含 value/error")
        failure_out = phase / "failed_calibration_r15.json"
        write_json(failure_out, failure)
        result_ref = {"artifact": relative(failure_out), "sha256": sha256(failure_out)}
        status, calibration_total = "failed_calibration_final_tier", 6
    if sha256(paths["observations"]) != pre_obs or sha256(paths["actions"]) != pre_actions:
        raise ValueError("R15 意外修改 controller")
    if not accepted and sha256(paths["calibration"]) != cal_hash:
        raise ValueError("R15 失败意外修改 accepted calibration")
    audit_path = phase / "r15_terminal_ingestion_audit.json"
    write_json(audit_path, {"schema_version": 1, "status": "pass", "terminal": status,
        "controller_counts": {"success": 14, "failed": 0, "pending": 2},
        "calibration_accepted_total": calibration_total, "controller_unchanged": True,
        "r14_and_earlier_provenance_preserved": True, "thresholds_relaxed": False,
        "crossing_assigned": False, "phase_label_assigned": False})
    summary_path = phase / "r15_terminal_ingestion_summary.json"
    summary = {"schema_version": 1, "status": status, "cell_id": CELL,
        "counts": {"controller_success_total": 14, "controller_failed_total": 0,
                   "controller_pending_total": 2, "calibration_accepted_total": calibration_total},
        "terminal_result": result_ref, "ingestion_audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
        "observations": {"artifact": relative(paths["observations"]), "sha256": sha256(paths["observations"])},
        "action_index": {"artifact": relative(paths["actions"]), "sha256": sha256(paths["actions"])},
        "thresholds_relaxed": False}
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
