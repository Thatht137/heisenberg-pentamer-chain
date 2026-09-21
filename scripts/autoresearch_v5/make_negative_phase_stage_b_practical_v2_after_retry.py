#!/usr/bin/env python3
"""R12通过后生成 Stage B 剩余76点续跑包。"""

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


STAGE_NAME = "stage-b-negative-coarse-r13-remaining76"
STAGE_REL = f"{RUN_REL}/{STAGE_NAME}"
STAGE = RUN / STAGE_NAME


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-stage", default="stage-b-negative-coarse-r11-remaining77")
    parser.add_argument("--retry-stage", default="stage-b-negative-coarse-r12-remaining1")
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base = RUN / args.base_stage
    retry = RUN / args.retry_stage
    spec_path = base / "parameter-scan.run_spec.json"
    plan_path = base / "stage-b-action-plan.json"
    index_path = base / "accepted-practical-v2-index.json"
    retry_spec_path = retry / "parameter-scan.run_spec.json"
    validation_path = args.validation.resolve()
    receipt_path = args.receipt.resolve()
    for path in (spec_path, plan_path, index_path, retry_spec_path, validation_path, receipt_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    if STAGE.exists():
        raise FileExistsError(STAGE)

    validation, receipt = load(validation_path), load(receipt_path)
    if (
        validation.get("status") != "pass"
        or validation.get("acceptance_label") != "accepted_under_practical_v2"
        or validation.get("thresholds", {}).get("variance_per_site_max") != VARIANCE_MAX
        or validation.get("failures") != []
        or receipt.get("status") != "pass"
        or receipt.get("non_clobbering") is not True
        or receipt.get("cell_id") != validation.get("cell_id")
    ):
        raise ValueError("R12证据不满足续跑门")
    retry_spec = load(retry_spec_path)
    if len(retry_spec["cells"]) != 1 or key(retry_spec["cells"][0]["params"]) != key(validation["params"]):
        raise ValueError("R12 spec 与 validator 不一致")

    base_spec, base_plan = load(spec_path), load(plan_path)
    accepted_key = key(validation["params"])
    matched = [cell for cell in base_spec["cells"] if key(cell["params"]) == accepted_key]
    if len(matched) != 1 or int(matched[0]["budget"]) != 32:
        raise ValueError("R11失败点映射错误")
    action_map = {row["action_id"]: row for row in base_plan["actions"]}
    cells, actions = [], []
    for original in base_spec["cells"]:
        if key(original["params"]) == accepted_key:
            continue
        cell = json.loads(json.dumps(original))
        if int(cell["budget"]) > MAX_SWEEPS:
            raise ValueError("剩余任务超过64 sweeps")
        old_id = cell["cell_id"]
        cell["cell_id"] = old_id.replace("negb11-", "negb13-", 1)
        cell["stage"] = "B-R13-practical-v2-remaining76"
        cell["r11_cell_id"] = old_id
        cell["budget_rationale"] = "R12补算通过后释放；保留原预算且上限64"
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
    if len(cells) != 76 or len({key(cell["params"]) for cell in cells}) != 76:
        raise ValueError("R13剩余点数量或唯一性错误")

    STAGE.mkdir(parents=True)
    index = load(index_path)
    run_dir = Path(validation["run_dir"])
    index["records"].append(
        {
            "params": {name: validation["params"][name] for name in ("alpha", "beta", "L")},
            "cell_id": validation["cell_id"],
            "sweeps": int(validation["settings"]["nsweeps"]),
            "artifact": relative(run_dir / "manifest.json"),
            "validation_basis": relative(validation_path),
            "validation_sha256": sha256(validation_path),
            "legacy_accepted": bool(validation.get("legacy_parent_accepted")),
        }
    )
    if len({key(row["params"]) for row in index["records"]}) != 20:
        raise ValueError("accepted index 未形成20个唯一物理点")
    index["records"] = sorted(index["records"], key=lambda row: key(row["params"]))
    index["count"] = 20
    index_out = STAGE / "accepted-practical-v2-index.json"
    write_json(index_out, index)

    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    spec = json.loads(json.dumps(base_spec))
    spec.update(
        {
            "run_id": "pentamer-negative-phase-stage-b-r13-practical-v2-remaining76-20260830",
            "scope": "Stage B Practical V2 remaining76 after accepted R12 retry",
            "cells": cells,
        }
    )
    spec["provenance"].update(
        {
            "practical_v2_ratified": True,
            "variance_gate_relaxed": True,
            "phase_boundary_thresholds_relaxed": False,
            "max_new_sweeps": MAX_SWEEPS,
            "r12_validation": relative(validation_path),
            "r12_validation_sha256": sha256(validation_path),
            "r12_fetch_receipt": relative(receipt_path),
            "r12_fetch_receipt_sha256": sha256(receipt_path),
            "accepted_index": relative(index_out),
            "accepted_index_sha256": sha256(index_out),
            "prior_accepted_physical_points": 20,
            "retry_policy": "32-sweep variance failure may retry once at64; no128",
            "code_sha256": code_hashes,
        }
    )
    plan = {
        "schema_version": 1,
        "stage": "B-R13-practical-v2-remaining76",
        "canonical_action_index_mutated": False,
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
        "cell_count": 76,
        "concurrency": 1,
        "stop_on_first_failure": True,
        "offline": True,
        "eta_hours": {"low": 14, "high": 25},
        "budget_counts": budget_counts,
        "max_new_sweeps": MAX_SWEEPS,
        "variance_per_site_max": VARIANCE_MAX,
        "variance_gate_relaxed": True,
        "boundary_thresholds_relaxed": False,
        "run_spec_sha256": sha256(spec_out),
        "source_hashes_sha256": sha256(hashes_out),
        "action_plan_sha256": sha256(plan_out),
        "accepted_index_sha256": sha256(index_out),
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
            "stage": "B-R13-practical-v2-remaining76",
            "stage_directory": STAGE_NAME,
            "cell_count": 76,
            "concurrency": 1,
            "stop_on_first_failure": True,
            "eta_hours": {"low": 14, "high": 25},
            "files": [
                {"path": name, "sha256": sha256(ROOT / name), "bytes": (ROOT / name).stat().st_size}
                for name in files
            ],
        },
    )
    print(json.dumps({"status": "pass", "stage": STAGE_NAME, "accepted": 20, "remaining": 76, "budget_counts": budget_counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
