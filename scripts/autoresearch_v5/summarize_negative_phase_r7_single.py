#!/usr/bin/env python3
"""汇总 R7 唯一 materialized 失败单元，不接入 controller。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CELL_ID = "nega-r7-a0100-b0500-L060"
EXPECTED_KEY = (-0.1, 0.5, 60)
EXPECTED_ACTION = "act-6a4963c3064243f17ed8"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def key(params: dict[str, Any]) -> tuple[float, float, int]:
    return float(params["alpha"]), float(params["beta"]), int(params["L"])


def finite(source: dict[str, Any], name: str, label: str) -> float:
    item = source.get(name)
    if not isinstance(item, (int, float)) or not math.isfinite(float(item)):
        raise ValueError(f"{label}.{name} 不是有限数")
    return float(item)


def verify_checksums(directory: Path) -> dict[str, str]:
    checksum_path = directory / "checksums.sha256"
    if not checksum_path.is_file():
        raise FileNotFoundError(checksum_path)
    verified: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(maxsplit=1)
        name = name.strip().lstrip("*")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"非法 checksum: {line}")
        target = (directory / name).resolve()
        target.relative_to(directory.resolve())
        if not target.is_file() or sha256(target) != digest:
            raise ValueError(f"checksum 失败: {directory.name}/{name}")
        verified[name] = digest
    if not verified:
        raise ValueError(f"空 checksum: {checksum_path}")
    return verified


def contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(name in {"value", "error"} or contains_forbidden_key(item) for name, item in value.items())
    if isinstance(value, list):
        return any(contains_forbidden_key(item) for item in value)
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-dir", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--phase-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fetch_dir = args.fetch_dir.resolve()
    run_spec_path = args.run_spec.resolve()
    phase_dir = args.phase_dir.resolve()
    run_dir = fetch_dir / "cells" / CELL_ID
    manifest_path = run_dir / "manifest.json"
    status_path = run_dir / "status.json"
    preview_path = fetch_dir / "previews" / f"{CELL_ID}.json"
    receipt_path = fetch_dir / "receipts" / f"{CELL_ID}.json"
    validation_path = fetch_dir / "validation" / f"{CELL_ID}.json"
    observations_path = phase_dir / "observations.json"
    action_index_path = phase_dir / "action_index.json"
    required = (
        run_spec_path, manifest_path, status_path, preview_path, receipt_path,
        validation_path, observations_path, action_index_path,
    )
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)

    run_spec = load(run_spec_path)
    cells = run_spec.get("cells", [])
    cells_by_id = {cell.get("cell_id"): cell for cell in cells}
    if len(cells) != 8 or len(cells_by_id) != 8 or CELL_ID not in cells_by_id:
        raise ValueError("R7 run spec 必须含八个唯一 cell")
    cell = cells_by_id[CELL_ID]
    if (
        key(cell.get("params", {})) != EXPECTED_KEY
        or int(cell.get("budget", -1)) != 32
        or cell.get("controller_action_id") != EXPECTED_ACTION
        or cell.get("calibration_only") is not False
    ):
        raise ValueError("R7 materialized cell 身份不匹配")

    preview, receipt = load(preview_path), load(receipt_path)
    if (
        preview.get("status") != "pass"
        or preview.get("cell_id") != CELL_ID
        or preview.get("remote_checksum_status") != "pass"
        or preview.get("destination_exists") is not False
        or Path(preview.get("local_destination", "")).resolve() != run_dir
        or receipt.get("status") != "pass"
        or receipt.get("cell_id") != CELL_ID
        or receipt.get("non_clobbering") is not True
        or Path(receipt.get("destination", "")).resolve() != run_dir
        or receipt.get("preview_sha256") != sha256(preview_path)
        or receipt.get("manifest_sha256") != sha256(manifest_path)
        or receipt.get("checksums_sha256") != sha256(run_dir / "checksums.sha256")
    ):
        raise ValueError("R7 preview/receipt 身份或哈希不匹配")
    files = [path for path in run_dir.rglob("*") if path.is_file()]
    if len(files) != int(preview.get("file_count", -1)) or sum(path.stat().st_size for path in files) != int(preview.get("total_bytes", -1)):
        raise ValueError("R7 文件统计与 preview 不一致")
    parent_hashes = verify_checksums(run_dir)
    child_hashes = {mode: verify_checksums(run_dir / f"start_{mode}") for mode in ("center", "ferro_j2")}

    validation = load(validation_path)
    expected_checks = {
        "unique_run_spec_cell": True,
        "terminal_acceptance": False,
        "negative_alpha_range": True,
        "beta_range": True,
        "parent_checksums": True,
        "children": True,
    }
    failures = validation.get("failures", [])
    if (
        validation.get("status") != "fail"
        or validation.get("cell_id") != CELL_ID
        or Path(validation.get("run_dir", "")).resolve() != run_dir
        or Path(validation.get("run_spec", "")).resolve() != run_spec_path
        or validation.get("checks") != expected_checks
        or not isinstance(failures, list)
        or not failures
    ):
        raise ValueError("R7 validator 失败证据不完整")

    parent, parent_status = load(manifest_path), load(status_path)
    if (
        parent.get("cell_id") != CELL_ID
        or key(parent.get("params", {})) != EXPECTED_KEY
        or parent.get("status") != "failed"
        or parent.get("accepted") is not False
        or parent_status != {"status": "failed", "accepted": False, "returncode": 1}
        or int(parent.get("settings", {}).get("budget", -1)) != 32
    ):
        raise ValueError("R7 父终态不是预期 failed")

    thresholds = {
        "variance_per_site_max": 1e-8,
        "final_truncation_error_max": 1e-9,
        "sector_tolerance": 1e-8,
    }
    child_records: dict[str, dict[str, Any]] = {}
    for mode in ("center", "ferro_j2"):
        directory = run_dir / f"start_{mode}"
        child = load(directory / "manifest.json")
        child_status = load(directory / "status.json")
        settings = child.get("settings", {})
        diagnostics = child.get("diagnostics", {})
        observables = child.get("observables", {})
        acceptance = child.get("acceptance", {})
        if (
            child.get("status") != "success"
            or child.get("accepted") is not False
            or child_status.get("status") != "success"
            or child_status.get("accepted") is not False
            or key(child.get("params", {})) != EXPECTED_KEY
            or int(settings.get("nsweeps", -1)) != 32
            or int(settings.get("q_count", -1)) != 401
            or int(settings.get("maxdim", -1)) != 1000
        ):
            raise ValueError(f"R7 子终态身份异常: {mode}")
        false_flags = sorted(name for name, passed in acceptance.items() if passed is False)
        expected_false = ["nonnegative_gap", "variance_sz0_per_site_le_1e-8", "variance_sz1_per_site_le_1e-8"] if mode == "center" else ["variance_sz0_per_site_le_1e-8", "variance_sz1_per_site_le_1e-8"]
        if false_flags != expected_false:
            raise ValueError(f"R7 {mode} 失败门集合异常: {false_flags}")
        child_records[mode] = {
            "status": "failed_acceptance",
            "accepted": False,
            "false_acceptance_flags": false_flags,
            "energy_sz0": finite(observables, "energy_sz0", mode),
            "energy_sz1": finite(observables, "energy_sz1", mode),
            "spin_gap": finite(observables, "spin_gap", mode),
            "dominant_rpi": finite(observables, "dominant_structure_factor_ratio", mode),
            "q_peak_over_pi": finite(observables, "structure_factor_peak_q_over_pi", mode),
            "structure_factor_peak": finite(observables, "structure_factor_peak", mode),
            "variance_per_site_sz0": finite(diagnostics, "variance_per_site_sz0", mode),
            "variance_per_site_sz1": finite(diagnostics, "variance_per_site_sz1", mode),
            "final_truncation_error_sz0": finite(diagnostics, "final_truncation_error_sz0", mode),
            "final_truncation_error_sz1": finite(diagnostics, "final_truncation_error_sz1", mode),
            "total_sz0": finite(diagnostics, "total_sz0", mode),
            "total_sz1": finite(diagnostics, "total_sz1", mode),
            "actual_maxdim_sz0": int(finite(diagnostics, "actual_maxdim_sz0", mode)),
            "actual_maxdim_sz1": int(finite(diagnostics, "actual_maxdim_sz1", mode)),
            "requested_sweeps": int(settings["nsweeps"]),
            "q_count": int(settings["q_count"]),
            "threshold_comparison": {
                "variance_sz0_ratio_to_limit": diagnostics["variance_per_site_sz0"] / thresholds["variance_per_site_max"],
                "variance_sz1_ratio_to_limit": diagnostics["variance_per_site_sz1"] / thresholds["variance_per_site_max"],
                "truncation_sz0_ratio_to_limit": diagnostics["final_truncation_error_sz0"] / thresholds["final_truncation_error_max"],
                "truncation_sz1_ratio_to_limit": diagnostics["final_truncation_error_sz1"] / thresholds["final_truncation_error_max"],
            },
        }

    center, ferro = child_records["center"], child_records["ferro_j2"]
    differences = {
        "dominant_rpi_absolute_difference": abs(center["dominant_rpi"] - ferro["dominant_rpi"]),
        "dominant_rpi_half_difference": 0.5 * abs(center["dominant_rpi"] - ferro["dominant_rpi"]),
        "energy_sz0_absolute_difference": abs(center["energy_sz0"] - ferro["energy_sz0"]),
        "energy_sz1_absolute_difference": abs(center["energy_sz1"] - ferro["energy_sz1"]),
        "spin_gap_absolute_difference": abs(center["spin_gap"] - ferro["spin_gap"]),
        "structure_factor_peak_absolute_difference": abs(center["structure_factor_peak"] - ferro["structure_factor_peak"]),
        "q_peak_over_pi_absolute_difference": abs(center["q_peak_over_pi"] - ferro["q_peak_over_pi"]),
        "systematic_caution_required": True,
        "interpretation": "数值门失败时双初态差异仅作为失败诊断，不得形成accepted observable",
    }
    parent_observables = parent.get("observables", {})
    parent_diagnostics = {
        "reported_rpi_mean": finite(parent_observables.get("dominant_structure_factor_ratio", {}), "value", "parent.rpi"),
        "reported_rpi_uncertainty": finite(parent_observables.get("dominant_structure_factor_ratio", {}), "error", "parent.rpi"),
        "reported_q_peak_over_pi": finite(parent_observables.get("structure_factor_peak_q_over_pi", {}), "value", "parent.qpeak"),
        "reported_structure_factor_peak": finite(parent_observables.get("structure_factor_peak", {}), "value", "parent.peak"),
    }
    if not math.isclose(parent_diagnostics["reported_rpi_uncertainty"], differences["dominant_rpi_half_difference"], rel_tol=0.0, abs_tol=1e-14):
        raise ValueError("R7 父 Rpi 不确定度未保持双初态半差")

    observations_sha = sha256(observations_path)
    action_index_sha = sha256(action_index_path)
    failure_record = {
        "params": {"alpha": -0.1, "beta": 0.5, "L": 60},
        "status": "failed",
        "budget": 32,
        "artifact": relative(validation_path),
        "controller_action_id": EXPECTED_ACTION,
        "failure_evidence": {
            "validator_status": "fail",
            "validator_checks": validation["checks"],
            "validator_failures": failures,
            "thresholds": thresholds,
            "children": child_records,
            "initial_state_differences": differences,
            "parent_failed_diagnostics_only": parent_diagnostics,
            "checksum_receipt": relative(receipt_path),
            "checksum_receipt_sha256": sha256(receipt_path),
            "manifest": relative(manifest_path),
            "manifest_sha256": sha256(manifest_path),
        },
        "accepted_only_eligible": False,
        "controller_written": False,
    }
    if contains_forbidden_key(failure_record):
        raise ValueError("失败记录不得含 value/error 字段")

    validation_summary_path = fetch_dir / "validation" / "summary.json"
    validation_summary = {
        "schema_version": 1,
        "status": "fail",
        "cell_count": 1,
        "counts": {"pass": 0, "fail": 1},
        "rows": [{
            "cell_id": CELL_ID,
            "validator_status": "fail",
            "exit_code": 1,
            "output": str(validation_path),
            "sha256": sha256(validation_path),
        }],
    }
    write_json(validation_summary_path, validation_summary)
    audit_path = fetch_dir / "handoff_audit.json"
    audit = {
        "schema_version": 1,
        "status": "blocked_by_validation_failure",
        "cell_id": CELL_ID,
        "remote_terminal": {"batch_status": "failed", "returncode": 1, "completed_cells": 0, "materialized_cells": [CELL_ID], "julia_processes": 0},
        "remote_checksum": {"parent": "pass", "children": {"center": "pass", "ferro_j2": "pass"}, "checked_at": "2026-08-11T06:18:47+08:00"},
        "non_clobbering_fetch": {"status": "pass", "artifact": relative(receipt_path), "sha256": sha256(receipt_path), "files": len(files), "bytes": sum(path.stat().st_size for path in files)},
        "local_checksum": {
            "parent": {"status": "pass", "entries": len(parent_hashes)},
            "children": {mode: {"status": "pass", "entries": len(items)} for mode, items in child_hashes.items()},
        },
        "validator": {"status": "fail", "artifact": relative(validation_path), "sha256": sha256(validation_path), "failures": failures},
        "failure_record": failure_record,
        "invariants": {
            "failure_record_has_value_error": False,
            "accepted_only_eligible": False,
            "controller_observations_unchanged_sha256": observations_sha,
            "action_index_unchanged_sha256": action_index_sha,
            "ingest_started": False,
            "retry_started": False,
            "julia_started": False,
        },
    }
    write_json(audit_path, audit)
    unmaterialized = [item["cell_id"] for item in cells if item["cell_id"] != CELL_ID]
    summary_path = fetch_dir / "partial_handoff_summary.json"
    summary = {
        "schema_version": 1,
        "status": "blocked_by_validation_failure",
        "run_id": run_spec.get("run_id"),
        "counts": {"planned": 8, "materialized": 1, "validator_pass": 0, "validator_fail": 1, "unmaterialized": 7},
        "failure_record": failure_record,
        "unmaterialized_cells": unmaterialized,
        "validation_summary": {"artifact": relative(validation_summary_path), "sha256": sha256(validation_summary_path)},
        "handoff_audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
        "run_spec": {"artifact": relative(run_spec_path), "sha256": sha256(run_spec_path)},
        "controller_written": False,
        "retry_started": False,
        "interpretation": "R7唯一materialized cell未通过方差门；双初态数值仅作失败诊断，不得写入value/error或accepted-only",
    }
    if contains_forbidden_key(summary["failure_record"]):
        raise ValueError("summary 失败记录含禁用字段")
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
