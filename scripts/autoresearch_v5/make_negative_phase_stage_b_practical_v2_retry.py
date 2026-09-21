#!/usr/bin/env python3
"""为 Practical V2 的纯方差失败生成一次64-sweep补算。"""

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


STAGE_NAME = "stage-b-negative-coarse-r12-remaining1"
STAGE_REL = f"{RUN_REL}/{STAGE_NAME}"
STAGE = RUN / STAGE_NAME


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-stage", default="stage-b-negative-coarse-r11-remaining77")
    parser.add_argument("--validation", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    previous = RUN / args.previous_stage
    spec_path = previous / "parameter-scan.run_spec.json"
    plan_path = previous / "stage-b-action-plan.json"
    index_path = previous / "accepted-practical-v2-index.json"
    validation_path = args.validation.resolve()
    receipt_path = args.receipt.resolve()
    for path in (spec_path, plan_path, index_path, validation_path, receipt_path):
        if not path.is_file():
            raise FileNotFoundError(path)
    if STAGE.exists():
        raise FileExistsError(STAGE)

    validation, receipt = load(validation_path), load(receipt_path)
    failures = validation.get("failures", [])
    if (
        validation.get("status") != "fail"
        or validation.get("acceptance_label") != "rejected_under_practical_v2"
        or validation.get("thresholds", {}).get("variance_per_site_max") != VARIANCE_MAX
        or len(failures) != 1
        or "variance" not in failures[0]
        or receipt.get("status") != "pass"
        or receipt.get("non_clobbering") is not True
        or receipt.get("cell_id") != validation.get("cell_id")
    ):
        raise ValueError("失败证据不满足单次64-sweep补算门")

    source_spec, source_plan = load(spec_path), load(plan_path)
    matches = [cell for cell in source_spec["cells"] if cell["cell_id"] == validation["cell_id"]]
    if len(matches) != 1 or int(matches[0]["budget"]) != 32 or key(matches[0]["params"]) != key(validation["params"]):
        raise ValueError("R11 cell 与 validator 不一致")
    original = matches[0]
    action_map = {row["action_id"]: row for row in source_plan["actions"]}
    action = json.loads(json.dumps(action_map[original["controller_action_id"]]))
    cell = json.loads(json.dumps(original))
    cell["cell_id"] = original["cell_id"].replace("negb11-", "negb12-", 1)
    cell["stage"] = "B-R12-practical-v2-retry1"
    cell["r11_cell_id"] = original["cell_id"]
    cell["budget"] = MAX_SWEEPS
    cell["budget_rationale"] = "Practical V2纯方差失败；32→64唯一补算"
    action.update(
        {
            "lifecycle_state": "PLANNED",
            "observation_status": "pending",
            "accepted": False,
            "budget": MAX_SWEEPS,
            "artifact": f"{STAGE_REL}/cells/{cell['cell_id']}/manifest.json",
            "convergence_policy": "practical_v2",
        }
    )

    STAGE.mkdir(parents=True)
    index = load(index_path)
    retry_index = STAGE / "accepted-practical-v2-index.json"
    write_json(retry_index, index)
    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    spec = json.loads(json.dumps(source_spec))
    spec.update(
        {
            "run_id": "pentamer-negative-phase-stage-b-r12-practical-v2-retry1-20260830",
            "scope": "Stage B Practical V2 one-point 32-to-64 variance retry",
            "cells": [cell],
        }
    )
    spec["provenance"].update(
        {
            "practical_v2_ratified": True,
            "variance_gate_relaxed": True,
            "phase_boundary_thresholds_relaxed": False,
            "max_new_sweeps": MAX_SWEEPS,
            "retry_is_final": True,
            "r11_failure_validation": relative(validation_path),
            "r11_failure_validation_sha256": sha256(validation_path),
            "r11_fetch_receipt": relative(receipt_path),
            "r11_fetch_receipt_sha256": sha256(receipt_path),
            "accepted_index": relative(retry_index),
            "accepted_index_sha256": sha256(retry_index),
            "code_sha256": code_hashes,
        }
    )
    plan = {
        "schema_version": 1,
        "stage": "B-R12-practical-v2-retry1",
        "canonical_action_index_mutated": False,
        "actions": [action],
    }
    spec_out = STAGE / "parameter-scan.run_spec.json"
    plan_out = STAGE / "stage-b-action-plan.json"
    hashes_out = STAGE / "stage_b_next_source_hashes.sha256"
    write_json(spec_out, spec)
    write_json(plan_out, plan)
    with hashes_out.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    contract = {
        "schema_version": 1,
        "launch_ready": True,
        "previous_failure_validated": True,
        "practical_v2_ratified": True,
        "cell_count": 1,
        "concurrency": 1,
        "stop_on_first_failure": True,
        "offline": True,
        "eta_hours": {"low": 0.33, "high": 0.75},
        "budget_counts": {"64": 1},
        "max_new_sweeps": MAX_SWEEPS,
        "variance_per_site_max": VARIANCE_MAX,
        "variance_gate_relaxed": True,
        "boundary_thresholds_relaxed": False,
        "run_spec_sha256": sha256(spec_out),
        "source_hashes_sha256": sha256(hashes_out),
        "action_plan_sha256": sha256(plan_out),
        "accepted_index_sha256": sha256(retry_index),
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
            "stage": "B-R12-practical-v2-retry1",
            "stage_directory": STAGE_NAME,
            "cell_count": 1,
            "concurrency": 1,
            "stop_on_first_failure": True,
            "eta_hours": {"low": 0.33, "high": 0.75},
            "files": [
                {"path": name, "sha256": sha256(ROOT / name), "bytes": (ROOT / name).stat().st_size}
                for name in files
            ],
        },
    )
    print(json.dumps({"status": "pass", "stage": STAGE_NAME, "cell": cell["cell_id"], "budget": 64}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
