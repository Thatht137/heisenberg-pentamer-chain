#!/usr/bin/env python3
"""接入通过实用裁决的 R16 calibration，不改 controller。"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from adjudicate_negative_phase_r16_practical import Audit, CELL, MODES, PARAMS, verify_checksums
from ingest_negative_phase_r6 import load, relative, sha256, write_json


KEY = (-0.05, 0.5, 80)
COUNTS = {"success": 14, "failed": 0, "pending": 2}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-dir", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--adjudication", type=Path, required=True)
    parser.add_argument("--phase-dir", type=Path, required=True)
    return parser.parse_args()


def finite(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{label} 不是有限数")
    return float(value)


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


def validate_baseline(spec: dict[str, Any], paths: dict[str, Path]) -> None:
    cells, settings, provenance = spec.get("cells", []), spec.get("settings", {}), spec.get("provenance", {})
    if (len(cells) != 1 or cells[0].get("cell_id") != CELL or cells[0].get("params") != PARAMS
            or cells[0].get("budget") != 256 or cells[0].get("calibration_only") is not True
            or cells[0].get("controller_action_id") is not None
            or settings.get("init_modes") != list(MODES) or settings.get("noise_profile") != "repair"):
        raise ValueError("R16 run spec 身份不匹配")
    expected = {
        "r15_terminal_ingestion_summary_sha256": sha256(paths["r15_summary"]),
        "r15_terminal_ingestion_audit_sha256": sha256(paths["r15_audit"]),
        "r15_failed_calibration_sha256": sha256(paths["r15_failed"]),
        "accepted_calibration_through_r9_sha256": sha256(paths["calibration"]),
        "observations_sha256": sha256(paths["observations"]),
        "action_index_sha256": sha256(paths["actions"]),
    }
    if any(provenance.get(key) != digest for key, digest in expected.items()):
        raise ValueError("R16 controller 或 calibration 基线 hash 不匹配")
    if provenance.get("thresholds_relaxed") is not False:
        raise ValueError("R16 原严格协议 provenance 不匹配")


def main() -> int:
    args = parse_args()
    fetch, spec_path, adjudication_path, phase = (
        args.fetch_dir.resolve(), args.run_spec.resolve(), args.adjudication.resolve(), args.phase_dir.resolve())
    run = fetch / CELL
    strict_path = fetch / "validation.json"
    paths = {
        "r15_summary": phase / "r15_terminal_ingestion_summary.json",
        "r15_audit": phase / "r15_terminal_ingestion_audit.json",
        "r15_failed": phase / "failed_calibration_r15.json",
        "calibration": phase / "accepted_calibration_through_r9.json",
        "observations": phase / "observations.json",
        "actions": phase / "action_index.json",
    }
    required = (spec_path, adjudication_path, strict_path, run / "manifest.json", fetch / "preview.json",
                fetch / "receipt.json", *paths.values())
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    spec, adjudication = load(spec_path), load(adjudication_path)
    validate_baseline(spec, paths)
    if controller_counts(load(paths["actions"])) != COUNTS:
        raise ValueError("R16 前 controller 计数不是 14/0/2")
    checks = adjudication.get("checks", {})
    strict_ref = adjudication.get("strict_failure_provenance", {})
    if (adjudication.get("status") != "pass"
            or adjudication.get("decision") != "accepted_practical_calibration"
            or adjudication.get("accepted_practical_calibration") is not True
            or adjudication.get("boundary_eligible") is not False
            or adjudication.get("cell_id") != CELL
            or Path(adjudication.get("fetch_dir", "")).resolve() != fetch
            or Path(adjudication.get("run_dir", "")).resolve() != run
            or Path(adjudication.get("run_spec", "")).resolve() != spec_path
            or not checks or not all(value is True for value in checks.values())
            or adjudication.get("policy", {}).get("energy_change_max") != 1e-7
            or adjudication.get("policy", {}).get("energy_spread_max") != 1e-6
            or adjudication.get("policy", {}).get("only_energy_change_gate_relaxed") is not True
            or strict_ref.get("status") != "fail"
            or Path(strict_ref.get("artifact", "")).resolve() != strict_path
            or strict_ref.get("sha256") != sha256(strict_path)):
        raise ValueError("R16 practical adjudication 身份或门槛不匹配")
    integrity = Audit()
    parent_hashes = verify_checksums(run, integrity, "parent_checksums", {"manifest.json", "status.json"})
    child_hashes = {mode: verify_checksums(run / f"start_{mode}", integrity, "child_checksums",
        {"manifest.json", "status.json", "structure_factor_fullq.csv", "string_profile.csv",
         "bond_correlations.csv", "schmidt_spectrum.csv"}) for mode in MODES}
    if integrity.failures:
        raise ValueError(f"R16 本地 checksum 复核失败: {integrity.failures}")
    receipt, preview, manifest = load(fetch / "receipt.json"), load(fetch / "preview.json"), load(run / "manifest.json")
    if (receipt.get("status") != "pass" or receipt.get("non_clobbering") is not True
            or receipt.get("cell_id") != CELL or Path(receipt.get("destination", "")).resolve() != run
            or receipt.get("manifest_sha256") != sha256(run / "manifest.json")
            or receipt.get("preview_sha256") != sha256(fetch / "preview.json")
            or preview.get("status") != "pass" or preview.get("remote_checksum_status") != "pass"
            or preview.get("destination_exists") is not False):
        raise ValueError("R16 回传身份、远端 checksum 或非覆盖门失败")
    observable = adjudication.get("calibration_observable", {})
    value, error = finite(observable.get("value"), "practical value"), finite(observable.get("error"), "practical error")
    parent_observable = manifest.get("observables", {}).get("dominant_structure_factor_ratio", {})
    if (not math.isclose(value, finite(parent_observable.get("value"), "parent value"), rel_tol=0.0, abs_tol=1e-14)
            or not math.isclose(error, finite(parent_observable.get("error"), "parent error"), rel_tol=0.0, abs_tol=1e-14)):
        raise ValueError("R16 practical observable 与父 manifest 不一致")
    pre_hashes = {name: sha256(paths[name]) for name in ("calibration", "observations", "actions")}
    calibration = load(paths["calibration"])
    indexed = {(row["params"]["alpha"], row["params"]["beta"], row["params"]["L"]): row
               for row in calibration.get("records", [])}
    if KEY in indexed:
        raise ValueError("R16 calibration 已存在")
    record = {
        "params": {"alpha": -0.05, "beta": 0.5, "L": 80}, "status": "success",
        "value": value, "error": error, "budget": 256, "artifact": relative(run / "manifest.json"),
        "accepted_only": True, "calibration_only": True, "controller_action_id": None,
        "acceptance_class": "accepted_practical_calibration", "boundary_eligible": False,
        "diagnostics": {"q_peak_over_pi": manifest["observables"]["structure_factor_peak_q_over_pi"],
                        "independent_start_energy_spread": adjudication["energy_spread"],
                        "practical_policy": adjudication["policy"]},
        "adjudication": {"artifact": relative(adjudication_path), "sha256": sha256(adjudication_path)},
        "strict_failure_provenance": {"artifact": relative(strict_path), "sha256": sha256(strict_path),
                                      "preserved": True},
        "checksum_receipt": {"artifact": relative(fetch / "receipt.json"), "sha256": sha256(fetch / "receipt.json")},
        "provenance": manifest.get("provenance", {}),
        "r15_failure_provenance": {"artifact": relative(paths["r15_failed"]),
                                   "sha256": sha256(paths["r15_failed"]), "preserved": True},
    }
    indexed[KEY] = record
    calibration_out = phase / "accepted_calibration_through_r16.json"
    audit_out = phase / "r16_practical_ingestion_audit.json"
    summary_out = phase / "r16_practical_ingestion_summary.json"
    if any(path.exists() for path in (calibration_out, audit_out, summary_out)):
        raise FileExistsError("R16 practical ingestion 输出已存在")
    write_json(calibration_out, {"schema_version": 1,
        "purpose": "R1、R3、R5、R9、R16 的 L80 calibration-only evidence；R16 为 practical 且不用于边界",
        "sources": calibration.get("sources", []) + [
            {"artifact": relative(paths["calibration"]), "sha256": pre_hashes["calibration"]},
            {"artifact": relative(adjudication_path), "sha256": sha256(adjudication_path)},
            {"artifact": relative(strict_path), "sha256": sha256(strict_path)}],
        "records": sorted(indexed.values(), key=lambda row: (row["params"]["alpha"], row["params"]["L"]))})
    if (sha256(paths["observations"]) != pre_hashes["observations"]
            or sha256(paths["actions"]) != pre_hashes["actions"]
            or sha256(paths["calibration"]) != pre_hashes["calibration"]):
        raise ValueError("R16 practical ingestion 意外修改既有证据")
    write_json(audit_out, {"schema_version": 1, "status": "pass_practical_calibration_only",
        "controller_counts": COUNTS, "calibration_accepted_total": 7,
        "controller_unchanged": True, "observations_unchanged": True, "action_index_unchanged": True,
        "boundary_eligible": False, "strict_failure_preserved": True,
        "checksum_entries": {"parent": parent_hashes, "children": child_hashes},
        "crossing_assigned": False, "phase_label_assigned": False})
    summary = {"schema_version": 1, "status": "accepted_practical_calibration", "cell_id": CELL,
        "counts": {"controller_success_total": 14, "controller_failed_total": 0,
                   "controller_pending_total": 2, "calibration_accepted_total": 7},
        "accepted_calibration": {"artifact": relative(calibration_out), "sha256": sha256(calibration_out)},
        "ingestion_audit": {"artifact": relative(audit_out), "sha256": sha256(audit_out)},
        "observations": {"artifact": relative(paths["observations"]), "sha256": sha256(paths["observations"])},
        "action_index": {"artifact": relative(paths["actions"]), "sha256": sha256(paths["actions"])},
        "boundary_eligible": False, "strict_failure_preserved": True,
        "next": {"auto_start": False, "prepared_only": True}}
    write_json(summary_out, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
