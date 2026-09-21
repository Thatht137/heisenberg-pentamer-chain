#!/usr/bin/env python3
"""把 Practical V2 的 Stage C 动作组装为离线计算包。"""

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
STAGE_NAME = "stage-c-negative-refine-practical-v2-r1"
STAGE_REL = f"{RUN_REL}/{STAGE_NAME}"
STAGE = ROOT / STAGE_REL
ANALYSIS = PHASE / "stage_b_practical_v2_cross_slice_diagnostic_v2.json"
SUMMARY = PHASE / "stage_b_practical_v2_completion_summary.json"
ACCEPTED = PHASE / "stage_b_practical_v2_accepted_index_final.json"
BOUNDED = PHASE / "stage_b_practical_v2_bounded_records_final.json"
STANDARD = ROOT / "docs/negative_alpha_practical_convergence_standard_20260829.md"
LAUNCHER = "scripts/autoresearch_v5/launch_negative_phase_stage_c_practical_v2_r1.sh"
SOURCES = [
    "Project.toml", "Manifest.toml",
    "docs/full_phase_diagram_negative_standard_20260809.md",
    "docs/negative_alpha_practical_convergence_standard_20260829.md",
    "src/PentamerChain.jl", "src/hamiltonian.jl", "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py", "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py",
    "scripts/autoresearch_v5/validate_negative_phase_run_practical_v2.py", LAUNCHER,
]


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"拒绝覆盖: {path}")
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
    return f"{round(abs(value) * 10000):05d}"


def main() -> int:
    for path in (ANALYSIS, SUMMARY, ACCEPTED, BOUNDED, STANDARD, ROOT / LAUNCHER):
        if not path.is_file():
            raise FileNotFoundError(path)
    if STAGE.exists():
        raise FileExistsError(STAGE)
    analysis, summary = load(ANALYSIS), load(SUMMARY)
    actions = analysis.get("stage_c_actions", [])
    if (
        analysis.get("status") != "action_required"
        or not actions
        or summary.get("status") != "accepted_stage_b_complete_with_bounded"
        or summary.get("counts") != {"grid": 96, "accepted": 89, "bounded": 7, "pending": 0}
        or analysis.get("inputs", {}).get("stage_b_summary", {}).get("sha256") != sha256(SUMMARY)
        or analysis.get("inputs", {}).get("accepted_index", {}).get("sha256") != sha256(ACCEPTED)
        or analysis.get("inputs", {}).get("bounded_records", {}).get("sha256") != sha256(BOUNDED)
        or analysis.get("decision", {}).get("boundary_thresholds_relaxed") is not False
    ):
        raise ValueError("Stage C guard 与 Practical V2 终态证据不匹配")
    keys = {(float(row["params"]["beta"]), float(row["params"]["alpha"]), int(row["params"]["L"]))
            for row in actions}
    if len(keys) != len(actions) or any(int(row["budget"]) != 64 for row in actions):
        raise ValueError("Stage C 动作重复或超过64 sweeps")
    if any(int(row["params"]["L"]) not in (60, 80) for row in actions):
        raise ValueError("Stage C 只允许 L60/L80")

    cells = []
    for row in actions:
        params = row["params"]
        cells.append({
            "cell_id": f"negc-v2-r1-a{token(params['alpha'])}-b{token(params['beta'])}-L{int(params['L']):03d}",
            "params": params, "budget": 64, "stage": "C-R1-practical-v2-refine",
            "controller_action_id": row["action_id"], "reason": row["reason"],
            "boundary_thresholds_relaxed": False,
        })
    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    spec = {
        "schema_version": 1,
        "run_id": "pentamer-negative-phase-stage-c-practical-v2-r1-20260908",
        "scope": "accepted-only negative-alpha boundary refinement; Fig.9 excluded",
        "controller": "local_only", "cells": cells,
        "settings": {
            "method": "finite_dmrg_multistart_fullq", "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"], "maxdim_by_L": {"60": 1000, "80": 1200},
            "nsweeps": 64, "cutoff": 1e-11, "threads": 8, "q_count": 401,
            "init_modes": ["center", "ferro_j2"], "variance_per_site_max": 5e-8,
            "acceptance": {"variance_per_site_max": 5e-8, "final_truncation_error_max": 1e-9,
                           "sector_tolerance": 1e-8, "spin_gap_min": -1e-8,
                           "boundary_sigma": 2.0, "target_width": 0.025,
                           "final_size_pair": [60, 80]},
            "offline": True,
            "execution": "direct SSH; concurrency=1; stop on first failed cell; max sweeps=64",
        },
        "provenance": {
            "negative_alpha_included": True, "stage_b_complete": True,
            "practical_v2": True, "max_sweeps": 64,
            "stage_b_summary_sha256": sha256(SUMMARY), "stage_b_analysis_sha256": sha256(ANALYSIS),
            "accepted_index_sha256": sha256(ACCEPTED), "bounded_records_sha256": sha256(BOUNDED),
            "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                             capture_output=True, text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes, "boundary_thresholds_relaxed": False,
            "phase_label_assigned": False, "bounded_points_excluded": True,
        },
    }
    STAGE.mkdir(parents=True)
    spec_out = STAGE / "parameter-scan.run_spec.json"
    hashes_out = STAGE / "stage_c_source_hashes.sha256"
    write_json(spec_out, spec)
    with hashes_out.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    contract = {
        "schema_version": 1, "launch_ready": True, "stage_b_complete": True,
        "practical_v2": True, "cell_count": len(cells), "concurrency": 1,
        "stop_on_first_failure": True, "offline": True, "max_sweeps": 64,
        "eta_hours": {"low": 14, "high": 28}, "variance_per_site_max": 5e-8,
        "boundary_thresholds_relaxed": False, "run_spec_sha256": sha256(spec_out),
        "source_hashes_sha256": sha256(hashes_out), "standard_sha256": sha256(STANDARD),
        "manifest_sha256": sha256(ROOT / "Manifest.toml"), "analysis_sha256": sha256(ANALYSIS),
    }
    contract_out = STAGE / "launch-contract.json"
    write_json(contract_out, contract)
    files = SOURCES + [f"{STAGE_REL}/parameter-scan.run_spec.json",
                       f"{STAGE_REL}/stage_c_source_hashes.sha256", f"{STAGE_REL}/launch-contract.json"]
    write_json(STAGE / "server_upload_manifest.json", {
        "schema_version": 1, "target": "/home/wangjieren/code/1x5_Heisenberg_Pentamer",
        "mode": "offline_upload_only", "launch_ready": True, "stage_b_complete": True,
        "practical_v2": True, "stage": "C-R1-practical-v2-refine", "stage_directory": STAGE_NAME,
        "cell_count": len(cells), "concurrency": 1, "stop_on_first_failure": True,
        "eta_hours": {"low": 14, "high": 28},
        "files": [{"path": name, "sha256": sha256(ROOT / name), "bytes": (ROOT / name).stat().st_size}
                  for name in files],
    })
    print(json.dumps({"status": "pass", "stage": STAGE_NAME, "cells": len(cells),
                      "eta_hours": [14, 28], "upload_files": len(files)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
