#!/usr/bin/env python3
"""把 R5 部分终态幂等写入 accepted-only 相图状态。"""

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
CAL_CELL = "nega-r5-a0250-b0500-L080"
FAIL_CELL = "nega-r5-a0100-b0500-L040"
FAIL_KEY = (-0.1, 0.5, 40)
FAIL_ACTION = "act-cd2b4353726834318d6b"
PRIOR_SUMMARIES = (
    "r1_ingestion_summary.json",
    "r2_ingestion_summary.json",
    "r3_partial_ingestion_summary.json",
    "r4_ingestion_summary.json",
)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
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


def finite_pair(block: dict[str, Any], label: str) -> tuple[float, float]:
    pair = block.get("value"), block.get("error")
    if not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in pair):
        raise ValueError(f"{label} 含非有限数")
    if float(pair[1]) < 0:
        raise ValueError(f"{label} error 为负")
    return float(pair[0]), float(pair[1])


def action_id(spec: dict[str, Any]) -> str:
    encoded = json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return "act-" + hashlib.sha256(encoded).hexdigest()[:20]


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
    action_index_path = phase_dir / "action_index.json"
    validation_summary_path = fetch_dir / "validation" / "summary.json"
    handoff_path = fetch_dir / "partial_handoff_summary.json"
    audit_path = phase_dir / "r5_partial_ingestion_audit.json"
    summary_path = phase_dir / "r5_partial_ingestion_summary.json"
    required = (
        run_spec_path, observations_path, state_path, action_index_path,
        validation_summary_path, handoff_path,
    )
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)

    run_spec = load(run_spec_path)
    cells = run_spec.get("cells", [])
    cells_by_id = {cell.get("cell_id"): cell for cell in cells}
    if len(cells) != 10 or len(cells_by_id) != 10 or not {CAL_CELL, FAIL_CELL}.issubset(cells_by_id):
        raise ValueError("R5 run spec 必须包含 10 个唯一 cell 及两个终态 cell")
    cal_cell, fail_cell = cells_by_id[CAL_CELL], cells_by_id[FAIL_CELL]
    if (
        key(cal_cell["params"]) != (-0.25, 0.5, 80)
        or int(cal_cell.get("budget", -1)) != 64
        or cal_cell.get("controller_action_id") is not None
        or cal_cell.get("calibration_only") is not True
        or key(fail_cell["params"]) != FAIL_KEY
        or int(fail_cell.get("budget", -1)) != 32
        or fail_cell.get("controller_action_id") != FAIL_ACTION
        or fail_cell.get("calibration_only") is not False
    ):
        raise ValueError("R5 两个终态 cell 的身份不匹配")

    validation_summary = load(validation_summary_path)
    rows = validation_summary.get("rows", [])
    rows_by_id = {row.get("cell_id"): row for row in rows}
    if (
        validation_summary.get("schema_version") != 1
        or validation_summary.get("status") != "partial_fail"
        or validation_summary.get("cell_count") != 2
        or validation_summary.get("counts") != {"pass": 1, "fail": 1}
        or set(rows_by_id) != {CAL_CELL, FAIL_CELL}
    ):
        raise ValueError("R5 validation summary 的 schema 或计数不匹配")
    handoff = load(handoff_path)
    handoff_records = {key(record["params"]): record for record in handoff.get("records", [])}
    if (
        handoff.get("schema_version") != 1
        or handoff.get("status") != "partial_terminal"
        or handoff.get("counts") != {
            "materialized": 2, "validator_pass": 1, "validator_fail": 1, "unmaterialized": 8,
        }
        or handoff.get("controller_written") is not False
        or handoff.get("retry_started") is not False
        or set(handoff_records) != {(-0.25, 0.5, 80), FAIL_KEY}
        or handoff.get("validation_summary", {}).get("sha256") != sha256(validation_summary_path)
        or handoff.get("run_spec", {}).get("sha256") != sha256(run_spec_path)
    ):
        raise ValueError("R5 partial handoff 的 schema、计数或输入哈希不匹配")

    evidence: dict[str, dict[str, Any]] = {}
    for cell, expected_status in ((cal_cell, "pass"), (fail_cell, "fail")):
        cell_id = cell["cell_id"]
        run_dir = fetch_dir / "cells" / cell_id
        manifest_path = run_dir / "manifest.json"
        validation_path = fetch_dir / "validation" / f"{cell_id}.json"
        receipt_path = fetch_dir / "receipts" / f"{cell_id}.json"
        for path in (manifest_path, validation_path, receipt_path):
            if not path.is_file():
                raise FileNotFoundError(path)
        manifest, validation, receipt = load(manifest_path), load(validation_path), load(receipt_path)
        row = rows_by_id[cell_id]
        if (
            validation.get("cell_id") != cell_id
            or validation.get("status") != expected_status
            or Path(validation.get("run_dir", "")).resolve() != run_dir.resolve()
            or Path(validation.get("run_spec", "")).resolve() != run_spec_path
            or row.get("validator_status") != expected_status
            or row.get("exit_code") != (0 if expected_status == "pass" else 1)
            or Path(row.get("output", "")).resolve() != validation_path
            or row.get("sha256") != sha256(validation_path)
        ):
            raise ValueError(f"{cell_id} 的 validator summary 或身份不匹配")
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
            or Path(receipt.get("destination", "")).resolve() != run_dir.resolve()
            or receipt.get("manifest_sha256") != sha256(manifest_path)
        ):
            raise ValueError(f"{cell_id} 的回传 receipt 无效")
        for name in ("manifest_sha256", "checksums_sha256", "preview_sha256"):
            value = receipt.get(name)
            if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
                raise ValueError(f"{cell_id} 的 {name} 无效")
        accepted = expected_status == "pass"
        if (
            manifest.get("cell_id") != cell_id
            or key(manifest.get("params", {})) != key(cell["params"])
            or int(manifest.get("settings", {}).get("budget", -1)) != int(cell["budget"])
            or manifest.get("status") != ("success" if accepted else "failed")
            or manifest.get("accepted") is not accepted
        ):
            raise ValueError(f"{cell_id} 的 manifest 终态不匹配")
        candidate = handoff_records[key(cell["params"])]
        if (
            candidate.get("status") != ("success" if accepted else "failed")
            or candidate.get("artifact") != relative(manifest_path if accepted else validation_path)
            or candidate.get("validation", {}).get("sha256") != sha256(validation_path)
            or candidate.get("checksum_receipt", {}).get("sha256") != sha256(receipt_path)
        ):
            raise ValueError(f"{cell_id} 的 handoff record 不匹配底层证据")
        evidence[cell_id] = {
            "cell": cell, "manifest": manifest, "manifest_path": manifest_path,
            "validation": validation, "validation_path": validation_path,
            "receipt": receipt, "receipt_path": receipt_path, "handoff": candidate,
        }

    observations = load(observations_path)
    current_observations_sha256 = sha256(observations_path)
    records = observations.get("records", [])
    indexed = {key(record["params"]): record for record in records}
    if len(records) != 16 or len(indexed) != 16:
        raise ValueError("controller observations 必须包含 16 个唯一参数键")
    current = indexed[FAIL_KEY]
    fail_validation = evidence[FAIL_CELL]["validation"]
    fail_validation_path = evidence[FAIL_CELL]["validation_path"]
    fail_manifest_path = evidence[FAIL_CELL]["manifest_path"]
    fail_receipt = evidence[FAIL_CELL]["receipt"]
    fail_receipt_path = evidence[FAIL_CELL]["receipt_path"]
    failed_candidate = {
        "params": {"alpha": -0.1, "beta": 0.5, "L": 40},
        "status": "failed",
        "budget": 32,
        "artifact": relative(fail_validation_path),
        "controller_action_id": FAIL_ACTION,
        "failure_evidence": {
            "validator_status": "fail",
            "validator_artifact": relative(fail_validation_path),
            "validator_sha256": sha256(fail_validation_path),
            "checks": fail_validation["checks"],
            "failures": fail_validation["failures"],
            "receipt": relative(fail_receipt_path),
            "receipt_sha256": sha256(fail_receipt_path),
            "manifest": relative(fail_manifest_path),
            "manifest_sha256": fail_receipt["manifest_sha256"],
            "checksums_sha256": fail_receipt["checksums_sha256"],
            "preview_sha256": fail_receipt["preview_sha256"],
            "diagnostics": evidence[FAIL_CELL]["handoff"]["failure_evidence"]["diagnostics"],
            "thresholds": evidence[FAIL_CELL]["handoff"]["failure_evidence"]["thresholds"],
        },
        "r5_provenance": {
            "run_spec": relative(run_spec_path),
            "run_spec_sha256": sha256(run_spec_path),
            "partial_handoff": relative(handoff_path),
            "partial_handoff_sha256": sha256(handoff_path),
        },
    }
    if current.get("status") == "pending":
        if (
            int(current.get("budget", -1)) != 32
            or not isinstance(current.get("receipt"), str)
            or not current.get("receipt")
            or not isinstance(current.get("artifact"), str)
            or not current.get("artifact")
        ):
            raise ValueError("R5 当前 pending observation 身份不完整")
        previous_pending = current
    elif current.get("status") == "failed" and current.get("artifact") == relative(fail_validation_path):
        previous_pending = current.get("r5_provenance", {}).get("previous_pending_observation")
        if not isinstance(previous_pending, dict):
            raise ValueError("R5 幂等重放缺少原 pending provenance")
    else:
        raise ValueError("R5 遇到不同终态，拒绝覆盖")
    failed_candidate["r5_provenance"]["previous_pending_observation"] = previous_pending
    failed_candidate["r5_provenance"]["r1_r2_r3_r4_evidence_preserved"] = True
    if "value" in failed_candidate or "error" in failed_candidate:
        raise ValueError("failed observation 不得含 value/error")

    state = load(state_path)
    actions = {action["action_id"]: action for action in state.get("actions", [])}
    expected_spec = {
        "kind": "phase-diagram-cell",
        "params": {"alpha": -0.1, "beta": 0.5, "L": 40},
        "budget": 32,
    }
    action = actions.get(FAIL_ACTION)
    if (
        len(actions) != 16 or not action or action.get("state") != "REGISTERED"
        or action.get("spec") != expected_spec or action_id(expected_spec) != FAIL_ACTION
    ):
        raise ValueError("R5 controller action 不处于原始 REGISTERED 状态")
    indexed[FAIL_KEY] = failed_candidate
    output_records = sorted(
        indexed.values(), key=lambda record: (
            record["params"]["beta"], record["params"]["alpha"], record["params"]["L"],
        ),
    )
    counts = {
        "success": sum(record.get("status") == "success" for record in output_records),
        "failed": sum(record.get("status") == "failed" for record in output_records),
        "pending": sum(record.get("status") == "pending" for record in output_records),
    }
    if counts != {"success": 10, "failed": 1, "pending": 5}:
        raise ValueError(f"R5 接入后的 controller 计数异常: {counts}")

    cal_evidence = evidence[CAL_CELL]
    cal_manifest = cal_evidence["manifest"]
    cal_receipt = cal_evidence["receipt"]
    value, error = finite_pair(
        cal_manifest["observables"]["dominant_structure_factor_ratio"], "R5 calibration observable",
    )
    q_value, q_error = finite_pair(
        cal_manifest["observables"]["structure_factor_peak_q_over_pi"], "R5 calibration q_peak",
    )
    calibration_candidate = {
        "params": {"alpha": -0.25, "beta": 0.5, "L": 80},
        "status": "success", "value": value, "error": error, "budget": 64,
        "artifact": relative(cal_evidence["manifest_path"]),
        "accepted_only": True, "calibration_only": True,
        "controller_action_id": None,
        "diagnostics": {
            "q_peak_over_pi": {
                **cal_manifest["observables"]["structure_factor_peak_q_over_pi"],
                "value": q_value, "error": q_error,
            }
        },
        "validation": {
            "status": "pass", "artifact": relative(cal_evidence["validation_path"]),
            "sha256": sha256(cal_evidence["validation_path"]),
        },
        "checksum_receipt": {
            "artifact": relative(cal_evidence["receipt_path"]),
            "sha256": sha256(cal_evidence["receipt_path"]),
            "manifest_sha256": cal_receipt["manifest_sha256"],
            "checksums_sha256": cal_receipt["checksums_sha256"],
            "preview_sha256": cal_receipt["preview_sha256"],
        },
        "provenance": cal_manifest["provenance"],
        "r5_partial_handoff": True,
    }
    cal_r1_path = phase_dir / "accepted_calibration_r1.json"
    cal_r3_path = phase_dir / "accepted_calibration_r3_partial.json"
    for path in (cal_r1_path, cal_r3_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    cal_r1, cal_r3 = load(cal_r1_path), load(cal_r3_path)
    if len(cal_r1.get("records", [])) != 3 or len(cal_r3.get("records", [])) != 1:
        raise ValueError("R1/R3 calibration 基线计数不是 3+1")
    calibration_records = cal_r1["records"] + cal_r3["records"] + [calibration_candidate]
    calibration_by_key = {key(record["params"]): record for record in calibration_records}
    if len(calibration_records) != 5 or len(calibration_by_key) != 5:
        raise ValueError("R5 接入后 calibration accepted 总数必须为 5 且参数唯一")
    aggregate_calibration = {
        "schema_version": 1,
        "purpose": "R1、R3、R5 的 L80 calibration-only accepted evidence；不进入 controller observations",
        "sources": [
            {"artifact": relative(cal_r1_path), "sha256": sha256(cal_r1_path)},
            {"artifact": relative(cal_r3_path), "sha256": sha256(cal_r3_path)},
            {"artifact": relative(handoff_path), "sha256": sha256(handoff_path)},
        ],
        "records": sorted(calibration_by_key.values(), key=lambda record: key(record["params"])),
    }
    r5_calibration_path = phase_dir / "accepted_calibration_r5_partial.json"
    aggregate_path = phase_dir / "accepted_calibration_through_r5.json"
    write_json(r5_calibration_path, {
        "schema_version": 1,
        "purpose": "R5 部分终态的 L80 calibration-only accepted evidence",
        "source_partial_handoff": relative(handoff_path),
        "records": [calibration_candidate],
    })
    write_json(aggregate_path, aggregate_calibration)
    write_json(observations_path, {"schema_version": 1, "records": output_records})

    action_index = load(action_index_path)
    if len(action_index.get("actions", [])) != 16:
        raise ValueError("action_index 必须含 16 个 action")
    for row in action_index["actions"]:
        if row.get("action_id") == FAIL_ACTION:
            row.update({
                "observation_status": "failed", "accepted": False,
                "artifact": failed_candidate["artifact"], "r5_partial_handoff": True,
            })
    write_json(action_index_path, action_index)

    prior_summary_evidence = []
    for name in PRIOR_SUMMARIES:
        path = phase_dir / name
        if not path.is_file():
            raise FileNotFoundError(path)
        prior_summary_evidence.append({"artifact": relative(path), "sha256": sha256(path)})
    if audit_path.is_file():
        pre_r5_observations_sha256 = load(audit_path).get("pre_r5_observations_sha256")
        if not isinstance(pre_r5_observations_sha256, str) or len(pre_r5_observations_sha256) != 64:
            raise ValueError("R5 audit 的 pre-R5 observations hash 无效")
    else:
        pre_r5_observations_sha256 = current_observations_sha256
    audit = {
        "schema_version": 1,
        "status": "pass",
        "pre_r5_observations_sha256": pre_r5_observations_sha256,
        "input_evidence": {
            "run_spec": {"artifact": relative(run_spec_path), "sha256": sha256(run_spec_path)},
            "validation_summary": {
                "artifact": relative(validation_summary_path), "sha256": sha256(validation_summary_path),
            },
            "partial_handoff": {"artifact": relative(handoff_path), "sha256": sha256(handoff_path)},
            "prior_ingestion_summaries": prior_summary_evidence,
        },
        "invariants": {
            "controller_counts": counts,
            "calibration_accepted_total": 5,
            "failed_has_no_value_error": True,
            "previous_pending_provenance_preserved": True,
            "r1_r2_r3_r4_evidence_preserved": True,
            "crossing_assigned": False,
            "phase_label_assigned": False,
        },
        "outputs": {
            "observations": relative(observations_path),
            "action_index": relative(action_index_path),
            "r5_calibration": relative(r5_calibration_path),
            "calibration_aggregate": relative(aggregate_path),
        },
    }
    write_json(audit_path, audit)

    report_path = args.controller_report.resolve() if args.controller_report else phase_dir / "report.json"
    report = load(report_path) if report_path.is_file() else None
    controller = {
        "status": report.get("status") if report else "NOT_EVALUATED",
        "reason": report.get("reason") if report else None,
        "report": relative(report_path) if report else None,
        "report_sha256": sha256(report_path) if report else None,
        "state": relative(state_path), "state_sha256": sha256(state_path),
        "phase_boundary_ready": bool(report and report.get("status") == "COMPLETE"),
        "crossing": "not_assigned", "phase_label": "not_assigned",
    }
    summary = {
        "schema_version": 1,
        "status": "blocked_by_validation_failure",
        "counts": {
            "controller_success_total": 10, "controller_failed_total": 1,
            "controller_pending_total": 5, "calibration_accepted_total": 5,
            "r5_materialized": 2, "r5_unmaterialized": 8,
        },
        "accepted_calibration_key": {"alpha": -0.25, "beta": 0.5, "L": 80},
        "failed_controller_key": {"alpha": -0.1, "beta": 0.5, "L": 40},
        "failed_evidence": failed_candidate["failure_evidence"],
        "audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
        "observations": {"artifact": relative(observations_path), "sha256": sha256(observations_path)},
        "action_index": {"artifact": relative(action_index_path), "sha256": sha256(action_index_path)},
        "calibration_aggregate": {"artifact": relative(aggregate_path), "sha256": sha256(aggregate_path)},
        "controller": controller,
        "interpretation": "R5 仅接入严格终态；失败项无 value/error，其余 action 保持 pending，不赋 crossing 或相名",
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
