#!/usr/bin/env python3
"""把 R2 严格重试写入 accepted-only 相图状态。"""

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
EXPECTED_KEY = (-0.35, 0.5, 60)
EXPECTED_CELL = "nega-r2-a0350-b0500-L060"
EXPECTED_ACTION = "act-b39c74e9721492bce614"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise ValueError(f"证据不在项目目录内: {path}") from exc


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def finite_pair(block: dict[str, Any]) -> tuple[float, float]:
    values = block.get("value"), block.get("error")
    if not all(isinstance(item, (int, float)) and math.isfinite(float(item)) for item in values):
        raise ValueError("R2 observable 含非有限数")
    if float(values[1]) < 0:
        raise ValueError("R2 observable error 为负")
    return float(values[0]), float(values[1])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-dir", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--phase-dir", type=Path, required=True)
    parser.add_argument("--controller-report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fetch_dir = args.fetch_dir.resolve()
    run_spec_path = args.run_spec.resolve()
    phase_dir = args.phase_dir.resolve()
    observations_path = phase_dir / "observations.json"
    state_path = phase_dir / "state.json"
    validation_path = fetch_dir / "validation" / f"{EXPECTED_CELL}.json"
    receipt_path = fetch_dir / "receipts" / f"{EXPECTED_CELL}.json"
    manifest_path = fetch_dir / "cells" / EXPECTED_CELL / "manifest.json"
    audit_path = fetch_dir / "audit" / "remote_checksum_20260810_1311.txt"

    run_spec = load(run_spec_path)
    cells = run_spec.get("cells", [])
    if len(cells) != 1:
        raise ValueError("R2 run spec 必须只有一个 cell")
    cell = cells[0]
    if (
        cell.get("cell_id") != EXPECTED_CELL
        or key(cell.get("params", {})) != EXPECTED_KEY
        or int(cell.get("budget", -1)) != 64
        or cell.get("controller_action_id") != EXPECTED_ACTION
        or cell.get("retry_of") != "nega-r1-a0350-b0500-L060"
        or cell.get("calibration_only") is not False
    ):
        raise ValueError("R2 cell 身份或重试策略不匹配")

    for path in (validation_path, receipt_path, manifest_path, audit_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    validation, receipt, manifest = load(validation_path), load(receipt_path), load(manifest_path)
    if validation.get("status") != "pass" or not validation.get("checks"):
        raise ValueError("R2 validator 未通过")
    if not all(value is True for value in validation["checks"].values()):
        raise ValueError("R2 validator 含失败门")
    if validation.get("cell_id") != EXPECTED_CELL:
        raise ValueError("R2 validator cell 身份不匹配")
    if Path(validation.get("run_dir", "")).resolve() != manifest_path.parent.resolve():
        raise ValueError("R2 validator run_dir 不匹配")
    if Path(validation.get("run_spec", "")).resolve() != run_spec_path:
        raise ValueError("R2 validator run spec 不匹配")
    if (
        receipt.get("status") != "pass"
        or receipt.get("cell_id") != EXPECTED_CELL
        or receipt.get("non_clobbering") is not True
        or Path(receipt.get("destination", "")).resolve() != manifest_path.parent.resolve()
    ):
        raise ValueError("R2 回传 receipt 无效")
    for name in ("manifest_sha256", "checksums_sha256", "preview_sha256"):
        value = receipt.get(name)
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"R2 receipt {name} 无效")
    if receipt["manifest_sha256"] != sha256(manifest_path):
        raise ValueError("R2 manifest checksum 与 receipt 不一致")
    if (
        manifest.get("cell_id") != EXPECTED_CELL
        or key(manifest.get("params", {})) != EXPECTED_KEY
        or manifest.get("status") != "success"
        or manifest.get("accepted") is not True
        or int(manifest.get("settings", {}).get("budget", -1)) != 64
    ):
        raise ValueError("R2 manifest 未达到 accepted 身份门")

    value, error = finite_pair(manifest["observables"]["dominant_structure_factor_ratio"])
    q_value, q_error = finite_pair(manifest["observables"]["structure_factor_peak_q_over_pi"])
    observations = load(observations_path)
    records = observations.get("records", [])
    indexed = {key(item["params"]): item for item in records}
    if len(indexed) != len(records) or EXPECTED_KEY not in indexed:
        raise ValueError("controller observations 缺少唯一 R2 参数键")
    current = indexed[EXPECTED_KEY]
    if current.get("status") == "failed":
        if current.get("controller_action_id") != EXPECTED_ACTION or int(current.get("budget", -1)) != 32:
            raise ValueError("R1 失败 observation 身份不匹配")
        previous_failed = current
    elif current.get("status") == "success":
        retry = current.get("retry_provenance", {})
        previous_failed = retry.get("previous_failed_observation")
        if not isinstance(previous_failed, dict):
            raise ValueError("幂等重放缺少 R1 失败 provenance")
    else:
        raise ValueError("R2 只能替换 failed observation")
    if previous_failed.get("status") != "failed" or key(previous_failed.get("params", {})) != EXPECTED_KEY:
        raise ValueError("保留的 R1 失败 provenance 无效")
    previous_artifact = ROOT / str(previous_failed.get("artifact", ""))
    if not previous_artifact.is_file():
        raise FileNotFoundError(previous_artifact)

    candidate = {
        "params": {"alpha": -0.35, "beta": 0.5, "L": 60},
        "status": "success",
        "value": value,
        "error": error,
        "budget": 64,
        "artifact": relative(manifest_path),
        "accepted_only": True,
        "controller_action_id": EXPECTED_ACTION,
        "diagnostics": {
            "q_peak_over_pi": {
                **manifest["observables"]["structure_factor_peak_q_over_pi"],
                "value": q_value,
                "error": q_error,
            }
        },
        "validation": {
            "status": "pass",
            "artifact": relative(validation_path),
            "sha256": sha256(validation_path),
        },
        "checksum_receipt": {
            "artifact": relative(receipt_path),
            "sha256": sha256(receipt_path),
            "manifest_sha256": receipt["manifest_sha256"],
            "checksums_sha256": receipt["checksums_sha256"],
            "preview_sha256": receipt["preview_sha256"],
        },
        "provenance": manifest["provenance"],
        "retry_provenance": {
            "retry_of": "nega-r1-a0350-b0500-L060",
            "previous_failed_observation": previous_failed,
            "previous_failure_artifact_sha256": sha256(previous_artifact),
            "r2_run_spec": relative(run_spec_path),
            "r2_run_spec_sha256": sha256(run_spec_path),
            "r2_receipt": relative(receipt_path),
            "r2_receipt_sha256": sha256(receipt_path),
            "r1_failure_provenance_preserved": True,
        },
    }
    indexed[EXPECTED_KEY] = candidate
    output_records = sorted(
        indexed.values(), key=lambda item: (item["params"]["beta"], item["params"]["alpha"], item["params"]["L"]),
    )
    output_observations = {"schema_version": 1, "records": output_records}

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
    validation_summary_path = fetch_dir / "validation" / "summary.json"
    write_json(validation_summary_path, validation_summary)

    handoff_summary = {
        "schema_version": 1,
        "status": "pass",
        "cell_id": EXPECTED_CELL,
        "remote_checksum_audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
        "receipt": {"artifact": relative(receipt_path), "sha256": sha256(receipt_path)},
        "validation_summary": {"artifact": relative(validation_summary_path), "sha256": sha256(validation_summary_path)},
        "accepted_gate": {
            "validator_pass": True,
            "non_clobbering_fetch": True,
            "local_checksum_pass": True,
            "r1_failure_provenance_preserved": True,
        },
    }
    handoff_summary_path = fetch_dir / "handoff_summary.json"
    write_json(handoff_summary_path, handoff_summary)

    state = load(state_path)
    action = next((item for item in state.get("actions", []) if item.get("action_id") == EXPECTED_ACTION), None)
    if action is None or action.get("state") != "REGISTERED":
        raise ValueError("R2 controller action 未处于 REGISTERED")
    expected_spec = {
        "kind": "phase-diagram-cell",
        "params": {"alpha": -0.35, "beta": 0.5, "L": 60},
        "budget": 32,
    }
    if action.get("spec") != expected_spec:
        raise ValueError("R2 controller action spec 被意外改写")

    controller = {"status": "NOT_EVALUATED", "phase_boundary_ready": False, "phase_label": "not_assigned"}
    if args.controller_report:
        report_path = args.controller_report.resolve()
        report = load(report_path)
        controller = {
            "status": report["status"],
            "reason": report["reason"],
            "report": relative(report_path),
            "report_sha256": sha256(report_path),
            "phase_boundary_ready": report["status"] == "COMPLETE",
            "phase_label": "not_assigned",
        }
    summary = {
        "schema_version": 1,
        "status": "accepted",
        "cell_id": EXPECTED_CELL,
        "accepted_key": {"alpha": -0.35, "beta": 0.5, "L": 60},
        "counts": {
            "validator_pass": 1,
            "controller_accepted": 1,
            "controller_failed": 0,
            "controller_success_total": sum(item.get("status") == "success" for item in output_records),
            "controller_pending_total": sum(item.get("status") == "pending" for item in output_records),
        },
        "validation_summary": {"artifact": relative(validation_summary_path), "sha256": sha256(validation_summary_path)},
        "handoff_summary": {"artifact": relative(handoff_summary_path), "sha256": sha256(handoff_summary_path)},
        "r1_failure": {
            "artifact": previous_failed["artifact"],
            "artifact_sha256": sha256(previous_artifact),
            "preserved_in_observation": True,
        },
        "r2_receipt": {"artifact": relative(receipt_path), "sha256": sha256(receipt_path)},
        "controller": controller,
        "interpretation": "仅更新 accepted-only observation；不得据此伪造 crossing 或相名",
    }

    write_json(observations_path, output_observations)
    action_index_path = phase_dir / "action_index.json"
    if action_index_path.is_file():
        action_index = load(action_index_path)
        for row in action_index.get("actions", []):
            if row.get("action_id") == EXPECTED_ACTION:
                row.update({
                    "observation_status": "success",
                    "accepted": True,
                    "artifact": candidate["artifact"],
                    "accepted_budget": 64,
                    "retry_of_budget": 32,
                })
        write_json(action_index_path, action_index)
    write_json(phase_dir / "r2_ingestion_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
