#!/usr/bin/env python3
"""生成 Stage B 六条 beta 切片的96单元粗扫描。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUN_REL = "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha"
RUN = ROOT / RUN_REL
PHASE = RUN / "phase-diagram-v2"
STAGE_REL = f"{RUN_REL}/stage-b-negative-coarse-r1-96"
STAGE = ROOT / STAGE_REL
SUMMARY = PHASE / "r19_success_ingestion_summary.json"
ANALYSIS = PHASE / "stage_a_finite_size_diagnostic_latest.json"
CALIBRATION = PHASE / "accepted_calibration_through_r19.json"
OBSERVATIONS = PHASE / "observations.json"
ACTION_INDEX = PHASE / "action_index.json"
STANDARD = ROOT / "docs/full_phase_diagram_negative_standard_20260809.md"
CAMPAIGN = RUN / "campaign-plan.json"
POLICY = PHASE / "phase-policy.json"
LAUNCHER = "scripts/autoresearch_v5/launch_negative_phase_stage_b_r1_96.sh"
ALPHAS = [-1.0, -0.75, -0.5, -0.35, -0.25, -0.1, -0.05, -0.025]
BETAS = [0.05, 0.1, 0.25, 0.75, 0.9, 1.0]
LENGTHS = [40, 60]
SOURCES = [
    "Project.toml", "Manifest.toml", "docs/full_phase_diagram_negative_standard_20260809.md",
    "src/PentamerChain.jl", "src/hamiltonian.jl", "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py", "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py",
    "scripts/autoresearch_v5/validate_negative_phase_run.py", LAUNCHER,
]


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: Any) -> None:
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


def token(value: float) -> str:
    return f"{round(abs(value) * 1000):04d}"


def action_id(alpha: float, beta: float, length: int) -> str:
    payload = json.dumps(["stage-b-r1", alpha, beta, length], separators=(",", ":"))
    return "act-" + hashlib.sha256(payload.encode()).hexdigest()[:20]


def budget(alpha: float) -> int:
    return 32 if alpha <= -0.5 else 64


def build_cells() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cells, actions = [], []
    for beta in BETAS:
        for alpha in ALPHAS:
            for length in LENGTHS:
                units = length // 5
                cell_id = f"negb1-a{token(alpha)}-b{token(beta)}-L{length:03d}"
                action = action_id(alpha, beta, length)
                cell_budget = budget(alpha)
                cells.append({
                    "cell_id": cell_id,
                    "params": {"alpha": alpha, "beta": beta, "L": length, "n_units": units},
                    "budget": cell_budget, "stage": "B-R1-coarse-96",
                    "controller_action_id": action, "calibration_only": False,
                    "budget_rationale": "深负区32 sweeps；alpha>-0.5按Stage A收敛经验预升至64",
                })
                actions.append({
                    "action_id": action, "lifecycle_state": "PLANNED",
                    "params": {"L": length, "alpha": alpha, "beta": beta},
                    "budget": cell_budget, "observation_status": "pending",
                    "accepted": False, "artifact": f"{STAGE_REL}/cells/{cell_id}/manifest.json",
                })
    return cells, actions


def main() -> int:
    outputs = [STAGE / name for name in (
        "parameter-scan.run_spec.json", "stage_b_source_hashes.sha256",
        "launch-contract.json", "stage-b-action-plan.json", "server_upload_manifest.json",
    )]
    if any(path.exists() for path in outputs):
        raise ValueError("Stage B launch-ready 文件已存在，拒绝覆盖")
    required = (SUMMARY, ANALYSIS, CALIBRATION, OBSERVATIONS, ACTION_INDEX,
                STANDARD, CAMPAIGN, POLICY, ROOT / LAUNCHER)
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Stage B 等待 Stage A 终态: " + ", ".join(missing))

    summary, analysis = load(SUMMARY), load(ANALYSIS)
    campaign, policy = load(CAMPAIGN), load(POLICY)
    observations, actions_before = load(OBSERVATIONS), load(ACTION_INDEX)
    counts = {name: sum(row.get("status") == name for row in observations.get("records", []))
              for name in ("success", "failed", "pending")}
    if (
        summary.get("status") != "accepted_stage_a_complete"
        or summary.get("counts") != {"controller_success_total": 16, "controller_failed_total": 0,
                                     "controller_pending_total": 0, "calibration_accepted_total": 8}
        or analysis.get("status") != "complete"
        or analysis.get("decision", {}).get("stage_a_complete") is not True
        or analysis.get("decision", {}).get("stage_b_ready") is not True
        or analysis.get("decision", {}).get("phase_boundary_confirmed") is not False
        or counts != {"success": 16, "failed": 0, "pending": 0}
        or len(load(CALIBRATION).get("records", [])) != 8
        or sha256(OBSERVATIONS) != summary["observations"]["sha256"]
        or sha256(ACTION_INDEX) != summary["action_index"]["sha256"]
        or sha256(CALIBRATION) != summary["accepted_calibration"]["sha256"]
        or campaign.get("stages", [None, None])[1].get("cells") != 96
        or policy.get("axes", {}).get("slice", {}).get("values") != [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]
    ):
        raise ValueError("Stage A 尚未满足 Stage B 释放门")

    cells, actions = build_cells()
    if len(cells) != 96 or len(actions) != 96 or len({row["cell_id"] for row in cells}) != 96:
        raise ValueError("Stage B cell 生成异常")
    existing_ids = {row["action_id"] for row in actions_before.get("actions", [])}
    if existing_ids & {row["action_id"] for row in actions}:
        raise ValueError("Stage B action_id 与既有控制器冲突")

    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    run_spec = {
        "schema_version": 1, "run_id": "pentamer-negative-phase-stage-b-r1-96-20260812",
        "scope": "Stage B six beta slices; 8 negative alpha x L40/L60; Fig.9 excluded",
        "controller": "local_only", "cells": cells,
        "settings": {
            "method": "finite_dmrg_multistart_fullq", "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"], "maxdim_by_L": {"40": 800, "60": 1000},
            "nsweeps": 32, "cutoff": 1e-11, "threads": 8, "q_count": 401,
            "init_modes": ["center", "ferro_j2"],
            "acceptance": {"variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9,
                           "sector_tolerance": 1e-8, "spin_gap_min": -1e-8,
                           "nonnegative_gap_required": True, "q_count_min": 401},
            "offline": True, "execution": "direct SSH; concurrency=1; stop on first failed cell",
        },
        "provenance": {
            "negative_alpha_included": True, "stage_a_complete": True,
            "r19_success_summary_sha256": sha256(SUMMARY),
            "stage_a_analysis_sha256": sha256(ANALYSIS),
            "accepted_calibration_through_r19_sha256": sha256(CALIBRATION),
            "observations_sha256": sha256(OBSERVATIONS), "action_index_sha256": sha256(ACTION_INDEX),
            "campaign_plan_sha256": sha256(CAMPAIGN), "phase_policy_sha256": sha256(POLICY),
            "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                             capture_output=True, text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes, "boundary_thresholds_relaxed": False,
            "r16_practical_boundary_ineligible_preserved": True,
            "exploratory_data_not_accepted": True,
        },
    }
    STAGE.mkdir(parents=True, exist_ok=True)
    spec_path = STAGE / "parameter-scan.run_spec.json"
    hashes_path = STAGE / "stage_b_source_hashes.sha256"
    action_plan = STAGE / "stage-b-action-plan.json"
    write_json(spec_path, run_spec)
    write_json(action_plan, {"schema_version": 1, "stage": "B-R1-coarse-96",
                             "canonical_action_index_mutated": False, "actions": actions})
    with hashes_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    contract = {
        "schema_version": 1, "launch_ready": True, "stage_a_complete": True,
        "cell_count": 96, "controller_cell_count": 96, "concurrency": 1,
        "stop_on_first_failure": True, "offline": True,
        "eta_hours": {"low": 18, "high": 32},
        "budget_counts": {"32": sum(row["budget"] == 32 for row in cells),
                          "64": sum(row["budget"] == 64 for row in cells)},
        "run_spec_sha256": sha256(spec_path), "source_hashes_sha256": sha256(hashes_path),
        "action_plan_sha256": sha256(action_plan), "standard_sha256": sha256(STANDARD),
        "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "stage_a_analysis_sha256": sha256(ANALYSIS),
        "history_evidence_preserved": True, "gap_gate_enforced": True,
        "boundary_thresholds_relaxed": False,
    }
    contract_path = STAGE / "launch-contract.json"
    write_json(contract_path, contract)
    files = SOURCES + [f"{STAGE_REL}/parameter-scan.run_spec.json",
                       f"{STAGE_REL}/stage_b_source_hashes.sha256",
                       f"{STAGE_REL}/stage-b-action-plan.json", f"{STAGE_REL}/launch-contract.json"]
    entries = [{"path": name, "sha256": sha256(ROOT / name), "bytes": (ROOT / name).stat().st_size}
               for name in files]
    write_json(STAGE / "server_upload_manifest.json", {
        "schema_version": 1, "target": "/home/wangjieren/code/1x5_Heisenberg_Pentamer",
        "mode": "offline_upload_only", "launch_ready": True, "stage_a_complete": True,
        "negative_alpha_included": True, "stage": "B-R1-coarse-96", "cell_count": 96,
        "concurrency": 1, "stop_on_first_failure": True, "eta_hours": {"low": 18, "high": 32},
        "remote_git_pull": False, "files": entries,
    })
    print(json.dumps({"status": "pass", "cells": 96, "eta_hours": [18, 32],
                      "budget_counts": contract["budget_counts"], "upload_files": len(entries)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
