#!/usr/bin/env python3
"""组装 Stage C 终态，不直接改写正式控制器。"""

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
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--launch-contract", type=Path, required=True)
    parser.add_argument("--phase-dir", type=Path, required=True)
    parser.add_argument("--round", type=int, default=1)
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
    direct, nested = fetch / cell_id, fetch / "cells" / cell_id
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
        "stage_c_provenance": {"run_spec": relative(spec_path),
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
        "stage_c_provenance": {"run_spec": relative(spec_path),
                               "run_spec_sha256": sha256(spec_path)},
    }
    if contains_measurement(record):
        raise ValueError(f"{cell_id} 失败记录含 value/error")
    return record


def pending_record(cell: dict[str, Any], spec_path: Path) -> dict[str, Any]:
    return {
        "params": cell["params"], "status": "pending", "budget": cell["budget"],
        "accepted_only": False, "controller_action_id": cell["controller_action_id"],
        "stage_c_provenance": {"run_spec": relative(spec_path),
                               "run_spec_sha256": sha256(spec_path)},
    }


def main() -> int:
    args = parse_args()
    fetch, spec_path = args.fetch_dir.resolve(), args.run_spec.resolve()
    analysis_path, contract_path = args.analysis.resolve(), args.launch_contract.resolve()
    phase = args.phase_dir.resolve()
    for path in (fetch, spec_path, analysis_path, contract_path, phase):
        if not path.exists():
            raise FileNotFoundError(path)
    spec, analysis, contract = load(spec_path), load(analysis_path), load(contract_path)
    stage_b_summary = phase / "stage_b_r1_terminal_summary.json"
    if not stage_b_summary.is_file():
        raise FileNotFoundError(stage_b_summary)
    cells = spec.get("cells", [])
    action_rows = (analysis.get("stage_c_actions", []) if analysis.get("status") == "action_required"
                   else analysis.get("next_actions", []))
    actions = {row["action_id"]: row for row in action_rows}
    analysis_hash = spec.get("provenance", {}).get(
        "parent_analysis_sha256", spec.get("provenance", {}).get("stage_b_analysis_sha256")
    )
    contract_analysis_hash = contract.get(
        "parent_analysis_sha256", contract.get("stage_b_analysis_sha256")
    )
    if (
        contract.get("launch_ready") is not True or contract.get("stage_b_complete") is not True
        or contract.get("run_spec_sha256") != sha256(spec_path)
        or contract_analysis_hash != sha256(analysis_path)
        or spec.get("provenance", {}).get("stage_b_summary_sha256") != sha256(stage_b_summary)
        or analysis_hash != sha256(analysis_path)
        or load(stage_b_summary).get("status") != "accepted_stage_b_complete"
        or analysis.get("status") not in {"action_required", "refinement_required"}
        or len(cells) == 0 or len(cells) != len(actions)
        or len({key(cell["params"]) for cell in cells}) != len(cells)
    ):
        raise ValueError("Stage C 输入或 Stage B 释放证据不匹配")

    records, action_results, failed_cells, pass_cells = [], [], [], []
    seen_unmaterialized = False
    for cell in cells:
        cell_id = cell["cell_id"]
        action = dict(actions.get(cell["controller_action_id"], {}))
        if not action or key(action["params"]) != key(cell["params"]):
            raise ValueError(f"{cell_id} action 映射错误")
        validation_path = fetch / "validation" / f"{cell_id}.json"
        receipt_path = fetch / "receipts" / f"{cell_id}.json"
        if not validation_path.is_file() and not receipt_path.is_file():
            seen_unmaterialized = True
            record = pending_record(cell, spec_path)
            action.update({"observation_status": "pending", "accepted": False,
                           "terminal_state": "unmaterialized"})
        else:
            if seen_unmaterialized:
                raise ValueError("未物化 cell 之后仍有物化结果")
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
        action_results.append(action)

    counts = {name: sum(row["status"] == name for row in records)
              for name in ("success", "failed", "pending")}
    complete = counts == {"success": len(cells), "failed": 0, "pending": 0}
    status = "accepted_stage_c_round_complete" if complete else "partial_failure" if failed_cells else "not_terminal"
    if status == "not_terminal":
        raise ValueError("Stage C 仍运行，不应组装终态")
    outputs = {
        "observations": phase / f"stage_c_r{args.round}_terminal_observations.json",
        "actions": phase / f"stage_c_r{args.round}_terminal_action_results.json",
        "summary": phase / f"stage_c_r{args.round}_terminal_summary.json",
    }
    if any(path.exists() for path in outputs.values()):
        raise FileExistsError("Stage C 终态文件已存在，拒绝覆盖")
    stage_name = f"C-R{args.round}-refine"
    write_json(outputs["observations"], {"schema_version": 1, "stage": stage_name,
                                         "records": records})
    write_json(outputs["actions"], {"schema_version": 1, "stage": stage_name,
                                    "canonical_action_index_mutated": False,
                                    "actions": action_results})
    summary = {
        "schema_version": 1, "status": status, "round": args.round, "counts": counts,
        "planned_cells": len(cells), "pass_cells": pass_cells, "failed_cells": failed_cells,
        "unmaterialized_cells": counts["pending"],
        "observations": {"artifact": relative(outputs["observations"]),
                         "sha256": sha256(outputs["observations"])},
        "action_results": {"artifact": relative(outputs["actions"]),
                           "sha256": sha256(outputs["actions"])},
        "next_analysis_ready": complete, "stage_d_ready": False,
        "canonical_controller_mutated": False,
        "failed_records_contain_value_or_error": any(
            contains_measurement(row) for row in records if row["status"] == "failed"),
        "boundary_thresholds_relaxed": False,
    }
    if summary["failed_records_contain_value_or_error"]:
        raise ValueError("Stage C 失败记录泄漏测量值")
    write_json(outputs["summary"], summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
