#!/usr/bin/env python3
"""按 Practical V2 生成 Stage B 最小续跑包。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN_REL = "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha"
RUN = ROOT / RUN_REL
STAGE_NAME = "stage-b-negative-coarse-r11-remaining77"
STAGE_REL = f"{RUN_REL}/{STAGE_NAME}"
STAGE = RUN / STAGE_NAME
VARIANCE_MAX = 5e-8
MAX_SWEEPS = 64
SOURCES = [
    "Project.toml",
    "Manifest.toml",
    "docs/full_phase_diagram_negative_standard_20260809.md",
    "docs/negative_alpha_practical_convergence_standard_20260829.md",
    "src/PentamerChain.jl",
    "src/hamiltonian.jl",
    "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py",
    "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py",
    "scripts/autoresearch_v5/validate_negative_phase_run_practical_v2.py",
    "scripts/autoresearch_v5/launch_negative_phase_stage_b_next.sh",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-stage", default="stage-b-negative-coarse-r10-remaining79")
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--validation", type=Path, action="append", required=True)
    return parser.parse_args()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def key(params: dict) -> tuple[float, float, int]:
    return float(params["alpha"]), float(params["beta"]), int(params["L"])


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def expected_grid() -> set[tuple[float, float, int]]:
    alphas = (-1.0, -0.75, -0.5, -0.35, -0.25, -0.1, -0.05, -0.025)
    betas = (0.05, 0.1, 0.25, 0.75, 0.9, 1.0)
    return {(alpha, beta, length) for beta in betas for alpha in alphas for length in (40, 60)}


def accepted_index(audit_path: Path, validation_paths: list[Path]) -> dict:
    audit = load(audit_path)
    chosen: dict[tuple[float, float, int], dict] = {}
    for row in audit.get("records", []):
        if row.get("pass_5e-08") is not True:
            continue
        physical_key = float(row["alpha"]), float(row["beta"]), int(row["L"])
        candidate = {
            "params": {"alpha": physical_key[0], "beta": physical_key[1], "L": physical_key[2]},
            "cell_id": row["cell_id"],
            "sweeps": int(row["sweeps"]),
            "artifact": Path(row["manifest"]).as_posix(),
            "validation_basis": "threshold_audit_5e-8",
            "legacy_accepted": bool(row.get("old_accepted")),
        }
        current = chosen.get(physical_key)
        if current is None or (candidate["sweeps"], candidate["legacy_accepted"]) > (
            current["sweeps"], current["legacy_accepted"]
        ):
            chosen[physical_key] = candidate

    for validation_path in validation_paths:
        validation = load(validation_path)
        if (
            validation.get("status") != "pass"
            or validation.get("acceptance_label") != "accepted_under_practical_v2"
            or validation.get("thresholds", {}).get("variance_per_site_max") != VARIANCE_MAX
            or validation.get("failures") != []
        ):
            raise ValueError(f"V2 validator 未通过: {validation_path}")
        physical_key = key(validation["params"])
        run_dir = Path(validation["run_dir"])
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.is_file() or validation["provenance"]["original_manifest_sha256"] != sha256(manifest_path):
            raise ValueError(f"V2 validator provenance 不匹配: {validation_path}")
        candidate = {
            "params": {"alpha": physical_key[0], "beta": physical_key[1], "L": physical_key[2]},
            "cell_id": validation["cell_id"],
            "sweeps": int(validation["settings"]["nsweeps"]),
            "artifact": relative(manifest_path),
            "validation_basis": relative(validation_path),
            "validation_sha256": sha256(validation_path),
            "legacy_accepted": bool(validation.get("legacy_parent_accepted")),
        }
        current = chosen.get(physical_key)
        if current is None or (candidate["sweeps"], candidate["legacy_accepted"]) >= (
            current["sweeps"], current["legacy_accepted"]
        ):
            chosen[physical_key] = candidate

    records = [chosen[item] for item in sorted(chosen)]
    return {
        "schema_version": 1,
        "policy": "Practical V2",
        "variance_per_site_max": VARIANCE_MAX,
        "records": records,
        "count": len(records),
        "old_manifests_unchanged": True,
    }


def main() -> int:
    args = parse_args()
    source = RUN / args.source_stage
    spec_path = source / "parameter-scan.run_spec.json"
    plan_path = source / "stage-b-action-plan.json"
    audit_path = args.audit.resolve()
    validation_paths = [path.resolve() for path in args.validation]
    for path in (spec_path, plan_path, audit_path, *validation_paths):
        if not path.is_file():
            raise FileNotFoundError(path)
    if STAGE.exists():
        raise FileExistsError(STAGE)

    source_spec, source_plan = load(spec_path), load(plan_path)
    index = accepted_index(audit_path, validation_paths)
    accepted_keys = {key(row["params"]) for row in index["records"]}
    source_keys = {key(cell["params"]) for cell in source_spec["cells"]}
    if accepted_keys | source_keys != expected_grid() or len(accepted_keys) != 19:
        raise ValueError("accepted 与 R10 未覆盖完整 96 点网格")

    action_map = {row["action_id"]: row for row in source_plan["actions"]}
    cells, actions = [], []
    for original in source_spec["cells"]:
        if key(original["params"]) in accepted_keys:
            continue
        cell = json.loads(json.dumps(original))
        if int(cell["budget"]) > MAX_SWEEPS:
            raise ValueError(f"新任务超过 {MAX_SWEEPS} sweeps: {cell['cell_id']}")
        old_id = cell["cell_id"]
        cell["cell_id"] = old_id.replace(old_id.split("-", 1)[0] + "-", "negb11-", 1)
        cell["stage"] = "B-R11-practical-v2-remaining77"
        cell["r10_cell_id"] = old_id
        cell["budget_rationale"] = "Practical V2 粗扫；保留原预算且上限64"
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
    if len(cells) != 77 or len({key(cell["params"]) for cell in cells}) != 77:
        raise ValueError("续跑点数量或唯一性错误")

    STAGE.mkdir(parents=True)
    index_path = STAGE / "accepted-practical-v2-index.json"
    write_json(index_path, index)
    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    spec = json.loads(json.dumps(source_spec))
    spec.update(
        {
            "run_id": "pentamer-negative-phase-stage-b-r11-practical-v2-remaining77-20260829",
            "scope": "Stage B Practical V2 remaining77; archive reuse before recompute",
            "cells": cells,
        }
    )
    spec["settings"]["variance_per_site_max"] = VARIANCE_MAX
    spec["settings"]["acceptance"]["variance_per_site_max"] = VARIANCE_MAX
    spec["settings"]["execution"] = "direct SSH; concurrency=1; stop on first failed cell; max new sweeps=64"
    spec["provenance"].update(
        {
            "practical_v2_ratified": True,
            "ratified_at": "2026-08-29",
            "variance_gate_relaxed": True,
            "phase_boundary_thresholds_relaxed": False,
            "max_new_sweeps": MAX_SWEEPS,
            "policy": "docs/negative_alpha_practical_convergence_standard_20260829.md",
            "policy_sha256": sha256(ROOT / "docs/negative_alpha_practical_convergence_standard_20260829.md"),
            "threshold_audit": relative(audit_path),
            "threshold_audit_sha256": sha256(audit_path),
            "accepted_index": relative(index_path),
            "accepted_index_sha256": sha256(index_path),
            "prior_accepted_physical_points": len(accepted_keys),
            "retry_policy": "32-sweep failure may retry once at 64; no new 128-sweep task",
            "code_sha256": code_hashes,
        }
    )
    plan = {
        "schema_version": 1,
        "stage": "B-R11-practical-v2-remaining77",
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
        "cell_count": len(cells),
        "concurrency": 1,
        "stop_on_first_failure": True,
        "offline": True,
        "eta_hours": {"low": 15, "high": 26},
        "budget_counts": budget_counts,
        "max_new_sweeps": MAX_SWEEPS,
        "variance_per_site_max": VARIANCE_MAX,
        "variance_gate_relaxed": True,
        "boundary_thresholds_relaxed": False,
        "run_spec_sha256": sha256(spec_out),
        "source_hashes_sha256": sha256(hashes_out),
        "action_plan_sha256": sha256(plan_out),
        "accepted_index_sha256": sha256(index_path),
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
            "stage": "B-R11-practical-v2-remaining77",
            "stage_directory": STAGE_NAME,
            "cell_count": len(cells),
            "concurrency": 1,
            "stop_on_first_failure": True,
            "eta_hours": {"low": 15, "high": 26},
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
                "accepted_physical_points": len(accepted_keys),
                "remaining_cells": len(cells),
                "budget_counts": budget_counts,
                "variance_per_site_max": VARIANCE_MAX,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
