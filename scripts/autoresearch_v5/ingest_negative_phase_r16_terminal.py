#!/usr/bin/env python3
"""接入 R16 三初态校准终态，不改 controller。"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from ingest_negative_phase_r6 import load, relative, sha256, verify_checksums, write_json


CELL = "nega-r16-a0050-b0500-L080"
KEY = (-0.05, 0.5, 80)
MODES = ("center_random", "ferro_j2", "domain")
COUNTS = {"success": 14, "failed": 0, "pending": 2}


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


def controller_counts(action_index: dict[str, Any]) -> dict[str, int]:
    rows = action_index.get("actions", [])
    if not isinstance(rows, list):
        raise ValueError("action_index.actions 缺失")
    result = {"success": 0, "failed": 0, "pending": 0}
    for row in rows:
        status = row.get("observation_status") if isinstance(row, dict) else None
        if status not in result:
            raise ValueError(f"未知 controller 状态: {status}")
        result[status] += 1
    return result


def validate_spec(spec: dict[str, Any], paths: dict[str, Path]) -> None:
    cells, settings, provenance = spec.get("cells", []), spec.get("settings", {}), spec.get("provenance", {})
    expected_cell = {
        "cell_id": CELL,
        "params": {"alpha": -0.05, "beta": 0.5, "L": 80, "n_units": 16},
        "budget": 256,
        "retry_of": "nega-r15-a0050-b0500-L080",
        "calibration_only": True,
        "controller_action_id": None,
    }
    if len(cells) != 1 or any(cells[0].get(key) != value for key, value in expected_cell.items()):
        raise ValueError("R16 cell 身份不匹配")
    expected_settings = {
        "nsweeps": 256, "cutoff": 1e-11, "threads": 8, "q_count": 401,
        "init_modes": list(MODES), "noise_profile": "repair", "energy_change_max": 1e-8,
        "energy_spread_max": 1e-6,
    }
    if any(settings.get(key) != value for key, value in expected_settings.items()):
        raise ValueError("R16 三初态修复协议不匹配")
    if settings.get("maxdim_by_L", {}).get("80") != 1200:
        raise ValueError("R16 L80 maxdim 不匹配")
    acceptance = settings.get("acceptance", {})
    strict = {"variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9,
              "sector_tolerance": 1e-8, "spin_gap_min": -1e-8,
              "energy_change_max": 1e-8, "energy_spread_max": 1e-6, "q_count_min": 401}
    if any(acceptance.get(key) != value for key, value in strict.items()):
        raise ValueError("R16 严格门不匹配")
    expected_hashes = {
        "r15_terminal_ingestion_summary_sha256": sha256(paths["r15_summary"]),
        "r15_terminal_ingestion_audit_sha256": sha256(paths["r15_audit"]),
        "r15_failed_calibration_sha256": sha256(paths["r15_failed"]),
        "accepted_calibration_through_r9_sha256": sha256(paths["calibration"]),
        "observations_sha256": sha256(paths["observations"]),
        "action_index_sha256": sha256(paths["actions"]),
    }
    if any(provenance.get(key) != value for key, value in expected_hashes.items()):
        raise ValueError("R16 基线 provenance 不匹配")
    if provenance.get("thresholds_relaxed") is not False or provenance.get("posthoc_branch_selection_forbidden") is not True:
        raise ValueError("R16 门槛或事后选支标记错误")


def child_diagnostics(run: Path) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for mode in MODES:
        child = load(run / f"start_{mode}" / "manifest.json")
        diagnostics, observables = child.get("diagnostics", {}), child.get("observables", {})
        result[mode] = {
            "variance_per_site_sz0": finite(diagnostics.get("variance_per_site_sz0"), f"{mode}.variance0"),
            "variance_per_site_sz1": finite(diagnostics.get("variance_per_site_sz1"), f"{mode}.variance1"),
            "final_truncation_error_sz0": finite(diagnostics.get("final_truncation_error_sz0"), f"{mode}.truncation0"),
            "final_truncation_error_sz1": finite(diagnostics.get("final_truncation_error_sz1"), f"{mode}.truncation1"),
            "final_energy_change_sz0": finite(diagnostics.get("final_energy_change_sz0"), f"{mode}.energy_change0"),
            "final_energy_change_sz1": finite(diagnostics.get("final_energy_change_sz1"), f"{mode}.energy_change1"),
            "total_sz0": finite(diagnostics.get("total_sz0"), f"{mode}.Sz0"),
            "total_sz1": finite(diagnostics.get("total_sz1"), f"{mode}.Sz1"),
            "energy_sz0": finite(observables.get("energy_sz0"), f"{mode}.energy0"),
            "energy_sz1": finite(observables.get("energy_sz1"), f"{mode}.energy1"),
            "spin_gap": finite(observables.get("spin_gap"), f"{mode}.gap"),
            "dominant_structure_factor_ratio": finite(observables.get("dominant_structure_factor_ratio"), f"{mode}.ratio"),
        }
    return result


def main() -> int:
    args = parse_args()
    fetch, spec_path, phase = args.fetch_dir.resolve(), args.run_spec.resolve(), args.phase_dir.resolve()
    run = fetch / CELL
    manifest_path = run / "manifest.json"
    validation_path = choose(fetch / "validation" / f"{CELL}.json", fetch / "validation.json")
    receipt_path = choose(fetch / "receipts" / f"{CELL}.json", fetch / "fetch-receipt.json")
    preview_path = choose(fetch / "previews" / f"{CELL}.json", fetch / "fetch-preview.json")
    paths = {
        "r15_summary": phase / "r15_terminal_ingestion_summary.json",
        "r15_audit": phase / "r15_terminal_ingestion_audit.json",
        "r15_failed": phase / "failed_calibration_r15.json",
        "calibration": phase / "accepted_calibration_through_r9.json",
        "observations": phase / "observations.json",
        "actions": phase / "action_index.json",
    }
    for path in (spec_path, manifest_path, validation_path, receipt_path, preview_path, *paths.values()):
        if not path.is_file():
            raise FileNotFoundError(path)
    validate_spec(load(spec_path), paths)
    if controller_counts(load(paths["actions"])) != COUNTS:
        raise ValueError("R16 前 controller 计数不是 14/0/2")
    receipt, preview = load(receipt_path), load(preview_path)
    if (
        receipt.get("status") != "pass" or receipt.get("non_clobbering") is not True
        or receipt.get("cell_id") != CELL or Path(receipt.get("destination", "")).resolve() != run
        or receipt.get("manifest_sha256") != sha256(manifest_path)
        or receipt.get("preview_sha256") != sha256(preview_path)
        or preview.get("status") != "pass" or preview.get("remote_checksum_status") != "pass"
        or preview.get("destination_exists") is not False
        or Path(preview.get("local_destination", "")).resolve() != run
    ):
        raise ValueError("R16 回传身份或非覆盖门失败")
    parent_hashes = verify_checksums(run)
    child_hashes = {mode: verify_checksums(run / f"start_{mode}") for mode in MODES}
    validation, manifest = load(validation_path), load(manifest_path)
    if (
        validation.get("cell_id") != CELL or Path(validation.get("run_dir", "")).resolve() != run
        or Path(validation.get("run_spec", "")).resolve() != spec_path
        or manifest.get("cell_id") != CELL
        or manifest.get("params") != {"alpha": -0.05, "beta": 0.5, "L": 80, "n_units": 16}
    ):
        raise ValueError("R16 validator 或父 manifest 身份不匹配")
    checks = validation.get("checks", {})
    integrity_keys = ("identity", "parent_checksums", "child_checksums", "provenance", "data_files")
    if any(checks.get(key) is not True for key in integrity_keys):
        raise ValueError("R16 完整性、checksum、provenance 或数据文件门失败")
    accepted = (
        validation.get("status") == "pass" and not validation.get("failures")
        and checks and all(checks.values())
        and manifest.get("status") == "success" and manifest.get("accepted") is True
    )
    not_evaluable = (
        validation.get("status") == "fail" and bool(validation.get("failures"))
        and checks.get("terminal_acceptance") is False
        and manifest.get("status") == "failed" and manifest.get("accepted") is False
    )
    if accepted == not_evaluable:
        raise ValueError("R16 终态不唯一")
    diagnostics = child_diagnostics(run)
    pre_hashes = {name: sha256(path) for name, path in paths.items() if name in {"calibration", "observations", "actions"}}
    validation_summary = fetch / "validation" / "summary.json"
    write_json(validation_summary, {"schema_version": 1, "status": "pass" if accepted else "fail",
        "cell_count": 1, "counts": {"pass": int(accepted), "fail": int(not_evaluable)},
        "rows": [{"cell_id": CELL, "validator_status": validation["status"],
                  "exit_code": 0 if accepted else 1, "output": str(validation_path),
                  "sha256": sha256(validation_path)}]})
    handoff_audit = fetch / "handoff_audit.json"
    write_json(handoff_audit, {"schema_version": 1,
        "status": "pass" if accepted else "pass_not_evaluable_only", "cell_id": CELL,
        "remote_checksums": "parent_and_three_children_pass", "local_checksums": "pass",
        "non_clobbering_fetch": True,
        "checksum_entries": {"parent": len(parent_hashes), "children": {key: len(value) for key, value in child_hashes.items()}},
        "validator": {"status": validation["status"], "sha256": sha256(validation_path)},
        "accepted_only_eligible": accepted, "thresholds_relaxed": False})
    r15_failure = load(paths["r15_failed"])
    if accepted:
        parent_ratio = manifest.get("observables", {}).get("dominant_structure_factor_ratio", {})
        value = finite(parent_ratio.get("value"), "父 dominant ratio.value")
        error = finite(parent_ratio.get("error"), "父 dominant ratio.error")
        record = {
            "params": {"alpha": -0.05, "beta": 0.5, "L": 80}, "status": "success",
            "value": value, "error": error, "budget": 256, "artifact": relative(manifest_path),
            "accepted_only": True, "controller_action_id": None, "calibration_only": True,
            "diagnostics": {"q_peak_over_pi": manifest["observables"]["structure_factor_peak_q_over_pi"],
                            "strict_numerical_gates": diagnostics,
                            "independent_start_energy_spread": validation["energy_spread"]},
            "validation": {"status": "pass", "artifact": relative(validation_path), "sha256": sha256(validation_path)},
            "checksum_receipt": {"artifact": relative(receipt_path), "sha256": sha256(receipt_path)},
            "provenance": manifest["provenance"],
            "r15_failure_provenance": {"record": r15_failure, "sha256": sha256(paths["r15_failed"]), "preserved": True},
        }
        calibration = load(paths["calibration"])
        indexed = {(row["params"]["alpha"], row["params"]["beta"], row["params"]["L"]): row for row in calibration["records"]}
        if KEY in indexed:
            raise ValueError("R16 calibration 已存在")
        indexed[KEY] = record
        calibration_out = phase / "accepted_calibration_through_r16.json"
        if calibration_out.exists():
            raise FileExistsError(calibration_out)
        write_json(calibration_out, {"schema_version": 1,
            "purpose": "R1、R3、R5、R9、R16 的 L80 calibration-only accepted evidence；不进入 controller observations",
            "sources": calibration.get("sources", []) + [
                {"artifact": relative(paths["calibration"]), "sha256": pre_hashes["calibration"]},
                {"artifact": relative(paths["r15_failed"]), "sha256": sha256(paths["r15_failed"])},
            ],
            "records": sorted(indexed.values(), key=lambda row: (row["params"]["alpha"], row["params"]["L"]))})
        result_ref = {"artifact": relative(calibration_out), "sha256": sha256(calibration_out)}
        terminal, calibration_total = "accepted_calibration", 7
    else:
        failure = {"schema_version": 1, "status": "NotEvaluable", "cell_id": CELL,
            "params": {"alpha": -0.05, "beta": 0.5, "L": 80}, "budget": 256,
            "artifact": relative(validation_path), "manifest": relative(manifest_path),
            "receipt": relative(receipt_path), "validator_failures": validation["failures"],
            "strict_numerical_diagnostics": diagnostics, "accepted_only_eligible": False,
            "r15_failure_provenance": {"record": r15_failure, "sha256": sha256(paths["r15_failed"]), "preserved": True},
            "thresholds_relaxed": False, "crossing_assigned": False, "phase_label_assigned": False}
        if forbidden(failure):
            raise ValueError("R16 NotEvaluable evidence 含 value/error")
        failure_out = phase / "failed_calibration_r16.json"
        if failure_out.exists():
            raise FileExistsError(failure_out)
        write_json(failure_out, failure)
        result_ref = {"artifact": relative(failure_out), "sha256": sha256(failure_out)}
        terminal, calibration_total = "not_evaluable_calibration", 6
    if sha256(paths["observations"]) != pre_hashes["observations"] or sha256(paths["actions"]) != pre_hashes["actions"]:
        raise ValueError("R16 意外修改 controller")
    if sha256(paths["calibration"]) != pre_hashes["calibration"]:
        raise ValueError("R16 意外修改既有 accepted calibration")
    audit_path = phase / "r16_terminal_ingestion_audit.json"
    summary_path = phase / "r16_terminal_ingestion_summary.json"
    if audit_path.exists() or summary_path.exists():
        raise FileExistsError("R16 ingestion 输出已存在")
    write_json(audit_path, {"schema_version": 1, "status": "pass", "terminal": terminal,
        "controller_counts": COUNTS, "calibration_accepted_total": calibration_total,
        "controller_unchanged": True, "observations_unchanged": True, "action_index_unchanged": True,
        "r15_and_earlier_provenance_preserved": True, "thresholds_relaxed": False,
        "crossing_assigned": False, "phase_label_assigned": False})
    summary = {"schema_version": 1, "status": terminal, "cell_id": CELL,
        "counts": {"controller_success_total": 14, "controller_failed_total": 0,
                   "controller_pending_total": 2, "calibration_accepted_total": calibration_total},
        "terminal_result": result_ref,
        "ingestion_audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
        "observations": {"artifact": relative(paths["observations"]), "sha256": sha256(paths["observations"])},
        "action_index": {"artifact": relative(paths["actions"]), "sha256": sha256(paths["actions"])},
        "next": {"prepared_only": True, "auto_start": False,
                 "cells": ["alpha=-0.025,beta=0.5,L=40", "alpha=-0.025,beta=0.5,L=60", "alpha=-0.025,beta=0.5,L=80"]},
        "thresholds_relaxed": False}
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
