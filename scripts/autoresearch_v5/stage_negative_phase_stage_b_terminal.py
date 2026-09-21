#!/usr/bin/env python3
"""组装 Stage B 终态，不直接改写正式控制器。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ingest_negative_phase_r6 import load, relative, sha256, write_json


ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch-dir", type=Path, required=True)
    parser.add_argument("--run-spec", type=Path, required=True)
    parser.add_argument("--action-plan", type=Path, required=True)
    parser.add_argument("--launch-contract", type=Path, required=True)
    parser.add_argument("--phase-dir", type=Path, required=True)
    parser.add_argument("--round", default="r1")
    return parser.parse_args()


def key(params: dict[str, Any]) -> tuple[float, float, int]:
    return float(params["alpha"]), float(params["beta"]), int(params["L"])


def contains_measurement(value: Any) -> bool:
    if isinstance(value, dict):
        return any(name in {"value", "error"} or contains_measurement(item)
                   for name, item in value.items())
    if isinstance(value, list):
        return any(contains_measurement(item) for item in value)
    return False


def cell_dir(fetch: Path, cell_id: str) -> Path:
    direct = fetch / cell_id
    nested = fetch / "cells" / cell_id
    if direct.is_dir() == nested.is_dir():
        raise ValueError(f"{cell_id} 回传目录缺失或重复")
    return direct if direct.is_dir() else nested


def accepted_record(cell: dict[str, Any], manifest_path: Path, validation_path: Path,
                    receipt_path: Path, spec_path: Path) -> dict[str, Any]:
    manifest, validation, receipt = map(load, (manifest_path, validation_path, receipt_path))
    cell_id = cell["cell_id"]
    if (
        validation.get("status") != "pass" or validation.get("cell_id") != cell_id
        or validation.get("failures") != [] or not all(validation.get("checks", {}).values())
        or receipt.get("status") != "pass" or receipt.get("cell_id") != cell_id
        or receipt.get("non_clobbering") is not True
        or manifest.get("status") != "success" or manifest.get("accepted") is not True
        or manifest.get("cell_id") != cell_id or key(manifest.get("params", {})) != key(cell["params"])
        or manifest.get("settings", {}).get("nsweeps") != cell["budget"]
    ):
        raise ValueError(f"{cell_id} 的 validator、receipt 或 manifest 不一致")
    observable = manifest["observables"]["dominant_structure_factor_ratio"]
    return {
        "params": cell["params"], "status": "success",
        "value": observable["value"], "error": observable["error"],
        "budget": cell["budget"], "artifact": relative(manifest_path),
        "accepted_only": True, "controller_action_id": cell["controller_action_id"],
        "boundary_eligible": True,
        "diagnostics": {
            "q_peak_over_pi": manifest["observables"]["structure_factor_peak_q_over_pi"],
            "strict_numerical_gates": validation["checks"],
        },
        "validation": {"status": "pass", "artifact": relative(validation_path),
                       "sha256": sha256(validation_path)},
        "checksum_receipt": {"artifact": relative(receipt_path), "sha256": sha256(receipt_path)},
        "provenance": manifest["provenance"],
        "stage_b_provenance": {"run_spec": relative(spec_path),
                               "run_spec_sha256": sha256(spec_path)},
    }


def failed_record(cell: dict[str, Any], manifest_path: Path, validation_path: Path,
                  receipt_path: Path, spec_path: Path) -> dict[str, Any]:
    validation, receipt = load(validation_path), load(receipt_path)
    cell_id = cell["cell_id"]
    if (
        validation.get("status") != "fail" or validation.get("cell_id") != cell_id
        or not validation.get("failures") or receipt.get("status") != "pass"
        or receipt.get("cell_id") != cell_id or receipt.get("non_clobbering") is not True
    ):
        raise ValueError(f"{cell_id} 的失败证据不完整")
    record = {
        "params": cell["params"], "status": "failed", "budget": cell["budget"],
        "accepted_only": False, "artifact": relative(validation_path),
        "controller_action_id": cell["controller_action_id"],
        "failure_evidence": {
            "validator_artifact": relative(validation_path), "validator_sha256": sha256(validation_path),
            "manifest_artifact": relative(manifest_path), "manifest_sha256": sha256(manifest_path),
            "receipt_artifact": relative(receipt_path), "receipt_sha256": sha256(receipt_path),
            "failed_gates": validation["failures"], "thresholds_relaxed": False,
        },
        "stage_b_provenance": {"run_spec": relative(spec_path),
                               "run_spec_sha256": sha256(spec_path)},
    }
    if contains_measurement(record):
        raise ValueError(f"{cell_id} 失败记录含 value/error")
    return record


def pending_record(cell: dict[str, Any], spec_path: Path) -> dict[str, Any]:
    record = {
        "params": cell["params"], "status": "pending", "budget": cell["budget"],
        "accepted_only": False, "controller_action_id": cell["controller_action_id"],
        "artifact": cell.get("artifact"),
        "stage_b_provenance": {"run_spec": relative(spec_path),
                               "run_spec_sha256": sha256(spec_path)},
    }
    if contains_measurement(record):
        raise ValueError(f"{cell['cell_id']} pending 记录含 value/error")
    return record


def main() -> int:
    args = parse_args()
    fetch, spec_path, plan_path = args.fetch_dir.resolve(), args.run_spec.resolve(), args.action_plan.resolve()
    contract_path, phase = args.launch_contract.resolve(), args.phase_dir.resolve()
    for path in (fetch, spec_path, plan_path, contract_path, phase):
        if not path.exists():
            raise FileNotFoundError(path)
    spec, plan, contract = load(spec_path), load(plan_path), load(contract_path)
    stage_a_summary = phase / "r19_success_ingestion_summary.json"
    stage_a_analysis = phase / "stage_a_finite_size_diagnostic_latest.json"
    stage_a_calibration = phase / "accepted_calibration_through_r19.json"
    for path in (stage_a_summary, stage_a_analysis, stage_a_calibration):
        if not path.is_file():
            raise FileNotFoundError(path)
    stage_a_summary_doc = load(stage_a_summary)
    stage_a_analysis_doc = load(stage_a_analysis)
    if (
        contract.get("launch_ready") is not True or contract.get("stage_a_complete") is not True
        or contract.get("run_spec_sha256") != sha256(spec_path)
        or contract.get("action_plan_sha256") != sha256(plan_path)
        or spec.get("provenance", {}).get("r19_success_summary_sha256") != sha256(stage_a_summary)
        or spec.get("provenance", {}).get("stage_a_analysis_sha256") != sha256(stage_a_analysis)
        or spec.get("provenance", {}).get("accepted_calibration_through_r19_sha256") != sha256(stage_a_calibration)
        or stage_a_summary_doc.get("status") != "accepted_stage_a_complete"
        or stage_a_summary_doc.get("counts") != {
            "controller_success_total": 16, "controller_failed_total": 0,
            "controller_pending_total": 0, "calibration_accepted_total": 8,
        }
        or stage_a_analysis_doc.get("status") != "complete"
        or stage_a_analysis_doc.get("decision", {}).get("stage_b_ready") is not True
        or len(load(stage_a_calibration).get("records", [])) != 8
        or plan.get("canonical_action_index_mutated") is not False
        or len(spec.get("cells", [])) != int(contract.get("cell_count", -1))
        or len(plan.get("actions", [])) != len(spec.get("cells", []))
    ):
        raise ValueError("Stage B 输入或 Stage A 释放证据不匹配")

    actions = {row["action_id"]: dict(row) for row in plan["actions"]}
    records, failed_cells, pass_cells = [], [], []
    seen_unmaterialized = False
    for cell in spec["cells"]:
        cell_id = cell["cell_id"]
        validation_path = fetch / "validation" / f"{cell_id}.json"
        receipt_path = fetch / "receipts" / f"{cell_id}.json"
        action = actions.get(cell["controller_action_id"])
        if action is None or key(action["params"]) != key(cell["params"]):
            raise ValueError(f"{cell_id} action 映射错误")
        materialized = validation_path.is_file() or receipt_path.is_file()
        if not materialized:
            seen_unmaterialized = True
            records.append(pending_record(cell, spec_path))
            action.update({"observation_status": "pending", "accepted": False,
                           "terminal_state": "unmaterialized"})
            continue
        if seen_unmaterialized:
            raise ValueError("发现未物化 cell 之后仍有物化结果，违反顺序执行")
        run = cell_dir(fetch, cell_id)
        manifest_path = run / "manifest.json"
        for path in (manifest_path, validation_path, receipt_path):
            if not path.is_file():
                raise FileNotFoundError(path)
        status = load(validation_path).get("status")
        if status == "pass":
            record = accepted_record(cell, manifest_path, validation_path, receipt_path, spec_path)
            pass_cells.append(cell_id)
            action.update({"observation_status": "success", "accepted": True,
                           "terminal_state": "validated", "artifact": record["artifact"]})
        elif status == "fail":
            if failed_cells:
                raise ValueError("stop-on-first-failure 批次出现多个失败 cell")
            record = failed_record(cell, manifest_path, validation_path, receipt_path, spec_path)
            failed_cells.append(cell_id)
            action.update({"observation_status": "failed", "accepted": False,
                           "terminal_state": "validated_failure", "artifact": record["artifact"],
                           "retry_recommendation": {"next_budget": min(128, cell["budget"] * 2),
                                                    "thresholds_relaxed": False}})
            seen_unmaterialized = True
        else:
            raise ValueError(f"{cell_id} validator 状态非法")
        records.append(record)

    counts = {name: sum(row["status"] == name for row in records)
              for name in ("success", "failed", "pending")}
    planned_count = len(spec["cells"])
    if sum(counts.values()) != planned_count or len({key(row["params"]) for row in records}) != planned_count:
        raise ValueError("Stage B 记录数量或参数唯一性异常")
    if counts["failed"] not in {0, 1} or (counts["failed"] == 0 and counts["pending"] not in {0, 96}):
        raise ValueError(f"Stage B 终态形状异常: {counts}")
    complete = counts == {"success": planned_count, "failed": 0, "pending": 0}
    status = "accepted_stage_b_complete" if complete else "partial_failure" if failed_cells else "not_terminal"
    if status == "not_terminal":
        raise ValueError("Stage B 仍运行，不应组装终态")

    round_name = str(args.round).lower()
    if not round_name.startswith("r") or not round_name[1:].isdigit():
        raise ValueError("round 必须为 r1、r2 等")
    observations_out = phase / f"stage_b_{round_name}_terminal_observations.json"
    actions_out = phase / f"stage_b_{round_name}_terminal_action_results.json"
    summary_out = phase / f"stage_b_{round_name}_terminal_summary.json"
    for path in (observations_out, actions_out, summary_out):
        if path.exists():
            raise FileExistsError(f"拒绝覆盖: {path}")
    stage_name = f"B-{round_name.upper()}-coarse-96"
    write_json(observations_out, {"schema_version": 1, "stage": stage_name,
                                  "records": records})
    write_json(actions_out, {"schema_version": 1, "stage": stage_name,
                             "canonical_action_index_mutated": False,
                             "actions": list(actions.values())})
    summary = {
        "schema_version": 1, "status": status, "counts": counts,
        "pass_cells": pass_cells, "failed_cells": failed_cells,
        "unmaterialized_cells": counts["pending"],
        "observations": {"artifact": relative(observations_out), "sha256": sha256(observations_out)},
        "action_results": {"artifact": relative(actions_out), "sha256": sha256(actions_out)},
        "stage_c_ready": complete, "canonical_controller_mutated": False,
        "stage_a_release": {
            "summary": {"artifact": relative(stage_a_summary), "sha256": sha256(stage_a_summary)},
            "analysis": {"artifact": relative(stage_a_analysis), "sha256": sha256(stage_a_analysis)},
            "calibration": {"artifact": relative(stage_a_calibration), "sha256": sha256(stage_a_calibration)},
        },
        "failed_records_contain_value_or_error": any(
            contains_measurement(row) for row in records if row["status"] == "failed"),
        "boundary_thresholds_relaxed": False,
    }
    if summary["failed_records_contain_value_or_error"]:
        raise ValueError("Stage B 失败记录泄漏测量值")
    write_json(summary_out, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
