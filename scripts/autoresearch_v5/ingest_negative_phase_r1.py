#!/usr/bin/env python3
"""把 R1 验证结果写入本地 accepted-only 相图状态。"""

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


def same_params(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return key(left) == key(right)


def action_id(spec: dict[str, Any]) -> str:
    encoded = json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "act-" + hashlib.sha256(encoded).hexdigest()[:20]


def accepted_record(
    cell: dict[str, Any], manifest_path: Path, validation_path: Path,
    receipt_path: Path, manifest: dict[str, Any], receipt: dict[str, Any],
) -> dict[str, Any]:
    observable = manifest["observables"]["dominant_structure_factor_ratio"]
    q_peak = manifest["observables"]["structure_factor_peak_q_over_pi"]
    value, error = observable.get("value"), observable.get("error")
    if not all(isinstance(item, (int, float)) and math.isfinite(float(item)) for item in (value, error)):
        raise ValueError(f"{cell['cell_id']} 的 observable 非有限数")
    if float(error) < 0:
        raise ValueError(f"{cell['cell_id']} 的 observable error 为负")
    if not all(
        isinstance(q_peak.get(name), (int, float)) and math.isfinite(float(q_peak[name]))
        for name in ("value", "error")
    ):
        raise ValueError(f"{cell['cell_id']} 的 q_peak 非有限数")
    return {
        "params": {name: cell["params"][name] for name in ("alpha", "beta", "L")},
        "status": "success",
        "value": float(value),
        "error": float(error),
        "budget": int(cell["budget"]),
        "artifact": relative(manifest_path),
        "accepted_only": True,
        "controller_action_id": cell.get("controller_action_id"),
        "diagnostics": {"q_peak_over_pi": q_peak},
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
    }


def failed_record(
    cell: dict[str, Any], validation_path: Path, receipt_path: Path,
    receipt: dict[str, Any], validation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "params": {name: cell["params"][name] for name in ("alpha", "beta", "L")},
        "status": "failed",
        "budget": int(cell["budget"]),
        "artifact": relative(validation_path),
        "controller_action_id": cell.get("controller_action_id"),
        "failure_evidence": {
            "validator_status": validation.get("status"),
            "checks": validation.get("checks", {}),
            "receipt": relative(receipt_path),
            "receipt_sha256": sha256(receipt_path),
            "manifest_sha256": receipt["manifest_sha256"],
        },
    }


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
    validation_summary_path = fetch_dir / "validation" / "summary.json"

    run_spec = load(run_spec_path)
    state = load(state_path)
    observations = load(observations_path)
    validation_summary = load(validation_summary_path)
    cells = {item["cell_id"]: item for item in run_spec["cells"]}
    actions = {item["action_id"]: item for item in state["actions"]}
    existing = {key(item["params"]): item for item in observations["records"]}
    if len(existing) != len(observations["records"]):
        raise ValueError("observations 存在重复参数键")
    rows = validation_summary.get("rows")
    if not isinstance(rows, list) or validation_summary.get("cell_count") != len(rows):
        raise ValueError("validation summary 计数不一致")

    accepted_controller: list[dict[str, Any]] = []
    accepted_calibration: list[dict[str, Any]] = []
    failed_controller: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        cell_id = row.get("cell_id")
        if cell_id in seen or cell_id not in cells:
            raise ValueError(f"未知或重复 validator cell: {cell_id}")
        seen.add(cell_id)
        cell = cells[cell_id]
        manifest_path = fetch_dir / "cells" / cell_id / "manifest.json"
        validation_path = fetch_dir / "validation" / f"{cell_id}.json"
        receipt_path = fetch_dir / "receipts" / f"{cell_id}.json"
        for path in (manifest_path, validation_path, receipt_path):
            if not path.is_file():
                raise FileNotFoundError(path)
        manifest, validation, receipt = load(manifest_path), load(validation_path), load(receipt_path)
        if row.get("validator_status") != validation.get("status"):
            raise ValueError(f"{cell_id} 的 summary 与 validator 状态不一致")
        expected_exit = 0 if validation.get("status") == "pass" else 1
        if row.get("exit_code") != expected_exit:
            raise ValueError(f"{cell_id} 的 validator exit code 不一致")
        if Path(row.get("output", "")).resolve() != validation_path.resolve():
            raise ValueError(f"{cell_id} 的 validator 输出路径不一致")
        if validation.get("cell_id") != cell_id:
            raise ValueError(f"{cell_id} 的 validator 身份不一致")
        if Path(validation.get("run_dir", "")).resolve() != manifest_path.parent.resolve():
            raise ValueError(f"{cell_id} 的 validator run_dir 不一致")
        if not same_params(cell["params"], manifest.get("params", {})):
            raise ValueError(f"{cell_id} 的 run spec 与 manifest 参数不一致")
        if manifest.get("cell_id") != cell_id:
            raise ValueError(f"{cell_id} 的 manifest 身份不一致")
        if int(cell["budget"]) != int(manifest.get("settings", {}).get("budget", -1)):
            raise ValueError(f"{cell_id} 的 budget 不一致")
        if (
            receipt.get("status") != "pass"
            or receipt.get("cell_id") != cell_id
            or receipt.get("non_clobbering") is not True
        ):
            raise ValueError(f"{cell_id} 的回传 receipt 无效")
        if Path(receipt.get("destination", "")).resolve() != manifest_path.parent.resolve():
            raise ValueError(f"{cell_id} 的 receipt destination 不一致")
        for name in ("manifest_sha256", "checksums_sha256", "preview_sha256"):
            value = receipt.get(name)
            if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ValueError(f"{cell_id} 的 {name} 无效")
        if receipt.get("manifest_sha256") != sha256(manifest_path):
            raise ValueError(f"{cell_id} 的 manifest checksum 不一致")
        action_name = cell.get("controller_action_id")
        calibration_only = bool(cell.get("calibration_only"))
        if calibration_only != (int(cell["params"]["L"]) == 80):
            raise ValueError(f"{cell_id} 的 calibration_only 与 L 不一致")
        if calibration_only:
            if action_name is not None:
                raise ValueError(f"{cell_id} 不得伪造 controller action")
        else:
            current_key = key(cell["params"])
            if current_key not in existing:
                raise ValueError(f"{cell_id} 不在 controller observations 中")
            action = actions.get(action_name)
            if not action or action.get("state") != "REGISTERED":
                raise ValueError(f"{cell_id} 没有 REGISTERED controller action")
            expected_spec = {
                "kind": "phase-diagram-cell",
                "params": {name: cell["params"][name] for name in ("alpha", "beta", "L")},
                "budget": int(cell["budget"]),
            }
            if action.get("spec") != expected_spec or action_id(expected_spec) != action_name:
                raise ValueError(f"{cell_id} 的 controller action 不匹配")

        if validation.get("status") == "pass":
            checks = validation.get("checks", {})
            if not checks or not all(value is True for value in checks.values()):
                raise ValueError(f"{cell_id} 的 pass validator 含未通过检查")
            if manifest.get("status") != "success" or manifest.get("accepted") is not True:
                raise ValueError(f"{cell_id} 的父 manifest 未 accepted")
            record = accepted_record(
                cell, manifest_path, validation_path, receipt_path, manifest, receipt,
            )
            if calibration_only:
                accepted_calibration.append(record | {"calibration_only": True})
            else:
                accepted_controller.append(record)
                existing[current_key] = record
        elif validation.get("status") == "fail":
            if calibration_only:
                raise ValueError(f"校准 cell 失败，需显式处理: {cell_id}")
            record = failed_record(cell, validation_path, receipt_path, receipt, validation)
            failed_controller.append(record)
            existing[current_key] = record
        else:
            raise ValueError(f"{cell_id} 的 validator 状态非法")

    if len(accepted_controller) != 7 or len(accepted_calibration) != 3 or len(failed_controller) != 1:
        raise ValueError("R1 预期必须为 controller pass=7、L80 pass=3、controller fail=1")
    if key(failed_controller[0]["params"]) != (-0.35, 0.5, 60):
        raise ValueError("R1 唯一失败必须是 alpha=-0.35, beta=0.5, L=60")

    records = sorted(existing.values(), key=lambda item: (item["params"]["beta"], item["params"]["alpha"], item["params"]["L"]))
    output_observations = {"schema_version": 1, "records": records}
    calibration = {
        "schema_version": 1,
        "purpose": "L80 calibration-only accepted evidence; not controller observations",
        "source_validation_summary": relative(validation_summary_path),
        "records": sorted(accepted_calibration, key=lambda item: key(item["params"])),
    }

    status_by_key = {key(item["params"]): item for item in records}
    action_rows = []
    for action in sorted(state["actions"], key=lambda item: item["action_id"]):
        record = status_by_key.get(key(action["spec"]["params"]))
        action_rows.append({
            "action_id": action["action_id"],
            "lifecycle_state": action["state"],
            "params": action["spec"]["params"],
            "budget": action["spec"]["budget"],
            "observation_status": record.get("status") if record else "missing",
            "accepted": bool(record and record.get("status") == "success"),
            "artifact": record.get("artifact") if record else None,
        })
    action_index = {
        "schema_version": 1,
        "goal_id": state["goal_id"],
        "source_state": relative(state_path),
        "actions": action_rows,
    }

    controller = {"status": "NOT_EVALUATED", "phase_label": "not_assigned"}
    if args.controller_report:
        controller_report = load(args.controller_report.resolve())
        controller = {
            "status": controller_report["status"],
            "reason": controller_report["reason"],
            "report": relative(args.controller_report.resolve()),
            "phase_boundary_ready": controller_report["status"] == "COMPLETE",
            "phase_label": "not_assigned",
        }
    summary = {
        "schema_version": 1,
        "status": "not_ready" if controller.get("status") != "COMPLETE" else "boundary_ready",
        "source": {
            "run_spec": relative(run_spec_path),
            "validation_summary": relative(validation_summary_path),
            "validation_summary_sha256": sha256(validation_summary_path),
        },
        "counts": {
            "validator_pass": len(accepted_controller) + len(accepted_calibration),
            "controller_accepted": len(accepted_controller),
            "calibration_accepted": len(accepted_calibration),
            "controller_failed": len(failed_controller),
            "controller_pending": sum(item["status"] == "pending" for item in records),
        },
        "failed_keys": [item["params"] for item in failed_controller],
        "controller": controller,
        "interpretation": "crossing 未完成前不得赋予相名",
    }

    write_json(observations_path, output_observations)
    write_json(phase_dir / "accepted_calibration_r1.json", calibration)
    write_json(phase_dir / "action_index.json", action_index)
    write_json(phase_dir / "r1_ingestion_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
