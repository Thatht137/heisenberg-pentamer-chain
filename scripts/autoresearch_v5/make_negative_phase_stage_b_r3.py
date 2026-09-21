#!/usr/bin/env python3
"""生成 Stage B R3：L60升至64 sweeps并续跑剩余95点。"""

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
R2 = RUN / "stage-b-negative-coarse-r2-96"
STAGE_REL = f"{RUN_REL}/stage-b-negative-coarse-r3-remaining95"
STAGE = ROOT / STAGE_REL
LAUNCHER = "scripts/autoresearch_v5/launch_negative_phase_stage_b_r3_remaining95.sh"
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
            stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True); raise


def main() -> int:
    outputs = [STAGE / name for name in ("parameter-scan.run_spec.json", "stage_b_r3_source_hashes.sha256",
               "launch-contract.json", "stage-b-action-plan.json", "server_upload_manifest.json")]
    if any(path.exists() for path in outputs):
        raise FileExistsError("Stage B R3 文件已存在")
    spec2_path = R2 / "parameter-scan.run_spec.json"
    plan2_path = R2 / "stage-b-action-plan.json"
    summary2_path = PHASE / "stage_b_r2_terminal_summary.json"
    spec2, plan2, summary2 = map(load, (spec2_path, plan2_path, summary2_path))
    if (summary2.get("counts") != {"success": 1, "failed": 1, "pending": 94}
            or summary2.get("pass_cells") != ["negb2-a1000-b0050-L040"]
            or summary2.get("failed_cells") != ["negb2-a1000-b0050-L060"]
            or summary2.get("failed_records_contain_value_or_error") is not False):
        raise ValueError("R2终态基线不匹配")
    cells = []
    for original in spec2["cells"][1:]:
        cell = json.loads(json.dumps(original))
        cell["cell_id"] = cell["cell_id"].replace("negb2-", "negb3-")
        cell["stage"] = "B-R3-coarse-remaining95"
        cell["r2_cell_id"] = original["cell_id"]
        if original["cell_id"] == "negb2-a1000-b0050-L060":
            cell["budget"] = 64
            cell["budget_rationale"] = "R2双初态Sz0/Sz1方差超门；按32→64重试"
        cells.append(cell)
    if len(cells) != 95 or cells[0]["budget"] != 64:
        raise ValueError("R3 cells异常")
    actions2 = {row["action_id"]: row for row in plan2["actions"]}
    actions = []
    for cell in cells:
        action = json.loads(json.dumps(actions2[cell["controller_action_id"]]))
        action.update({"lifecycle_state": "PLANNED", "observation_status": "pending", "accepted": False,
                       "budget": cell["budget"], "artifact": f"{STAGE_REL}/cells/{cell['cell_id']}/manifest.json"})
        actions.append(action)
    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    spec = json.loads(json.dumps(spec2))
    spec.update({"run_id": "pentamer-negative-phase-stage-b-r3-remaining95-20260812",
                 "scope": "Stage B R3 remaining95; failed L60 promoted 32 to 64", "cells": cells})
    spec["provenance"].update({"stage_b_r2_terminal_summary_sha256": sha256(summary2_path),
                               "stage_b_r2_run_spec_sha256": sha256(spec2_path),
                               "prior_accepted_cells": ["negb2-a1000-b0050-L040"],
                               "retry_policy": "failed L60 32->64; remaining cells retain budgets",
                               "code_sha256": code_hashes, "boundary_thresholds_relaxed": False})
    plan = {"schema_version": 1, "stage": "B-R3-coarse-remaining95",
            "canonical_action_index_mutated": False, "actions": actions}
    STAGE.mkdir(parents=True, exist_ok=True)
    spec_path, plan_path = STAGE / "parameter-scan.run_spec.json", STAGE / "stage-b-action-plan.json"
    hashes_path = STAGE / "stage_b_r3_source_hashes.sha256"
    write_json(spec_path, spec); write_json(plan_path, plan)
    with hashes_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    counts = {"32": sum(c["budget"] == 32 for c in cells), "64": sum(c["budget"] == 64 for c in cells)}
    contract = {"schema_version": 1, "launch_ready": True, "stage_a_complete": True,
                "r2_failure_validated": True, "cell_count": 95, "concurrency": 1,
                "stop_on_first_failure": True, "offline": True, "eta_hours": {"low": 18, "high": 32},
                "budget_counts": counts, "run_spec_sha256": sha256(spec_path),
                "source_hashes_sha256": sha256(hashes_path), "action_plan_sha256": sha256(plan_path),
                "r2_terminal_summary_sha256": sha256(summary2_path), "boundary_thresholds_relaxed": False}
    contract_path = STAGE / "launch-contract.json"; write_json(contract_path, contract)
    files = SOURCES + [f"{STAGE_REL}/parameter-scan.run_spec.json", f"{STAGE_REL}/stage_b_r3_source_hashes.sha256",
                       f"{STAGE_REL}/stage-b-action-plan.json", f"{STAGE_REL}/launch-contract.json"]
    write_json(STAGE / "server_upload_manifest.json", {"schema_version": 1,
        "target": "/home/wangjieren/code/1x5_Heisenberg_Pentamer", "mode": "offline_upload_only",
        "launch_ready": True, "r2_failure_validated": True, "stage": "B-R3-coarse-remaining95",
        "cell_count": 95, "concurrency": 1, "stop_on_first_failure": True,
        "eta_hours": {"low": 18, "high": 32}, "remote_git_pull": False,
        "files": [{"path": name, "sha256": sha256(ROOT / name), "bytes": (ROOT / name).stat().st_size}
                  for name in files]})
    print(json.dumps({"status": "pass", "cells": 95, "budget_counts": counts, "eta_hours": [18, 32]}, ensure_ascii=False))
    return 0


if __name__ == "__main__": raise SystemExit(main())
