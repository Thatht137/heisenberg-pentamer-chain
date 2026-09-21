#!/usr/bin/env python3
"""把本地 Stage C guard 动作组装为离线计算包。"""

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
STAGE_REL = f"{RUN_REL}/stage-c-negative-refine-r1"
STAGE = ROOT / STAGE_REL
ANALYSIS = PHASE / "stage_b_cross_slice_diagnostic.json"
STAGE_B_SUMMARY = PHASE / "stage_b_r1_terminal_summary.json"
STANDARD = ROOT / "docs/full_phase_diagram_negative_standard_20260809.md"
CAMPAIGN = RUN / "campaign-plan.json"
POLICY = PHASE / "phase-policy.json"
LAUNCHER = "scripts/autoresearch_v5/launch_negative_phase_stage_c_r1.sh"
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


def main() -> int:
    outputs = [STAGE / name for name in ("parameter-scan.run_spec.json", "stage_c_source_hashes.sha256",
                                         "launch-contract.json", "server_upload_manifest.json")]
    if any(path.exists() for path in outputs):
        raise FileExistsError("Stage C launch-ready 文件已存在，拒绝覆盖")
    for path in (ANALYSIS, STAGE_B_SUMMARY, STANDARD, CAMPAIGN, POLICY, ROOT / LAUNCHER):
        if not path.is_file():
            raise FileNotFoundError("Stage C 等待 Stage B 终态: " + str(path))
    analysis, summary = load(ANALYSIS), load(STAGE_B_SUMMARY)
    actions = analysis.get("stage_c_actions", [])
    if (
        analysis.get("status") != "action_required" or not actions
        or analysis.get("decision", {}).get("phase_boundary_confirmed") is not False
        or analysis.get("decision", {}).get("boundary_thresholds_relaxed") is not False
        or summary.get("status") != "accepted_stage_b_complete"
        or summary.get("stage_c_ready") is not True
        or analysis.get("inputs", {}).get("stage_b_summary", {}).get("sha256") != sha256(STAGE_B_SUMMARY)
        or len({item["action_id"] for item in actions}) != len(actions)
        or len({(item["params"]["beta"], item["params"]["alpha"], item["params"]["L"])
                for item in actions}) != len(actions)
    ):
        raise ValueError("Stage C guard 或 Stage B 完成证据不匹配")
    cells = []
    for item in actions:
        params = item["params"]
        cells.append({
            "cell_id": f"negc1-a{token(params['alpha'])}-b{token(params['beta'])}-L{int(params['L']):03d}",
            "params": params, "budget": int(item["budget"]), "stage": "C-R1-refine",
            "controller_action_id": item["action_id"], "reason": item["reason"],
            "boundary_thresholds_relaxed": False,
        })
    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    run_spec = {
        "schema_version": 1, "run_id": "pentamer-negative-phase-stage-c-r1-20260812",
        "scope": "guard-authorized negative-alpha refinement only; Fig.9 excluded",
        "controller": "local_only", "cells": cells,
        "settings": {
            "method": "finite_dmrg_multistart_fullq", "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"], "maxdim_by_L": {"40": 800, "60": 1000, "80": 1200},
            "nsweeps": 64, "cutoff": 1e-11, "threads": 8, "q_count": 401,
            "init_modes": ["center", "ferro_j2"],
            "acceptance": {"variance_per_site_max": 1e-8, "final_truncation_error_max": 1e-9,
                           "sector_tolerance": 1e-8, "spin_gap_min": -1e-8,
                           "boundary_sigma": 2.0, "target_width": 0.025,
                           "final_size_pair": [60, 80]},
            "offline": True, "execution": "direct SSH; concurrency=1; stop on first failed cell",
        },
        "provenance": {
            "negative_alpha_included": True, "stage_b_complete": True,
            "stage_b_summary_sha256": sha256(STAGE_B_SUMMARY),
            "stage_b_analysis_sha256": sha256(ANALYSIS),
            "campaign_plan_sha256": sha256(CAMPAIGN), "phase_policy_sha256": sha256(POLICY),
            "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                             capture_output=True, text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes, "boundary_thresholds_relaxed": False,
            "phase_label_assigned": False, "exploratory_data_not_accepted": True,
        },
    }
    STAGE.mkdir(parents=True, exist_ok=True)
    spec_path = STAGE / "parameter-scan.run_spec.json"
    hashes_path = STAGE / "stage_c_source_hashes.sha256"
    write_json(spec_path, run_spec)
    hashes_path.write_text("".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()),
                           encoding="utf-8")
    contract = {
        "schema_version": 1, "launch_ready": True, "stage_b_complete": True,
        "cell_count": len(cells), "concurrency": 1, "stop_on_first_failure": True,
        "offline": True, "eta_hours": {"low": 8, "high": 24},
        "run_spec_sha256": sha256(spec_path), "source_hashes_sha256": sha256(hashes_path),
        "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "stage_b_analysis_sha256": sha256(ANALYSIS), "boundary_thresholds_relaxed": False,
    }
    contract_path = STAGE / "launch-contract.json"
    write_json(contract_path, contract)
    files = SOURCES + [f"{STAGE_REL}/parameter-scan.run_spec.json",
                       f"{STAGE_REL}/stage_c_source_hashes.sha256", f"{STAGE_REL}/launch-contract.json"]
    entries = [{"path": name, "sha256": sha256(ROOT / name), "bytes": (ROOT / name).stat().st_size}
               for name in files]
    write_json(STAGE / "server_upload_manifest.json", {
        "schema_version": 1, "target": "/home/wangjieren/code/1x5_Heisenberg_Pentamer",
        "mode": "offline_upload_only", "launch_ready": True, "stage_b_complete": True,
        "negative_alpha_included": True, "stage": "C-R1-refine", "cell_count": len(cells),
        "concurrency": 1, "stop_on_first_failure": True, "eta_hours": {"low": 8, "high": 24},
        "remote_git_pull": False, "files": entries,
    })
    print(json.dumps({"status": "pass", "cells": len(cells), "eta_hours": [8, 24],
                      "upload_files": len(entries)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
