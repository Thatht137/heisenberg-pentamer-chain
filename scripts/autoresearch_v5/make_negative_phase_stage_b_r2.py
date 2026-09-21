#!/usr/bin/env python3
"""生成 Stage B R2：首点升至64 sweeps，其余95点续跑。"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN_REL = "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha"
RUN = ROOT / RUN_REL
PHASE = RUN / "phase-diagram-v2"
R1 = RUN / "stage-b-negative-coarse-r1-96"
STAGE_REL = f"{RUN_REL}/stage-b-negative-coarse-r2-96"
STAGE = ROOT / STAGE_REL
LAUNCHER = "scripts/autoresearch_v5/launch_negative_phase_stage_b_r2_96.sh"
SOURCES = [
    "Project.toml", "Manifest.toml", "docs/full_phase_diagram_negative_standard_20260809.md",
    "src/PentamerChain.jl", "src/hamiltonian.jl", "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py", "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py",
    "scripts/autoresearch_v5/validate_negative_phase_run.py", LAUNCHER,
]


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


def main() -> int:
    outputs = [STAGE / name for name in (
        "parameter-scan.run_spec.json", "stage_b_r2_source_hashes.sha256",
        "launch-contract.json", "stage-b-action-plan.json", "server_upload_manifest.json",
    )]
    existing = [path for path in outputs if path.exists()]
    if existing:
        complete = all(path.exists() for path in outputs)
        if complete:
            raise FileExistsError("Stage B R2 文件已存在，拒绝覆盖")
        if any(path.name not in {"parameter-scan.run_spec.json", "stage-b-action-plan.json"} for path in existing):
            raise FileExistsError("Stage B R2 存在未知部分输出，拒绝覆盖")
        for path in existing:
            path.unlink()
    r1_spec_path = R1 / "parameter-scan.run_spec.json"
    r1_plan_path = R1 / "stage-b-action-plan.json"
    r1_summary_path = PHASE / "stage_b_r1_terminal_summary.json"
    required = [r1_spec_path, r1_plan_path, r1_summary_path, *(ROOT / name for name in SOURCES)]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(missing)
    r1_spec, r1_plan, summary = map(load, (r1_spec_path, r1_plan_path, r1_summary_path))
    if (
        summary.get("status") != "partial_failure"
        or summary.get("counts") != {"success": 0, "failed": 1, "pending": 95}
        or summary.get("failed_cells") != ["negb1-a1000-b0050-L040"]
        or summary.get("boundary_thresholds_relaxed") is not False
        or len(r1_spec.get("cells", [])) != 96
    ):
        raise ValueError("Stage B R1 失败基线不匹配")

    cells = []
    for index, original in enumerate(r1_spec["cells"]):
        cell = json.loads(json.dumps(original))
        cell["cell_id"] = cell["cell_id"].replace("negb1-", "negb2-")
        cell["stage"] = "B-R2-coarse-96"
        if index == 0:
            cell["budget"] = 64
            cell["budget_rationale"] = "R1双初态Sz0方差超门；按32→64重试"
        cell["r1_cell_id"] = original["cell_id"]
        cells.append(cell)
    if cells[0]["budget"] != 64 or sum(row["budget"] == 64 for row in cells) != 61:
        raise ValueError("R2预算分配异常")

    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    spec = json.loads(json.dumps(r1_spec))
    spec.update({
        "run_id": "pentamer-negative-phase-stage-b-r2-96-20260812",
        "scope": "Stage B R2; first failed cell promoted 32 to 64, then remaining 95",
        "cells": cells,
    })
    spec["settings"]["execution"] = "direct SSH; concurrency=1; stop on first failed cell"
    spec["provenance"].update({
        "stage_b_r1_terminal_summary_sha256": sha256(r1_summary_path),
        "stage_b_r1_run_spec_sha256": sha256(r1_spec_path),
        "retry_policy": "only first failed cell 32->64; later cells retain declared budgets",
        "code_sha256": code_hashes,
        "boundary_thresholds_relaxed": False,
    })
    actions = json.loads(json.dumps(r1_plan))
    actions["stage"] = "B-R2-coarse-96"
    actions["r1_terminal_summary_sha256"] = sha256(r1_summary_path)
    for index, action in enumerate(actions["actions"]):
        action.update({"lifecycle_state": "PLANNED", "observation_status": "pending",
                       "accepted": False, "artifact": f"{STAGE_REL}/cells/{cells[index]['cell_id']}/manifest.json",
                       "budget": cells[index]["budget"]})

    STAGE.mkdir(parents=True, exist_ok=True)
    spec_path = STAGE / "parameter-scan.run_spec.json"
    plan_path = STAGE / "stage-b-action-plan.json"
    hashes_path = STAGE / "stage_b_r2_source_hashes.sha256"
    write_json(spec_path, spec)
    write_json(plan_path, actions)
    with hashes_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    contract = {
        "schema_version": 1, "launch_ready": True, "stage_a_complete": True,
        "r1_failure_validated": True, "cell_count": 96, "concurrency": 1,
        "stop_on_first_failure": True, "offline": True, "eta_hours": {"low": 18, "high": 32},
        "budget_counts": {"32": 35, "64": 61}, "run_spec_sha256": sha256(spec_path),
        "source_hashes_sha256": sha256(hashes_path), "action_plan_sha256": sha256(plan_path),
        "r1_terminal_summary_sha256": sha256(r1_summary_path),
        "boundary_thresholds_relaxed": False,
    }
    contract_path = STAGE / "launch-contract.json"
    write_json(contract_path, contract)
    files = SOURCES + [
        f"{STAGE_REL}/parameter-scan.run_spec.json", f"{STAGE_REL}/stage_b_r2_source_hashes.sha256",
        f"{STAGE_REL}/stage-b-action-plan.json", f"{STAGE_REL}/launch-contract.json",
    ]
    write_json(STAGE / "server_upload_manifest.json", {
        "schema_version": 1, "target": "/home/wangjieren/code/1x5_Heisenberg_Pentamer",
        "mode": "offline_upload_only", "launch_ready": True, "stage_a_complete": True,
        "r1_failure_validated": True, "stage": "B-R2-coarse-96", "cell_count": 96,
        "concurrency": 1, "stop_on_first_failure": True, "eta_hours": {"low": 18, "high": 32},
        "remote_git_pull": False,
        "files": [{"path": name, "sha256": sha256(ROOT / name), "bytes": (ROOT / name).stat().st_size}
                  for name in files],
    })
    print(json.dumps({"status": "pass", "cells": 96, "budget_counts": contract["budget_counts"],
                      "first_cell_budget": 64, "eta_hours": [18, 32]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
