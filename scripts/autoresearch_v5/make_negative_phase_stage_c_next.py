#!/usr/bin/env python3
"""把 Stage C 再二分动作组装为离线计算包。"""

from __future__ import annotations

import argparse
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
STANDARD = ROOT / "docs/full_phase_diagram_negative_standard_20260809.md"
LAUNCHER = "scripts/autoresearch_v5/launch_negative_phase_stage_c_next.sh"
SOURCES = [
    "Project.toml", "Manifest.toml", "docs/full_phase_diagram_negative_standard_20260809.md",
    "src/PentamerChain.jl", "src/hamiltonian.jl", "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py", "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py",
    "scripts/autoresearch_v5/validate_negative_phase_run.py", LAUNCHER,
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--stage-b-summary", type=Path, required=True)
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


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
    args = parse_args()
    if args.round < 2:
        raise ValueError("再二分 round 必须 >=2")
    analysis_path, summary_path = args.analysis.resolve(), args.stage_b_summary.resolve()
    for path in (analysis_path, summary_path, STANDARD, ROOT / LAUNCHER):
        if not path.is_file():
            raise FileNotFoundError(path)
    analysis, summary = load(analysis_path), load(summary_path)
    actions = analysis.get("next_actions", [])
    if (
        analysis.get("status") != "refinement_required" or not actions
        or analysis.get("round") != args.round - 1
        or analysis.get("decision", {}).get("boundary_thresholds_relaxed") is not False
        or summary.get("status") != "accepted_stage_b_complete"
        or len({row["action_id"] for row in actions}) != len(actions)
        or len({(row["params"]["alpha"], row["params"]["beta"], row["params"]["L"])
                for row in actions}) != len(actions)
    ):
        raise ValueError("Stage C 再二分释放证据不匹配")
    stage = (args.output_dir.resolve() if args.output_dir
             else ROOT / f"{RUN_REL}/stage-c-negative-refine-r{args.round}")
    try:
        stage_rel = stage.relative_to(ROOT).as_posix()
    except ValueError as exc:
        raise ValueError("输出目录必须位于项目内") from exc
    outputs = [stage / name for name in ("parameter-scan.run_spec.json",
                                          "stage_c_source_hashes.sha256",
                                          "launch-contract.json", "server_upload_manifest.json")]
    if any(path.exists() for path in outputs):
        raise FileExistsError("Stage C 再二分文件已存在，拒绝覆盖")
    cells = []
    for row in actions:
        params = row["params"]
        cells.append({
            "cell_id": f"negc{args.round}-a{token(params['alpha'])}-b{token(params['beta'])}-L{int(params['L']):03d}",
            "params": params, "budget": int(row["budget"]),
            "stage": f"C-R{args.round}-refine", "controller_action_id": row["action_id"],
            "reason": row["reason"], "boundary_thresholds_relaxed": False,
        })
    code_hashes = {name: sha256(ROOT / name) for name in SOURCES}
    source_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   capture_output=True, text=True, check=True).stdout.strip()
    run_spec = {
        "schema_version": 1, "run_id": f"pentamer-negative-phase-stage-c-r{args.round}-20260812",
        "scope": "guard-authorized negative-alpha bisection only; Fig.9 excluded",
        "controller": "local_only", "cells": cells,
        "settings": {
            "method": "finite_dmrg_multistart_fullq", "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"], "maxdim_by_L": {"60": 1000, "80": 1200},
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
            "stage_b_summary_sha256": sha256(summary_path),
            "parent_analysis_sha256": sha256(analysis_path),
            "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"), "source_commit": source_commit,
            "code_sha256": code_hashes, "boundary_thresholds_relaxed": False,
            "phase_label_assigned": False, "exploratory_data_not_accepted": True,
        },
    }
    stage.mkdir(parents=True, exist_ok=True)
    spec_path, hashes_path = outputs[0], outputs[1]
    write_json(spec_path, run_spec)
    with hashes_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("".join(f"{digest}  {name}\n" for name, digest in code_hashes.items()))
    eta_low = round(max(0.5, len(cells) * 0.15), 1)
    eta_high = round(max(1.5, len(cells) * 0.35), 1)
    contract = {
        "schema_version": 1, "launch_ready": True, "stage_b_complete": True,
        "round": args.round, "cell_count": len(cells), "concurrency": 1,
        "stop_on_first_failure": True, "offline": True,
        "eta_hours_low": eta_low, "eta_hours_high": eta_high,
        "run_spec_sha256": sha256(spec_path), "source_hashes_sha256": sha256(hashes_path),
        "parent_analysis_sha256": sha256(analysis_path),
        "standard_sha256": sha256(STANDARD), "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "source_commit": f"uploaded-negative-stage-c-r{args.round}-20260812",
        "boundary_thresholds_relaxed": False,
    }
    write_json(outputs[2], contract)
    files = SOURCES + [f"{stage_rel}/parameter-scan.run_spec.json",
                       f"{stage_rel}/stage_c_source_hashes.sha256",
                       f"{stage_rel}/launch-contract.json"]
    entries = [{"path": name, "sha256": sha256(ROOT / name), "bytes": (ROOT / name).stat().st_size}
               for name in files]
    write_json(outputs[3], {
        "schema_version": 1, "target": "/home/wangjieren/code/1x5_Heisenberg_Pentamer",
        "mode": "offline_upload_only", "launch_ready": True, "stage_b_complete": True,
        "negative_alpha_included": True, "stage": f"C-R{args.round}-refine",
        "run_rel": stage_rel, "cell_count": len(cells), "concurrency": 1,
        "stop_on_first_failure": True, "eta_hours": {"low": eta_low, "high": eta_high},
        "remote_git_pull": False, "files": entries,
    })
    print(json.dumps({"status": "pass", "round": args.round, "cells": len(cells),
                      "eta_hours": [eta_low, eta_high], "upload_files": len(entries)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
