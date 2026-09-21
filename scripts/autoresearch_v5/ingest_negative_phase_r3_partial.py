#!/usr/bin/env python3
"""把 R3 部分终态证据写入 accepted-only 相图状态。"""

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
EXPECTED_FETCHED = {
    "nega-r3-a0350-b0500-L080": ((-0.35, 0.5, 80), "pass", None, True),
    "nega-r3-a0250-b0500-L040": (
        (-0.25, 0.5, 40), "pass", "act-2d26dfe7cf872627ea81", False,
    ),
    "nega-r3-a0250-b0500-L060": (
        (-0.25, 0.5, 60), "fail", "act-bd120db6bdbc305ddf42", False,
    ),
}
EXPECTED_PENDING_ACTIONS = {
    "act-cd2b4353726834318d6b",
    "act-6a4963c3064243f17ed8",
    "act-fffdf93a9cae183cb1c1",
    "act-7016420e7cbf8fc354b7",
    "act-4503b7acb169c6a5092f",
    "act-3d1ab066156655e22ec8",
}


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


def finite_pair(block: dict[str, Any], label: str) -> tuple[float, float]:
    pair = block.get("value"), block.get("error")
    if not all(isinstance(item, (int, float)) and math.isfinite(float(item)) for item in pair):
        raise ValueError(f"{label} 含非有限数")
    if float(pair[1]) < 0:
        raise ValueError(f"{label} error 为负")
    return float(pair[0]), float(pair[1])


def action_id(spec: dict[str, Any]) -> str:
    encoded = json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "act-" + hashlib.sha256(encoded).hexdigest()[:20]


def accepted_record(
    cell: dict[str, Any], manifest_path: Path, validation_path: Path,
    receipt_path: Path, manifest: dict[str, Any], receipt: dict[str, Any],
) -> dict[str, Any]:
    value, error = finite_pair(
        manifest["observables"]["dominant_structure_factor_ratio"], cell["cell_id"],
    )
    q_value, q_error = finite_pair(
        manifest["observables"]["structure_factor_peak_q_over_pi"], f"{cell['cell_id']} q_peak",
    )
    return {
        "params": {name: cell["params"][name] for name in ("alpha", "beta", "L")},
        "status": "success",
        "value": value,
        "error": error,
        "budget": int(cell["budget"]),
        "artifact": relative(manifest_path),
        "accepted_only": True,
        "controller_action_id": cell.get("controller_action_id"),
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
        "r3_partial_handoff": True,
    }


def failed_record(
    cell: dict[str, Any], manifest_path: Path, validation_path: Path,
    receipt_path: Path, validation: dict[str, Any], receipt: dict[str, Any],
) -> dict[str, Any]:
    return {
        "params": {name: cell["params"][name] for name in ("alpha", "beta", "L")},
        "status": "failed",
        "budget": int(cell["budget"]),
        "artifact": relative(validation_path),
        "controller_action_id": cell.get("controller_action_id"),
        "failure_evidence": {
            "validator_status": "fail",
            "validator_artifact": relative(validation_path),
            "validator_sha256": sha256(validation_path),
            "checks": validation["checks"],
            "failures": validation["failures"],
            "receipt": relative(receipt_path),
            "receipt_sha256": sha256(receipt_path),
            "manifest": relative(manifest_path),
            "manifest_sha256": receipt["manifest_sha256"],
            "checksums_sha256": receipt["checksums_sha256"],
            "preview_sha256": receipt["preview_sha256"],
        },
        "r3_partial_handoff": True,
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
    audit_path = fetch_dir / "audit" / "remote_checksum_20260810_1534.txt"

    for path in (run_spec_path, observations_path, state_path, audit_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    run_spec = load(run_spec_path)
    cells = run_spec.get("cells", [])
    if len(cells) != 13 or len({item.get("cell_id") for item in cells}) != 13:
        raise ValueError("R3 run spec 必须包含 13 个唯一 cell")
    cells_by_id = {item["cell_id"]: item for item in cells}
    if not set(EXPECTED_FETCHED).issubset(cells_by_id):
        raise ValueError("R3 run spec 缺少已回传 cell")
    fetched_dirs = {path.name for path in (fetch_dir / "cells").iterdir() if path.is_dir()}
    validation_ids = {
        path.stem for path in (fetch_dir / "validation").glob("*.json") if path.name != "summary.json"
    }
    receipt_ids = {path.stem for path in (fetch_dir / "receipts").glob("*.json")}
    if fetched_dirs != set(EXPECTED_FETCHED) or validation_ids != fetched_dirs or receipt_ids != fetched_dirs:
        raise ValueError("R3 回传、validator、receipt 集合必须严格等于三个终态 cell")

    observations = load(observations_path)
    records = observations.get("records", [])
    indexed = {key(item["params"]): item for item in records}
    if len(records) != 16 or len(indexed) != 16:
        raise ValueError("controller observations 必须包含 16 个唯一参数键")
    state = load(state_path)
    actions = {item["action_id"]: item for item in state.get("actions", [])}
    if len(actions) != 16:
        raise ValueError("controller state 必须包含 16 个唯一 action")

    candidates: dict[tuple[float, float, int], dict[str, Any]] = {}
    calibration_records: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    for cell_id, (expected_key, expected_status, expected_action, calibration_only) in EXPECTED_FETCHED.items():
        cell = cells_by_id[cell_id]
        if (
            key(cell.get("params", {})) != expected_key
            or cell.get("controller_action_id") != expected_action
            or bool(cell.get("calibration_only")) is not calibration_only
            or int(cell.get("budget", -1)) != (64 if expected_key[2] == 80 else 32)
        ):
            raise ValueError(f"{cell_id} 的 spec 身份不匹配")
        manifest_path = fetch_dir / "cells" / cell_id / "manifest.json"
        validation_path = fetch_dir / "validation" / f"{cell_id}.json"
        receipt_path = fetch_dir / "receipts" / f"{cell_id}.json"
        manifest, validation, receipt = load(manifest_path), load(validation_path), load(receipt_path)
        if (
            validation.get("cell_id") != cell_id
            or validation.get("status") != expected_status
            or Path(validation.get("run_dir", "")).resolve() != manifest_path.parent.resolve()
            or Path(validation.get("run_spec", "")).resolve() != run_spec_path
        ):
            raise ValueError(f"{cell_id} 的 validator 身份或状态不匹配")
        checks = validation.get("checks", {})
        if expected_status == "pass":
            if not checks or not all(value is True for value in checks.values()) or validation.get("failures"):
                raise ValueError(f"{cell_id} 的 pass validator 含失败门")
        elif (
            checks.get("terminal_acceptance") is not False
            or any(value is not True for name, value in checks.items() if name != "terminal_acceptance")
            or not validation.get("failures")
        ):
            raise ValueError(f"{cell_id} 的 fail validator 证据不完整")
        if (
            receipt.get("status") != "pass"
            or receipt.get("cell_id") != cell_id
            or receipt.get("non_clobbering") is not True
            or Path(receipt.get("destination", "")).resolve() != manifest_path.parent.resolve()
        ):
            raise ValueError(f"{cell_id} 的回传 receipt 无效")
        for name in ("manifest_sha256", "checksums_sha256", "preview_sha256"):
            value = receipt.get(name)
            if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ValueError(f"{cell_id} 的 {name} 无效")
        if receipt["manifest_sha256"] != sha256(manifest_path):
            raise ValueError(f"{cell_id} 的 manifest checksum 不一致")
        if (
            manifest.get("cell_id") != cell_id
            or key(manifest.get("params", {})) != expected_key
            or int(manifest.get("settings", {}).get("budget", -1)) != int(cell["budget"])
        ):
            raise ValueError(f"{cell_id} 的 manifest 身份不匹配")
        accepted = expected_status == "pass"
        if manifest.get("status") != ("success" if accepted else "failed") or manifest.get("accepted") is not accepted:
            raise ValueError(f"{cell_id} 的 manifest 终态不匹配")
        if not calibration_only:
            expected_spec = {
                "kind": "phase-diagram-cell",
                "params": {name: cell["params"][name] for name in ("alpha", "beta", "L")},
                "budget": int(cell["budget"]),
            }
            action = actions.get(expected_action)
            if (
                not action
                or action.get("state") != "REGISTERED"
                or action.get("spec") != expected_spec
                or action_id(expected_spec) != expected_action
            ):
                raise ValueError(f"{cell_id} 的 controller action 不匹配")
        record = (
            accepted_record(cell, manifest_path, validation_path, receipt_path, manifest, receipt)
            if accepted else
            failed_record(cell, manifest_path, validation_path, receipt_path, validation, receipt)
        )
        if calibration_only:
            calibration_records.append(record | {"calibration_only": True})
        else:
            current = indexed[expected_key]
            expected_artifact = record["artifact"]
            if current.get("status") == "pending":
                if (
                    int(current.get("budget", -1)) != 32
                    or not isinstance(current.get("receipt"), str)
                    or not current.get("receipt")
                    or not isinstance(current.get("artifact"), str)
                    or not current.get("artifact")
                ):
                    raise ValueError(f"{cell_id} 的 pending observation 身份不匹配")
            elif current.get("status") != record["status"] or current.get("artifact") != expected_artifact:
                raise ValueError(f"{cell_id} 已有不同终态，拒绝覆盖")
            candidates[expected_key] = record
        validation_rows.append({
            "cell_id": cell_id,
            "validator_status": expected_status,
            "exit_code": 0 if expected_status == "pass" else 1,
            "output": str(validation_path),
            "sha256": sha256(validation_path),
        })

    for expected_action in EXPECTED_PENDING_ACTIONS:
        action = actions.get(expected_action)
        if not action:
            raise ValueError(f"缺少未运行 action: {expected_action}")
        current = indexed[key(action["spec"]["params"])]
        if (
            current.get("status") != "pending"
            or int(current.get("budget", -1)) != int(action["spec"]["budget"])
            or not isinstance(current.get("receipt"), str)
            or not current.get("receipt")
        ):
            raise ValueError(f"未运行 action 不再是 pending: {expected_action}")
    indexed.update(candidates)
    output_records = sorted(
        indexed.values(), key=lambda item: (item["params"]["beta"], item["params"]["alpha"], item["params"]["L"]),
    )
    if sum(item["status"] == "success" for item in output_records) != 9:
        raise ValueError("R3 接入后 controller success 总数必须为 9")
    if sum(item["status"] == "failed" for item in output_records) != 1:
        raise ValueError("R3 接入后 controller failed 总数必须为 1")
    if sum(item["status"] == "pending" for item in output_records) != 6:
        raise ValueError("R3 接入后 controller pending 总数必须为 6")
    failed = next(item for item in output_records if item["status"] == "failed")
    if "value" in failed or "error" in failed:
        raise ValueError("failed observation 不得含 value/error")

    validation_summary = {
        "schema_version": 1,
        "status": "fail",
        "cell_count": 3,
        "counts": {"pass": 2, "fail": 1},
        "rows": sorted(validation_rows, key=lambda item: item["cell_id"]),
    }
    validation_summary_path = fetch_dir / "validation" / "summary.json"
    write_json(validation_summary_path, validation_summary)
    handoff_summary = {
        "schema_version": 1,
        "status": "partial_terminal",
        "run_spec": {"artifact": relative(run_spec_path), "sha256": sha256(run_spec_path)},
        "remote_checksum_audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
        "validation_summary": {
            "artifact": relative(validation_summary_path), "sha256": sha256(validation_summary_path),
        },
        "fetched_cells": sorted(EXPECTED_FETCHED),
        "unrun_cells": sorted(set(cells_by_id) - set(EXPECTED_FETCHED)),
        "accepted_gate": {
            "controller_accepted": ["nega-r3-a0250-b0500-L040"],
            "calibration_accepted": ["nega-r3-a0350-b0500-L080"],
            "controller_failed": ["nega-r3-a0250-b0500-L060"],
            "unrun_unchanged": True,
        },
    }
    handoff_summary_path = fetch_dir / "handoff_summary.json"
    write_json(handoff_summary_path, handoff_summary)

    output_observations = {"schema_version": 1, "records": output_records}
    write_json(observations_path, output_observations)
    calibration_path = phase_dir / "accepted_calibration_r3_partial.json"
    calibration = {
        "schema_version": 1,
        "purpose": "R3 部分终态的 L80 calibration-only accepted evidence；不进入 controller observations",
        "source_validation_summary": relative(validation_summary_path),
        "records": sorted(calibration_records, key=lambda item: key(item["params"])),
    }
    write_json(calibration_path, calibration)

    action_index_path = phase_dir / "action_index.json"
    action_index = load(action_index_path)
    if len(action_index.get("actions", [])) != 16:
        raise ValueError("action_index 必须含 16 个 action")
    status_by_key = {key(item["params"]): item for item in output_records}
    for row in action_index["actions"]:
        record = status_by_key[key(row["params"])]
        row.update({
            "observation_status": record["status"],
            "accepted": record["status"] == "success",
            "artifact": record.get("artifact"),
        })
        if record.get("r3_partial_handoff"):
            row["r3_partial_handoff"] = True
    write_json(action_index_path, action_index)

    report_path = args.controller_report.resolve() if args.controller_report else phase_dir / "report.json"
    report = load(report_path) if report_path.is_file() else None
    controller = {
        "status": report.get("status") if report else "NOT_EVALUATED",
        "reason": report.get("reason") if report else None,
        "report": relative(report_path) if report else None,
        "report_sha256": sha256(report_path) if report else None,
        "state": relative(state_path),
        "state_sha256": sha256(state_path),
        "phase_boundary_ready": bool(report and report.get("status") == "COMPLETE"),
        "phase_label": "not_assigned",
    }
    summary = {
        "schema_version": 1,
        "status": "blocked_by_validation_failure",
        "source": {
            "run_spec": relative(run_spec_path),
            "run_spec_sha256": sha256(run_spec_path),
            "handoff_summary": relative(handoff_summary_path),
            "handoff_summary_sha256": sha256(handoff_summary_path),
        },
        "counts": {
            "fetched_terminal": 3,
            "validator_pass": 2,
            "validator_fail": 1,
            "controller_success_total": 9,
            "controller_failed_total": 1,
            "controller_pending_total": 6,
            "calibration_accepted_r3": 1,
            "r3_unrun_total": 10,
            "r3_unrun_controller_pending": 6,
        },
        "accepted_controller_keys": [{"alpha": -0.25, "beta": 0.5, "L": 40}],
        "accepted_calibration_keys": [{"alpha": -0.35, "beta": 0.5, "L": 80}],
        "failed_controller_keys": [{"alpha": -0.25, "beta": 0.5, "L": 60}],
        "failed_evidence": failed["failure_evidence"],
        "calibration": {"artifact": relative(calibration_path), "sha256": sha256(calibration_path)},
        "action_index": {"artifact": relative(action_index_path), "sha256": sha256(action_index_path)},
        "controller": controller,
        "interpretation": "仅接入严格终态证据；失败项不含 value/error，未运行项保持 pending，不赋相名",
    }
    write_json(phase_dir / "r3_partial_ingestion_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
