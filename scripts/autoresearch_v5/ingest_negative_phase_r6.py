#!/usr/bin/env python3
"""把 R6 严格重试幂等接入 accepted-only 相图状态。"""

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
EXPECTED_KEY = (-0.1, 0.5, 40)
EXPECTED_CELL = "nega-r6-a0100-b0500-L040"
EXPECTED_ACTION = "act-cd2b4353726834318d6b"
EXPECTED_RETRY = "nega-r5-a0100-b0500-L040"
R5_COUNTS = {
    "controller_success_total": 10,
    "controller_failed_total": 1,
    "controller_pending_total": 5,
    "calibration_accepted_total": 5,
    "r5_materialized": 2,
    "r5_unmaterialized": 8,
}


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise ValueError(f"证据不在项目目录内: {path}") from exc


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


def finite(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{label} 不是有限数")
    return float(value)


def finite_pair(block: dict[str, Any], label: str) -> tuple[float, float]:
    value, error = finite(block.get("value"), f"{label}.value"), finite(block.get("error"), f"{label}.error")
    if error < 0:
        raise ValueError(f"{label}.error 为负")
    return value, error


def verify_checksums(directory: Path) -> dict[str, str]:
    checksum_path = directory / "checksums.sha256"
    if not checksum_path.is_file():
        raise FileNotFoundError(checksum_path)
    verified: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise ValueError(f"非法 checksum 行: {line}")
        expected, name = parts[0], parts[1].strip().lstrip("*")
        if any(char not in "0123456789abcdef" for char in expected):
            raise ValueError(f"非法 checksum: {expected}")
        target = (directory / name).resolve()
        target.relative_to(directory.resolve())
        if not target.is_file() or sha256(target) != expected:
            raise ValueError(f"本地 checksum 失败: {directory.name}/{name}")
        verified[name] = expected
    if not verified:
        raise ValueError(f"空 checksum: {checksum_path}")
    return verified


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
    run_dir = fetch_dir / "cells" / EXPECTED_CELL
    manifest_path = run_dir / "manifest.json"
    validation_path = fetch_dir / "validation" / f"{EXPECTED_CELL}.json"
    receipt_path = fetch_dir / "receipts" / f"{EXPECTED_CELL}.json"
    preview_path = fetch_dir / "previews" / f"{EXPECTED_CELL}.json"
    observations_path = phase_dir / "observations.json"
    state_path = phase_dir / "state.json"
    action_index_path = phase_dir / "action_index.json"
    r5_summary_path = phase_dir / "r5_partial_ingestion_summary.json"
    calibration_path = phase_dir / "accepted_calibration_through_r5.json"
    required = (
        run_spec_path, manifest_path, validation_path, receipt_path, preview_path,
        observations_path, state_path, action_index_path, r5_summary_path, calibration_path,
    )
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)

    run_spec = load(run_spec_path)
    cells = run_spec.get("cells", [])
    if len(cells) != 1:
        raise ValueError("R6 run spec 必须只有一个 cell")
    cell = cells[0]
    settings = run_spec.get("settings", {})
    acceptance = settings.get("acceptance", {})
    if (
        cell.get("cell_id") != EXPECTED_CELL
        or key(cell.get("params", {})) != EXPECTED_KEY
        or int(cell.get("budget", -1)) != 64
        or cell.get("controller_action_id") != EXPECTED_ACTION
        or cell.get("retry_of") != EXPECTED_RETRY
        or cell.get("calibration_only") is not False
        or int(settings.get("nsweeps", -1)) != 64
        or int(settings.get("threads", -1)) != 8
        or int(settings.get("q_count", -1)) != 401
        or float(settings.get("cutoff", -1)) != 1e-11
        or acceptance != {
            "variance_per_site_max": 1e-8,
            "final_truncation_error_max": 1e-9,
            "sector_tolerance": 1e-8,
            "q_count_min": 401,
        }
        or run_spec.get("provenance", {}).get("thresholds_relaxed") is not False
    ):
        raise ValueError("R6 身份或严格门槛不匹配")

    validation, receipt, preview, manifest = (
        load(validation_path), load(receipt_path), load(preview_path), load(manifest_path),
    )
    checks = validation.get("checks")
    if (
        validation.get("status") != "pass"
        or validation.get("cell_id") != EXPECTED_CELL
        or not isinstance(checks, dict)
        or not checks
        or not all(value is True for value in checks.values())
        or validation.get("failures")
        or Path(validation.get("run_dir", "")).resolve() != run_dir
        or Path(validation.get("run_spec", "")).resolve() != run_spec_path
    ):
        raise ValueError("R6 validator 未严格通过或身份不匹配")
    if (
        receipt.get("status") != "pass"
        or receipt.get("cell_id") != EXPECTED_CELL
        or receipt.get("non_clobbering") is not True
        or Path(receipt.get("destination", "")).resolve() != run_dir
        or preview.get("status") != "pass"
        or preview.get("cell_id") != EXPECTED_CELL
        or preview.get("remote_checksum_status") != "pass"
        or preview.get("destination_exists") is not False
        or Path(preview.get("local_destination", "")).resolve() != run_dir
        or receipt.get("preview_sha256") != sha256(preview_path)
        or receipt.get("manifest_sha256") != sha256(manifest_path)
        or receipt.get("checksums_sha256") != sha256(run_dir / "checksums.sha256")
    ):
        raise ValueError("R6 preview/receipt/checksum 身份门失败")
    local_files = [path for path in run_dir.rglob("*") if path.is_file()]
    if len(local_files) != int(preview.get("file_count", -1)) or sum(path.stat().st_size for path in local_files) != int(preview.get("total_bytes", -1)):
        raise ValueError("R6 本地文件统计与 preview 不一致")
    parent_hashes = verify_checksums(run_dir)
    child_hashes = {
        mode: verify_checksums(run_dir / f"start_{mode}")
        for mode in ("center", "ferro_j2")
    }
    if preview.get("hashes", {}).get("manifest.json") != sha256(manifest_path):
        raise ValueError("R6 preview manifest 哈希不匹配")

    if (
        manifest.get("cell_id") != EXPECTED_CELL
        or key(manifest.get("params", {})) != EXPECTED_KEY
        or manifest.get("status") != "success"
        or manifest.get("accepted") is not True
        or int(manifest.get("settings", {}).get("budget", -1)) != 64
        or int(manifest.get("settings", {}).get("q_count", -1)) != 401
    ):
        raise ValueError("R6 父 manifest 未达到 accepted 身份门")
    children: dict[str, dict[str, Any]] = {}
    ratios: dict[str, float] = {}
    child_diagnostics: dict[str, dict[str, float]] = {}
    for mode in ("center", "ferro_j2"):
        child_path = run_dir / f"start_{mode}" / "manifest.json"
        child = load(child_path)
        diagnostics = child.get("diagnostics", {})
        child_acceptance = child.get("acceptance", {})
        if (
            child.get("status") != "success"
            or child.get("accepted") is not True
            or key(child.get("params", {})) != EXPECTED_KEY
            or int(child.get("settings", {}).get("nsweeps", -1)) != 64
            or int(child.get("settings", {}).get("q_count", -1)) != 401
            or not child_acceptance
            or not all(value is True for value in child_acceptance.values())
        ):
            raise ValueError(f"R6 子 manifest {mode} 未严格通过")
        variance_sz0 = finite(diagnostics.get("variance_per_site_sz0"), f"{mode}.variance_sz0")
        variance_sz1 = finite(diagnostics.get("variance_per_site_sz1"), f"{mode}.variance_sz1")
        trunc_sz0 = finite(diagnostics.get("final_truncation_error_sz0"), f"{mode}.trunc_sz0")
        trunc_sz1 = finite(diagnostics.get("final_truncation_error_sz1"), f"{mode}.trunc_sz1")
        total_sz0 = finite(diagnostics.get("total_sz0"), f"{mode}.total_sz0")
        total_sz1 = finite(diagnostics.get("total_sz1"), f"{mode}.total_sz1")
        if (
            max(variance_sz0, variance_sz1) > 1e-8
            or max(trunc_sz0, trunc_sz1) > 1e-9
            or abs(total_sz0) > 1e-8
            or abs(total_sz1 - 1.0) > 1e-8
        ):
            raise ValueError(f"R6 子 manifest {mode} 数值门失败")
        ratios[mode] = finite(child.get("observables", {}).get("dominant_structure_factor_ratio"), f"{mode}.Rpi")
        child_diagnostics[mode] = {
            "variance_per_site_sz0": variance_sz0,
            "variance_per_site_sz1": variance_sz1,
            "final_truncation_error_sz0": trunc_sz0,
            "final_truncation_error_sz1": trunc_sz1,
            "total_sz0": total_sz0,
            "total_sz1": total_sz1,
        }
        children[mode] = child
    mean_ratio = 0.5 * (ratios["center"] + ratios["ferro_j2"])
    half_difference = 0.5 * abs(ratios["center"] - ratios["ferro_j2"])
    value, error = finite_pair(manifest["observables"]["dominant_structure_factor_ratio"], "R6 observable")
    q_value, q_error = finite_pair(manifest["observables"]["structure_factor_peak_q_over_pi"], "R6 q_peak")
    if not math.isclose(value, mean_ratio, rel_tol=0.0, abs_tol=1e-14) or not math.isclose(error, half_difference, rel_tol=0.0, abs_tol=1e-14):
        raise ValueError("R6 父 observable 未显式采用双初态均值/半差")

    r5_summary = load(r5_summary_path)
    r5_summary_hash = sha256(r5_summary_path)
    if (
        r5_summary.get("status") != "blocked_by_validation_failure"
        or r5_summary.get("counts") != R5_COUNTS
        or r5_summary.get("failed_controller_key") != {"alpha": -0.1, "beta": 0.5, "L": 40}
        or run_spec.get("provenance", {}).get("r5_ingestion_summary_sha256") != r5_summary_hash
        or not isinstance(r5_summary.get("failed_evidence"), dict)
    ):
        raise ValueError("R5 failure provenance 基线不匹配")
    calibration = load(calibration_path)
    if len(calibration.get("records", [])) != 5 or sha256(calibration_path) != r5_summary.get("calibration_aggregate", {}).get("sha256"):
        raise ValueError("R5 calibration accepted 基线不匹配")

    observations = load(observations_path)
    records = observations.get("records", [])
    indexed = {key(record["params"]): record for record in records}
    if len(records) != 16 or len(indexed) != 16 or EXPECTED_KEY not in indexed:
        raise ValueError("controller observations 缺少唯一 R6 参数键")
    current = indexed[EXPECTED_KEY]
    if current.get("status") == "failed":
        if (
            current.get("controller_action_id") != EXPECTED_ACTION
            or int(current.get("budget", -1)) != 32
            or current.get("failure_evidence") != r5_summary["failed_evidence"]
            or "value" in current
            or "error" in current
        ):
            raise ValueError("R5 failed observation 身份或 provenance 不匹配")
        previous_failed = current
    elif current.get("status") == "success":
        retry = current.get("r5_failure_provenance", {})
        previous_failed = retry.get("previous_failed_observation")
        if (
            current.get("artifact") != relative(manifest_path)
            or int(current.get("budget", -1)) != 64
            or not isinstance(previous_failed, dict)
            or previous_failed.get("failure_evidence") != r5_summary["failed_evidence"]
        ):
            raise ValueError("R6 幂等重放遇到不同 accepted 结果")
    else:
        raise ValueError("R6 只能替换 R5 failed observation")
    previous_artifact = ROOT / str(previous_failed.get("artifact", ""))
    if previous_failed.get("status") != "failed" or not previous_artifact.is_file():
        raise ValueError("R5 失败证据不存在")

    sensitivity = {
        "kind": "initial_state_half_difference",
        "center_rpi": ratios["center"],
        "ferro_j2_rpi": ratios["ferro_j2"],
        "absolute_difference": abs(ratios["center"] - ratios["ferro_j2"]),
        "half_difference": half_difference,
        "reported_as_observable_error": True,
        "numerical_gates_passed": True,
        "systematic_caution_required": True,
        "interpretation": "validator 通过不消除双初态差异；Rpi 半差作为系统敏感性保留",
    }
    candidate = {
        "params": {"alpha": -0.1, "beta": 0.5, "L": 40},
        "status": "success",
        "value": value,
        "error": error,
        "budget": 64,
        "artifact": relative(manifest_path),
        "accepted_only": True,
        "controller_action_id": EXPECTED_ACTION,
        "diagnostics": {
            "q_peak_over_pi": {**manifest["observables"]["structure_factor_peak_q_over_pi"], "value": q_value, "error": q_error},
            "initial_state_sensitivity": sensitivity,
            "strict_numerical_gates": child_diagnostics,
        },
        "validation": {"status": "pass", "artifact": relative(validation_path), "sha256": sha256(validation_path)},
        "checksum_receipt": {
            "artifact": relative(receipt_path),
            "sha256": sha256(receipt_path),
            "manifest_sha256": receipt["manifest_sha256"],
            "checksums_sha256": receipt["checksums_sha256"],
            "preview_sha256": receipt["preview_sha256"],
            "parent_checksum_entries": len(parent_hashes),
            "child_checksum_entries": {mode: len(entries) for mode, entries in child_hashes.items()},
        },
        "provenance": manifest["provenance"],
        "r5_failure_provenance": {
            "retry_of": EXPECTED_RETRY,
            "previous_failed_observation": previous_failed,
            "previous_failure_artifact_sha256": sha256(previous_artifact),
            "r5_ingestion_summary": relative(r5_summary_path),
            "r5_ingestion_summary_sha256": r5_summary_hash,
            "r6_run_spec": relative(run_spec_path),
            "r6_run_spec_sha256": sha256(run_spec_path),
            "preserved": True,
        },
    }
    indexed[EXPECTED_KEY] = candidate
    output_records = sorted(indexed.values(), key=lambda record: (record["params"]["beta"], record["params"]["alpha"], record["params"]["L"]))
    counts = {
        "success": sum(record.get("status") == "success" for record in output_records),
        "failed": sum(record.get("status") == "failed" for record in output_records),
        "pending": sum(record.get("status") == "pending" for record in output_records),
    }
    if counts != {"success": 11, "failed": 0, "pending": 5}:
        raise ValueError(f"R6 接入后的 controller 计数异常: {counts}")

    state = load(state_path)
    action = next((item for item in state.get("actions", []) if item.get("action_id") == EXPECTED_ACTION), None)
    expected_spec = {"kind": "phase-diagram-cell", "params": {"alpha": -0.1, "beta": 0.5, "L": 40}, "budget": 32}
    if action is None or action.get("state") != "REGISTERED" or action.get("spec") != expected_spec:
        raise ValueError("R6 controller action 不处于原始 REGISTERED 状态")
    action_index = load(action_index_path)
    action_rows = [row for row in action_index.get("actions", []) if row.get("action_id") == EXPECTED_ACTION]
    if len(action_index.get("actions", [])) != 16 or len(action_rows) != 1:
        raise ValueError("R6 action_index 身份不唯一")
    action_row = action_rows[0]
    if action_row.get("observation_status") not in {"failed", "success"}:
        raise ValueError("R6 action_index 不是可替换终态")
    action_row.update({
        "observation_status": "success",
        "accepted": True,
        "artifact": candidate["artifact"],
        "accepted_observation_budget": 64,
        "original_action_budget": 32,
        "r6_retry_handoff": True,
        "r5_failure_provenance": {
            "artifact": previous_failed["artifact"],
            "artifact_sha256": sha256(previous_artifact),
            "preserved": True,
        },
    })

    validation_summary_path = fetch_dir / "validation" / "summary.json"
    validation_summary = {
        "schema_version": 1,
        "status": "pass",
        "cell_count": 1,
        "counts": {"pass": 1, "fail": 0},
        "rows": [{
            "cell_id": EXPECTED_CELL,
            "validator_status": "pass",
            "exit_code": 0,
            "output": str(validation_path),
            "sha256": sha256(validation_path),
        }],
    }
    write_json(validation_summary_path, validation_summary)
    handoff_audit_path = fetch_dir / "handoff_audit.json"
    handoff_audit = {
        "schema_version": 1,
        "status": "pass_with_initial_state_sensitivity",
        "cell_id": EXPECTED_CELL,
        "remote_checksum": {
            "source_hashes": "pass",
            "parent": "pass",
            "children": {"center": "pass", "ferro_j2": "pass"},
            "preview_artifact": relative(preview_path),
            "preview_sha256": sha256(preview_path),
        },
        "non_clobbering_fetch": {"status": "pass", "artifact": relative(receipt_path), "sha256": sha256(receipt_path)},
        "local_checksum": {
            "parent": {"status": "pass", "entries": len(parent_hashes)},
            "children": {mode: {"status": "pass", "entries": len(entries)} for mode, entries in child_hashes.items()},
        },
        "validator": {"status": "pass", "artifact": relative(validation_path), "sha256": sha256(validation_path)},
        "initial_state_sensitivity": sensitivity,
        "accepted_observable": {
            "value": value,
            "error": error,
            "error_definition": "双初态 Rpi 半差",
        },
        "r5_failure_provenance": {
            "artifact": previous_failed["artifact"],
            "artifact_sha256": sha256(previous_artifact),
            "preserved": True,
        },
        "r7_started": False,
    }
    write_json(handoff_audit_path, handoff_audit)

    ingestion_audit_path = phase_dir / "r6_ingestion_audit.json"
    if ingestion_audit_path.is_file():
        pre_observations_sha256 = load(ingestion_audit_path).get("pre_r6_observations_sha256")
        if not isinstance(pre_observations_sha256, str) or len(pre_observations_sha256) != 64:
            raise ValueError("R6 既有 ingest audit 的 pre hash 无效")
    else:
        pre_observations_sha256 = sha256(observations_path)
    write_json(observations_path, {"schema_version": 1, "records": output_records})
    write_json(action_index_path, action_index)
    post_observations_sha256 = sha256(observations_path)
    ingestion_audit = {
        "schema_version": 1,
        "status": "pass_with_initial_state_sensitivity",
        "pre_r6_observations_sha256": pre_observations_sha256,
        "post_r6_observations_sha256": post_observations_sha256,
        "input_evidence": {
            "run_spec": {"artifact": relative(run_spec_path), "sha256": sha256(run_spec_path)},
            "validation_summary": {"artifact": relative(validation_summary_path), "sha256": sha256(validation_summary_path)},
            "handoff_audit": {"artifact": relative(handoff_audit_path), "sha256": sha256(handoff_audit_path)},
            "r5_ingestion_summary": {"artifact": relative(r5_summary_path), "sha256": r5_summary_hash},
        },
        "invariants": {
            "controller_counts": counts,
            "calibration_accepted_total": 5,
            "r5_failure_provenance_preserved": True,
            "initial_state_sensitivity_explicit": True,
            "crossing_assigned": False,
            "phase_label_assigned": False,
            "r7_started": False,
        },
        "initial_state_sensitivity": sensitivity,
        "outputs": {
            "observations": relative(observations_path),
            "action_index": relative(action_index_path),
        },
    }
    write_json(ingestion_audit_path, ingestion_audit)
    summary = {
        "schema_version": 1,
        "status": "accepted_with_initial_state_sensitivity",
        "cell_id": EXPECTED_CELL,
        "accepted_key": {"alpha": -0.1, "beta": 0.5, "L": 40},
        "counts": {
            "validator_pass": 1,
            "controller_success_total": 11,
            "controller_failed_total": 0,
            "controller_pending_total": 5,
            "calibration_accepted_total": 5,
        },
        "observable": {"value": value, "error": error},
        "initial_state_sensitivity": sensitivity,
        "handoff_audit": {"artifact": relative(handoff_audit_path), "sha256": sha256(handoff_audit_path)},
        "ingestion_audit": {"artifact": relative(ingestion_audit_path), "sha256": sha256(ingestion_audit_path)},
        "observations": {"artifact": relative(observations_path), "sha256": sha256(observations_path)},
        "action_index": {"artifact": relative(action_index_path), "sha256": sha256(action_index_path)},
        "r5_failure": {"artifact": previous_failed["artifact"], "artifact_sha256": sha256(previous_artifact), "preserved_in_observation": True},
        "controller": {"status": "NOT_REEVALUATED", "phase_boundary_ready": False, "crossing": "not_assigned", "phase_label": "not_assigned"},
        "r7_started": False,
        "interpretation": "R6 仅替换 R5 failed observation；validator 通过但双初态 Rpi 半差作为系统敏感性保留，不据此赋 crossing 或相名",
    }
    summary_path = phase_dir / "r6_ingestion_summary.json"
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
