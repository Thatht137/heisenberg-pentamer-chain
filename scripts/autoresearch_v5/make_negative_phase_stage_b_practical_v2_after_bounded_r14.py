#!/usr/bin/env python3
"""R14终态后生成跳过不可评估点的 Stage B 续跑包。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from make_negative_phase_stage_b_practical_v2_resume import (
    MAX_SWEEPS,
    ROOT,
    RUN,
    RUN_REL,
    SOURCES,
    VARIANCE_MAX,
    key,
    load,
    relative,
    sha256,
    write_json,
)


STAGE_NAME = "stage-b-negative-coarse-r15-remaining50"
STAGE_REL = f"{RUN_REL}/{STAGE_NAME}"
STAGE = RUN / STAGE_NAME


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-stage", default="stage-b-negative-coarse-r14-remaining65")
    parser.add_argument("--validation", type=Path, action="append", required=True)
    parser.add_argument("--receipt", type=Path, action="append", required=True)
    return parser.parse_args()


def validate_evidence(paths: list[Path], receipts: list[Path]) -> tuple[list[dict], dict, list[dict]]:
    if len(paths) != 15 or len(receipts) != 15:
        raise ValueError("R14 必须提供15组 validator 与回传证据")
    receipt_map = {load(path)["cell_id"]: (path.resolve(), load(path)) for path in receipts}
    passed: list[dict] = []
    failed: list[dict] = []
    evidence: list[dict] = []
    for path in paths:
        path = path.resolve()
        validation = load(path)
        cell_id = validation["cell_id"]
        receipt_path, receipt = receipt_map.get(cell_id, (None, None))
        if (
            receipt is None
            or receipt.get("status") != "pass"
            or receipt.get("non_clobbering") is not True
            or receipt.get("cell_id") != cell_id
        ):
            raise ValueError(f"回传证据不完整: {cell_id}")
        run_dir = Path(validation["run_dir"])
        manifest = run_dir / "manifest.json"
        if (
            not manifest.is_file()
            or validation.get("provenance", {}).get("original_manifest_sha256") != sha256(manifest)
            or validation.get("thresholds", {}).get("variance_per_site_max") != VARIANCE_MAX
        ):
            raise ValueError(f"validator provenance 不匹配: {cell_id}")
        row = {"validation_path": path, "receipt_path": receipt_path, "validation": validation}
        evidence.append(
            {
                "cell_id": cell_id,
                "status": validation.get("status"),
                "validation": relative(path),
                "validation_sha256": sha256(path),
                "receipt": relative(receipt_path),
                "receipt_sha256": sha256(receipt_path),
            }
        )
        if validation.get("status") == "pass" and validation.get("failures") == []:
            passed.append(row)
        else:
            failed.append(row)
    if len(passed) != 14 or len(failed) != 1:
        raise ValueError("R14 终态必须是14 pass/1 fail")
    failure = failed[0]["validation"]
    children = failure.get("children", [])
    if (
        int(failure.get("settings", {}).get("nsweeps", 0)) != MAX_SWEEPS
        or not failure.get("failures")
        or any(float(child["variance_per_site_sz0"]) > VARIANCE_MAX for child in children)
        or any(float(child["variance_per_site_sz1"]) > VARIANCE_MAX for child in children)
        or not any(float(child["spin_gap"]) < -1e-8 for child in children)
    ):
        raise ValueError("R14 失败不是64-sweep非方差终态")
    return passed, failed[0], evidence


def main() -> int:
    args = parse_args()
    base = RUN / args.base_stage
    spec_path = base / "parameter-scan.run_spec.json"
    plan_path = base / "stage-b-action-plan.json"
    index_path = base / "accepted-practical-v2-index.json"
    bounded_path = base / "bounded-practical-v2-records.json"
    for path in (spec_path, plan_path, index_path, bounded_path, *args.validation, *args.receipt):
        if not path.is_file():
            raise FileNotFoundError(path)
    if STAGE.exists():
        raise FileExistsError(STAGE)

    passed, failed, evidence = validate_evidence(args.validation, args.receipt)
    base_spec, base_plan, index = load(spec_path), load(plan_path), load(index_path)
    base_cells = {cell["cell_id"]: cell for cell in base_spec["cells"]}
    materialized_ids = {row["validation"]["cell_id"] for row in passed} | {failed["validation"]["cell_id"]}
    if not materialized_ids.issubset(base_cells):
        raise ValueError("R14 证据包含计划外 cell")

    STAGE.mkdir(parents=True)
    for row in passed:
        validation = row["validation"]
        run_dir = Path(validation["run_dir"])
        index["records"].append(
            {
                "params": {name: validation["params"][name] for name in ("alpha", "beta", "L")},
                "cell_id": validation["cell_id"],
                "sweeps": int(validation["settings"]["nsweeps"]),
                "artifact": relative(run_dir / "manifest.json"),
                "validation_basis": relative(row["validation_path"]),
                "validation_sha256": sha256(row["validation_path"]),
                "legacy_accepted": bool(validation.get("legacy_parent_accepted")),
            }
        )
    if len({key(row["params"]) for row in index["records"]}) != 44:
        raise ValueError("accepted index 未形成44个唯一物理点")
    index["records"] = sorted(index["records"], key=lambda row: key(row["params"]))
    index["count"] = 44
    index_out = STAGE / "accepted-practical-v2-index.json"
    write_json(index_out, index)

    bounded = load(bounded_path)
    if bounded.get("count") != 1 or len(bounded.get("records", [])) != 1:
        raise ValueError("R14 既有 bounded 索引异常")
    failed_validation = failed["validation"]
    bounded["records"].append(
        {
            "params": {name: failed_validation["params"][name] for name in ("alpha", "beta", "L")},
            "cell_id": failed_validation["cell_id"],
            "sweeps": MAX_SWEEPS,
            "status": "bounded/NotEvaluable",
            "failed_gate": "nonnegative_gap",
            "boundary_eligible": False,
            "retry_allowed": False,
            "validation_basis": relative(failed["validation_path"]),
            "validation_sha256": sha256(failed["validation_path"]),
            "receipt": relative(failed["receipt_path"]),
            "receipt_sha256": sha256(failed["receipt_path"]),
        }
    )
    bounded["records"] = sorted(bounded["records"], key=lambda row: key(row["params"]))
    bounded["count"] = 2
    bounded["accepted_index_unchanged_by_bounded_records"] = True
    bounded_out = STAGE / "bounded-practical-v2-records.json"
    write_json(bounded_out, bounded)
    evidence_out = STAGE / "r14-terminal-evidence-index.json"
    write_json(evidence_out, {"schema_version": 1, "summary": "14 pass/1 bounded", "records": evidence})

    action_map = {row["action_id"]: row for row in base_plan["actions"]}
    cells, actions = [], []
    for original in base_spec["cells"]:
        if original["cell_id"] in materialized_ids:
            continue
        cell = json.loads(json.dumps(original))
        if int(cell["budget"]) > MAX_SWEEPS:
            raise ValueError("剩余任务超过64 sweeps")
        old_id = cell["cell_id"]
        cell["cell_id"] = old_id.replace("negb14-", "negb15-", 1)
        cell["stage"] = "B-R15-practical-v2-remaining50"
        cell["r14_cell_id"] = old_id
        cell["budget_rationale"] = "R14终态验收后续跑；保留原预算且上限64"
        cells.append(cell)
        action = json.loads(json.dumps(action_map[cell["controller_action_id"]]))
        action.update(
            {
                "lifecycle_state": "PLANNED",
                "observation_status": "pending",
                "accepted": False,
                "budget": cell["budget"],
                "artifact": f"{STAGE_REL}/cells/{cell['cell_id']}/manifest.json",
                "convergence_policy": "practical_v2",
            }
        )
        actions.append(action)
    if len(cells) != 50 or len({key(cell["params"]) for cell in cells}) != 50:
        raise ValueError("R15剩余点数量或唯一性错误")

    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    spec = json.loads(json.dumps(base_spec))
    spec.update(
        {
            "run_id": "pentamer-negative-phase-stage-b-r15-practical-v2-remaining50-20260901",
            "scope": "Stage B Practical V2 remaining50 after R14 terminal evidence",
            "cells": cells,
        }
    )
    spec["provenance"].update(
        {
            "practical_v2_ratified": True,
            "phase_boundary_thresholds_relaxed": False,
            "max_new_sweeps": MAX_SWEEPS,
            "r14_terminal_evidence": relative(evidence_out),
            "r14_terminal_evidence_sha256": sha256(evidence_out),
            "accepted_index": relative(index_out),
            "accepted_index_sha256": sha256(index_out),
            "bounded_records": relative(bounded_out),
            "bounded_records_sha256": sha256(bounded_out),
            "prior_accepted_physical_points": 44,
            "bounded_physical_points": 2,
            "retry_policy": "32-sweep variance failure may retry once at64; 64/nonvariance becomes bounded; no128",
            "code_sha256": code_hashes,
        }
    )
    plan = {
        "schema_version": 1,
        "stage": "B-R15-practical-v2-remaining50",
        "canonical_action_index_mutated": False,
        "bounded_actions_excluded": 2,
        "actions": actions,
    }
    spec_out = STAGE / "parameter-scan.run_spec.json"
    plan_out = STAGE / "stage-b-action-plan.json"
    hashes_out = STAGE / "stage_b_next_source_hashes.sha256"
    write_json(spec_out, spec)
    write_json(plan_out, plan)
    with hashes_out.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    budget_counts = {str(value): sum(int(cell["budget"]) == value for cell in cells) for value in (32, 64)}
    contract = {
        "schema_version": 1,
        "launch_ready": True,
        "previous_failure_validated": True,
        "practical_v2_ratified": True,
        "cell_count": 50,
        "concurrency": 1,
        "stop_on_first_failure": True,
        "offline": True,
        "eta_hours": {"low": 10, "high": 18},
        "budget_counts": budget_counts,
        "max_new_sweeps": MAX_SWEEPS,
        "variance_per_site_max": VARIANCE_MAX,
        "boundary_thresholds_relaxed": False,
        "bounded_physical_points": 2,
        "run_spec_sha256": sha256(spec_out),
        "source_hashes_sha256": sha256(hashes_out),
        "action_plan_sha256": sha256(plan_out),
        "accepted_index_sha256": sha256(index_out),
        "bounded_records_sha256": sha256(bounded_out),
        "standard_sha256": sha256(ROOT / "docs/negative_alpha_practical_convergence_standard_20260829.md"),
        "manifest_sha256": sha256(ROOT / "Manifest.toml"),
    }
    contract_out = STAGE / "launch-contract.json"
    write_json(contract_out, contract)
    files = SOURCES + [
        f"{STAGE_REL}/parameter-scan.run_spec.json",
        f"{STAGE_REL}/stage-b-action-plan.json",
        f"{STAGE_REL}/stage_b_next_source_hashes.sha256",
        f"{STAGE_REL}/accepted-practical-v2-index.json",
        f"{STAGE_REL}/bounded-practical-v2-records.json",
        f"{STAGE_REL}/r14-terminal-evidence-index.json",
        f"{STAGE_REL}/launch-contract.json",
    ]
    write_json(
        STAGE / "server_upload_manifest.json",
        {
            "schema_version": 1,
            "target": "/home/wangjieren/code/1x5_Heisenberg_Pentamer",
            "mode": "offline_upload_only",
            "launch_ready": True,
            "previous_failure_validated": True,
            "stage": "B-R15-practical-v2-remaining50",
            "stage_directory": STAGE_NAME,
            "cell_count": 50,
            "concurrency": 1,
            "stop_on_first_failure": True,
            "eta_hours": {"low": 10, "high": 18},
            "files": [
                {"path": name, "sha256": sha256(ROOT / name), "bytes": (ROOT / name).stat().st_size}
                for name in files
            ],
        },
    )
    print(
        json.dumps(
            {
                "status": "pass",
                "stage": STAGE_NAME,
                "accepted": 44,
                "bounded": 2,
                "remaining": 50,
                "budget_counts": budget_counts,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
