#!/usr/bin/env python3
"""把 R7 单点失败证据幂等接入 accepted-only 相图状态。"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CELL_ID = "nega-r7-a0100-b0500-L060"
EXPECTED_KEY = (-0.1, 0.5, 60)
EXPECTED_ACTION = "act-6a4963c3064243f17ed8"
REMAINING_PENDING_ACTIONS = {
    "act-fffdf93a9cae183cb1c1",
    "act-7016420e7cbf8fc354b7",
    "act-4503b7acb169c6a5092f",
    "act-3d1ab066156655e22ec8",
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


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(name in {"value", "error"} or contains_forbidden_key(item) for name, item in value.items())
    if isinstance(value, list):
        return any(contains_forbidden_key(item) for item in value)
    return False


def verify_checksums(directory: Path) -> dict[str, str]:
    checksum_path = directory / "checksums.sha256"
    if not checksum_path.is_file():
        raise FileNotFoundError(checksum_path)
    verified: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise ValueError(f"非法 checksum 行: {line}")
        digest, name = parts[0], parts[1].strip().lstrip("*")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"非法 checksum: {line}")
        target = (directory / name).resolve()
        target.relative_to(directory.resolve())
        if not target.is_file() or sha256(target) != digest:
            raise ValueError(f"本地 checksum 失败: {directory.name}/{name}")
        verified[name] = digest
    if not verified:
        raise ValueError(f"空 checksum: {checksum_path}")
    return verified


def action_id(spec: dict[str, Any]) -> str:
    return "act-" + canonical_sha256(spec)[:20]


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
    run_dir = fetch_dir / "cells" / CELL_ID
    manifest_path = run_dir / "manifest.json"
    preview_path = fetch_dir / "previews" / f"{CELL_ID}.json"
    receipt_path = fetch_dir / "receipts" / f"{CELL_ID}.json"
    validation_path = fetch_dir / "validation" / f"{CELL_ID}.json"
    validation_summary_path = fetch_dir / "validation" / "summary.json"
    handoff_summary_path = fetch_dir / "partial_handoff_summary.json"
    handoff_audit_path = fetch_dir / "handoff_audit.json"
    observations_path = phase_dir / "observations.json"
    state_path = phase_dir / "state.json"
    action_index_path = phase_dir / "action_index.json"
    r6_summary_path = phase_dir / "r6_ingestion_summary.json"
    r6_audit_path = phase_dir / "r6_ingestion_audit.json"
    calibration_path = phase_dir / "accepted_calibration_through_r5.json"
    audit_path = phase_dir / "r7_failure_ingestion_audit.json"
    summary_path = phase_dir / "r7_failure_ingestion_summary.json"
    required = (
        run_spec_path, manifest_path, preview_path, receipt_path, validation_path,
        validation_summary_path, handoff_summary_path, handoff_audit_path,
        observations_path, state_path, action_index_path, r6_summary_path,
        r6_audit_path, calibration_path,
    )
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)

    run_spec = load(run_spec_path)
    cells = run_spec.get("cells", [])
    cells_by_id = {cell.get("cell_id"): cell for cell in cells}
    if len(cells) != 8 or len(cells_by_id) != 8 or CELL_ID not in cells_by_id:
        raise ValueError("R7 run spec 必须含 8 个唯一 cell")
    cell = cells_by_id[CELL_ID]
    provenance = run_spec.get("provenance", {})
    if (
        key(cell.get("params", {})) != EXPECTED_KEY
        or int(cell.get("budget", -1)) != 32
        or cell.get("controller_action_id") != EXPECTED_ACTION
        or cell.get("calibration_only") is not False
        or provenance.get("thresholds_relaxed") is not False
        or provenance.get("r6_ingestion_summary_sha256") != sha256(r6_summary_path)
    ):
        raise ValueError("R7 cell 身份、门槛或 R6 provenance 不匹配")

    validation_summary = load(validation_summary_path)
    rows = validation_summary.get("rows", [])
    if (
        validation_summary.get("schema_version") != 1
        or validation_summary.get("status") != "fail"
        or validation_summary.get("cell_count") != 1
        or validation_summary.get("counts") != {"pass": 0, "fail": 1}
        or len(rows) != 1
        or rows[0].get("cell_id") != CELL_ID
        or rows[0].get("validator_status") != "fail"
        or rows[0].get("exit_code") != 1
        or Path(rows[0].get("output", "")).resolve() != validation_path
        or rows[0].get("sha256") != sha256(validation_path)
    ):
        raise ValueError("R7 validation summary 的 schema、计数或证据不匹配")
    handoff_summary = load(handoff_summary_path)
    handoff_audit = load(handoff_audit_path)
    existing_ingestion_audit = load(audit_path) if audit_path.is_file() else None
    baseline_observations_sha256 = (
        existing_ingestion_audit.get("pre_r7_observations_sha256") or sha256(observations_path)
        if existing_ingestion_audit else sha256(observations_path)
    )
    baseline_action_index_sha256 = (
        existing_ingestion_audit.get("pre_r7_action_index_sha256")
        or handoff_audit.get("invariants", {}).get("action_index_unchanged_sha256")
        if existing_ingestion_audit else handoff_audit.get("invariants", {}).get("action_index_unchanged_sha256")
    )
    if (
        handoff_summary.get("schema_version") != 1
        or handoff_summary.get("status") != "blocked_by_validation_failure"
        or handoff_summary.get("counts") != {
            "planned": 8, "materialized": 1, "validator_pass": 0,
            "validator_fail": 1, "unmaterialized": 7,
        }
        or handoff_summary.get("controller_written") is not False
        or handoff_summary.get("retry_started") is not False
        or handoff_summary.get("validation_summary", {}).get("sha256") != sha256(validation_summary_path)
        or handoff_summary.get("handoff_audit", {}).get("sha256") != sha256(handoff_audit_path)
        or handoff_summary.get("run_spec", {}).get("sha256") != sha256(run_spec_path)
        or handoff_audit.get("schema_version") != 1
        or handoff_audit.get("status") != "blocked_by_validation_failure"
        or handoff_audit.get("cell_id") != CELL_ID
        or handoff_audit.get("invariants", {}).get("failure_record_has_value_error") is not False
        or handoff_audit.get("invariants", {}).get("accepted_only_eligible") is not False
        or handoff_audit.get("invariants", {}).get("ingest_started") is not False
        or handoff_audit.get("invariants", {}).get("retry_started") is not False
        or handoff_audit.get("invariants", {}).get("controller_observations_unchanged_sha256") != baseline_observations_sha256
        or handoff_audit.get("invariants", {}).get("action_index_unchanged_sha256") != baseline_action_index_sha256
        or provenance.get("observations_sha256") != baseline_observations_sha256
    ):
        raise ValueError("R7 partial handoff 或 handoff audit 不匹配")
    if handoff_summary.get("failure_record") != handoff_audit.get("failure_record"):
        raise ValueError("R7 summary 与 audit 的 failure record 不一致")

    preview, receipt, manifest, validation = (
        load(preview_path), load(receipt_path), load(manifest_path), load(validation_path),
    )
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
        raise ValueError("R7 preview、receipt 或 checksum 绑定失败")
    for name in ("preview_sha256", "manifest_sha256", "checksums_sha256"):
        digest = receipt.get(name)
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError(f"R7 receipt {name} 无效")
    parent_hashes = verify_checksums(run_dir)
    child_hashes = {
        mode: verify_checksums(run_dir / f"start_{mode}") for mode in ("center", "ferro_j2")
    }
    files = [path for path in run_dir.rglob("*") if path.is_file()]
    if (
        len(files) != int(preview.get("file_count", -1))
        or sum(path.stat().st_size for path in files) != int(preview.get("total_bytes", -1))
        or handoff_audit.get("local_checksum", {}).get("parent") != {
            "status": "pass", "entries": len(parent_hashes),
        }
        or handoff_audit.get("local_checksum", {}).get("children") != {
            mode: {"status": "pass", "entries": len(entries)} for mode, entries in child_hashes.items()
        }
    ):
        raise ValueError("R7 本地文件统计或 checksum audit 不一致")
    expected_checks = {
        "unique_run_spec_cell": True, "terminal_acceptance": False,
        "negative_alpha_range": True, "beta_range": True,
        "parent_checksums": True, "children": True,
    }
    if (
        validation.get("status") != "fail"
        or validation.get("cell_id") != CELL_ID
        or validation.get("checks") != expected_checks
        or not validation.get("failures")
        or Path(validation.get("run_dir", "")).resolve() != run_dir
        or Path(validation.get("run_spec", "")).resolve() != run_spec_path
        or manifest.get("cell_id") != CELL_ID
        or key(manifest.get("params", {})) != EXPECTED_KEY
        or manifest.get("status") != "failed"
        or manifest.get("accepted") is not False
        or int(manifest.get("settings", {}).get("budget", -1)) != 32
    ):
        raise ValueError("R7 validator 或 manifest 终态不匹配")
    if (
        handoff_audit.get("validator", {}).get("sha256") != sha256(validation_path)
        or handoff_audit.get("non_clobbering_fetch", {}).get("sha256") != sha256(receipt_path)
        or handoff_summary["failure_record"].get("artifact") != relative(validation_path)
        or handoff_summary["failure_record"].get("failure_evidence", {}).get("manifest_sha256") != sha256(manifest_path)
        or handoff_summary["failure_record"].get("failure_evidence", {}).get("checksum_receipt_sha256") != sha256(receipt_path)
    ):
        raise ValueError("R7 failure record 未绑定 validator、receipt 或 manifest")

    r6_summary, r6_audit = load(r6_summary_path), load(r6_audit_path)
    if (
        r6_summary.get("schema_version") != 1
        or r6_summary.get("status") != "accepted_with_initial_state_sensitivity"
        or r6_summary.get("counts") != {
            "validator_pass": 1, "controller_success_total": 11,
            "controller_failed_total": 0, "controller_pending_total": 5,
            "calibration_accepted_total": 5,
        }
        or r6_summary.get("ingestion_audit", {}).get("sha256") != sha256(r6_audit_path)
        or r6_audit.get("invariants", {}).get("controller_counts") != {
            "success": 11, "failed": 0, "pending": 5,
        }
        or r6_audit.get("invariants", {}).get("calibration_accepted_total") != 5
        or r6_audit.get("invariants", {}).get("r5_failure_provenance_preserved") is not True
    ):
        raise ValueError("R6 summary/audit provenance 基线不匹配")
    calibration = load(calibration_path)
    if len(calibration.get("records", [])) != 5 or len({key(row["params"]) for row in calibration["records"]}) != 5:
        raise ValueError("calibration accepted 基线不是 5 个唯一点")

    observations = load(observations_path)
    records = observations.get("records", [])
    indexed = {key(record["params"]): record for record in records}
    if len(records) != 16 or len(indexed) != 16 or EXPECTED_KEY not in indexed:
        raise ValueError("controller observations 必须含 16 个唯一参数键")
    r6_key = (-0.1, 0.5, 40)
    r6_record = indexed.get(r6_key)
    if (
        not r6_record
        or r6_record.get("status") != "success"
        or int(r6_record.get("budget", -1)) != 64
        or r6_record.get("accepted_only") is not True
        or r6_record.get("controller_action_id") != "act-cd2b4353726834318d6b"
    ):
        raise ValueError("R6 accepted observation 不存在或身份不匹配")
    r6_artifact = ROOT / str(r6_record.get("artifact", ""))
    r6_validation = ROOT / str(r6_record.get("validation", {}).get("artifact", ""))
    r6_receipt = ROOT / str(r6_record.get("checksum_receipt", {}).get("artifact", ""))
    for path in (r6_artifact, r6_validation, r6_receipt):
        if not path.is_file():
            raise FileNotFoundError(path)
    if (
        r6_record.get("validation", {}).get("sha256") != sha256(r6_validation)
        or r6_record.get("checksum_receipt", {}).get("sha256") != sha256(r6_receipt)
        or r6_summary.get("accepted_key") != {"alpha": -0.1, "beta": 0.5, "L": 40}
    ):
        raise ValueError("R6 accepted observation 的 provenance 不完整")

    current = indexed[EXPECTED_KEY]
    target_artifact = relative(validation_path)
    if current.get("status") == "pending":
        if (
            int(current.get("budget", -1)) != 32
            or not isinstance(current.get("receipt"), str)
            or not current.get("receipt")
            or not isinstance(current.get("artifact"), str)
            or not current.get("artifact")
        ):
            raise ValueError("R7 原 pending observation 身份不完整")
        previous_pending = current
    elif current.get("status") == "failed" and current.get("artifact") == target_artifact:
        previous_pending = current.get("r7_provenance", {}).get("previous_pending_observation")
        if not isinstance(previous_pending, dict):
            raise ValueError("R7 幂等重放缺少原 pending provenance")
    else:
        raise ValueError("R7 遇到不同终态，拒绝覆盖")

    failure_record = copy.deepcopy(handoff_summary["failure_record"])
    failure_record.pop("controller_written", None)
    failure_record["accepted_only_eligible"] = False
    failure_record["r7_provenance"] = {
        "previous_pending_observation": previous_pending,
        "run_spec": {"artifact": relative(run_spec_path), "sha256": sha256(run_spec_path)},
        "validation_summary": {
            "artifact": relative(validation_summary_path), "sha256": sha256(validation_summary_path),
        },
        "partial_handoff_summary": {
            "artifact": relative(handoff_summary_path), "sha256": sha256(handoff_summary_path),
        },
        "handoff_audit": {"artifact": relative(handoff_audit_path), "sha256": sha256(handoff_audit_path)},
        "r6": {
            "ingestion_summary": {"artifact": relative(r6_summary_path), "sha256": sha256(r6_summary_path)},
            "ingestion_audit": {"artifact": relative(r6_audit_path), "sha256": sha256(r6_audit_path)},
            "accepted_observation_canonical_sha256": canonical_sha256(r6_record),
            "accepted_artifact": {"artifact": relative(r6_artifact), "sha256": sha256(r6_artifact)},
            "validation": {"artifact": relative(r6_validation), "sha256": sha256(r6_validation)},
            "checksum_receipt": {"artifact": relative(r6_receipt), "sha256": sha256(r6_receipt)},
            "r5_failure_provenance_preserved": r6_record.get("r5_failure_provenance", {}).get("preserved") is True,
        },
    }
    if contains_forbidden_key(failure_record):
        raise ValueError("R7 failed observation 不得含 value/error 字段")

    state = load(state_path)
    actions = {action["action_id"]: action for action in state.get("actions", [])}
    expected_spec = {
        "kind": "phase-diagram-cell",
        "params": {"alpha": -0.1, "beta": 0.5, "L": 60},
        "budget": 32,
    }
    action = actions.get(EXPECTED_ACTION)
    if (
        len(actions) != 16 or not action or action.get("state") != "REGISTERED"
        or action.get("spec") != expected_spec or action_id(expected_spec) != EXPECTED_ACTION
    ):
        raise ValueError("R7 controller action 不处于原始 REGISTERED 状态")
    for pending_action in REMAINING_PENDING_ACTIONS:
        pending = actions.get(pending_action)
        if not pending:
            raise ValueError(f"缺少剩余 pending action: {pending_action}")
        record = indexed[key(pending["spec"]["params"])]
        if record.get("status") != "pending" or int(record.get("budget", -1)) != 32:
            raise ValueError(f"其余 action 不再是 pending: {pending_action}")

    indexed[EXPECTED_KEY] = failure_record
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
    if counts != {"success": 11, "failed": 1, "pending": 4}:
        raise ValueError(f"R7 接入后的 controller 计数异常: {counts}")
    write_json(observations_path, {"schema_version": 1, "records": output_records})

    action_index = load(action_index_path)
    rows = [row for row in action_index.get("actions", []) if row.get("action_id") == EXPECTED_ACTION]
    if len(action_index.get("actions", [])) != 16 or len(rows) != 1:
        raise ValueError("R7 action_index 身份不唯一")
    row = rows[0]
    if row.get("observation_status") not in {"pending", "failed"}:
        raise ValueError("R7 action_index 已有不同终态")
    row.update({
        "observation_status": "failed", "accepted": False,
        "artifact": failure_record["artifact"], "r7_failure_handoff": True,
        "failure_evidence_sha256": canonical_sha256(failure_record["failure_evidence"]),
    })
    write_json(action_index_path, action_index)

    pre_observations_sha256 = baseline_observations_sha256
    pre_action_index_sha256 = baseline_action_index_sha256
    if (
        not isinstance(pre_observations_sha256, str) or len(pre_observations_sha256) != 64
        or not isinstance(pre_action_index_sha256, str) or len(pre_action_index_sha256) != 64
    ):
        raise ValueError("R7 audit 的 pre-state hash 无效")
    audit = {
        "schema_version": 1,
        "status": "pass_failure_only",
        "pre_r7_observations_sha256": pre_observations_sha256,
        "pre_r7_action_index_sha256": pre_action_index_sha256,
        "post_r7_observations_sha256": sha256(observations_path),
        "post_r7_action_index_sha256": sha256(action_index_path),
        "input_evidence": {
            "run_spec": {"artifact": relative(run_spec_path), "sha256": sha256(run_spec_path)},
            "validation_summary": {"artifact": relative(validation_summary_path), "sha256": sha256(validation_summary_path)},
            "partial_handoff_summary": {"artifact": relative(handoff_summary_path), "sha256": sha256(handoff_summary_path)},
            "handoff_audit": {"artifact": relative(handoff_audit_path), "sha256": sha256(handoff_audit_path)},
            "r6_ingestion_summary": {"artifact": relative(r6_summary_path), "sha256": sha256(r6_summary_path)},
            "r6_ingestion_audit": {"artifact": relative(r6_audit_path), "sha256": sha256(r6_audit_path)},
            "calibration": {"artifact": relative(calibration_path), "sha256": sha256(calibration_path)},
        },
        "checksum_entries": {
            "parent": len(parent_hashes),
            "children": {mode: len(entries) for mode, entries in child_hashes.items()},
        },
        "invariants": {
            "controller_counts": counts, "calibration_accepted_total": 5,
            "failure_record_has_value_error": False,
            "original_pending_preserved": True, "r6_provenance_preserved": True,
            "remaining_pending_unchanged": True,
            "crossing_assigned": False, "phase_label_assigned": False,
        },
        "outputs": {"observations": relative(observations_path), "action_index": relative(action_index_path)},
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
        "cell_id": CELL_ID,
        "failed_key": {"alpha": -0.1, "beta": 0.5, "L": 60},
        "counts": {
            "controller_success_total": 11, "controller_failed_total": 1,
            "controller_pending_total": 4, "calibration_accepted_total": 5,
        },
        "failure_evidence": failure_record["failure_evidence"],
        "provenance": failure_record["r7_provenance"],
        "audit": {"artifact": relative(audit_path), "sha256": sha256(audit_path)},
        "observations": {"artifact": relative(observations_path), "sha256": sha256(observations_path)},
        "action_index": {"artifact": relative(action_index_path), "sha256": sha256(action_index_path)},
        "controller": controller,
        "interpretation": "R7 仅把严格失败终态写入 action；无 value/error，其余 action 保持 pending，不赋 crossing 或相名",
    }
    write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
