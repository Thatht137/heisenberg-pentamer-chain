#!/usr/bin/env python3
"""生成负 alpha 阶段 A R1 的离线 run spec。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v5_20260809" / "round44_phase_diagram_full_alpha"
STAGE = RUN / "stage-a-beta050-calibration-r1"
STANDARD = ROOT / "docs" / "full_phase_diagram_negative_standard_20260809.md"
ORIGINAL_SPEC = RUN / "stage-a-beta050-calibration" / "parameter-scan.run_spec.json"
ALPHAS = [-1.0, -0.75, -0.5, -0.35, -0.25, -0.1, -0.05, -0.025]
LENGTHS = [40, 60, 80]
SOURCE_FILES = [
    "Project.toml",
    "Manifest.toml",
    "docs/full_phase_diagram_negative_standard_20260809.md",
    "src/PentamerChain.jl",
    "src/hamiltonian.jl",
    "src/order_parameters.jl",
    "scripts/autoresearch_v5/progress.py",
    "scripts/autoresearch_v5/negative_static_cell.jl",
    "scripts/autoresearch_v5/run_negative_static_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_cell.py",
    "scripts/autoresearch_v5/run_negative_phase_structure_batch.py",
    "scripts/autoresearch_v5/validate_negative_phase_run.py",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def label(value: float) -> str:
    return f"{abs(value):.3f}".replace(".", "")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-generated", action="store_true")
    args = parser.parse_args()
    run_spec_path = STAGE / "parameter-scan.run_spec.json"
    source_hashes_path = STAGE / "r1_source_hashes.sha256"
    if run_spec_path.exists() and not args.refresh_generated:
        raise SystemExit(f"拒绝覆盖既有 R1 run spec: {run_spec_path}")
    if args.refresh_generated:
        forbidden = [STAGE / "run_status.json", STAGE / "run.json"]
        cells_dir = STAGE / "cells"
        if any(path.exists() for path in forbidden) or (cells_dir.exists() and any(cells_dir.iterdir())):
            raise SystemExit("R1 已有提交或 cell 证据，拒绝刷新")
    original = json.loads(ORIGINAL_SPEC.read_text(encoding="utf-8"))
    original_cells = {
        (float(cell["params"]["alpha"]), float(cell["params"]["beta"]), int(cell["params"]["L"])): cell
        for cell in original["cells"]
    }
    code_hashes = {relative: sha256(ROOT / relative) for relative in SOURCE_FILES}
    cells = []
    for alpha in ALPHAS:
        for length in LENGTHS:
            budget = 64 if length == 80 else 32
            original_cell = original_cells.get((alpha, 0.5, length))
            if original_cell is None:
                raise SystemExit(f"原 Stage A 缺少 action 对应点: alpha={alpha}, L={length}")
            cells.append({
                "cell_id": f"nega-r1-a{label(alpha)}-b0500-L{length:03d}",
                "params": {"alpha": alpha, "beta": 0.5, "L": length, "n_units": length // 5},
                "budget": budget,
                "stage": "A-R1",
                "retry_policy": "L80 仅此轮 32->64；L40/L60 保持 32",
                "controller_action_id": original_cell.get("controller_action_id"),
                "calibration_only": bool(original_cell.get("calibration_only")),
            })
    run_spec = {
        "schema_version": 1,
        "run_id": "pentamer-negative-phase-stage-a-r1-20260809",
        "scope": "-1<=alpha<0, beta=0.5, L=40/60/80; static phase diagnostics; Fig.9 excluded",
        "controller": "local_only",
        "cells": cells,
        "settings": {
            "method": "finite_dmrg_multistart_fullq",
            "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"],
            "maxdim_by_L": {"40": 800, "60": 1000, "80": 1200},
            "nsweeps": 32,
            "cutoff": 1e-11,
            "threads": 8,
            "q_count": 401,
            "init_modes": ["center", "ferro_j2"],
            "budget_definition": "每个独立初态的 sweeps；仅 L80 使用 64",
            "acceptance": {
                "variance_per_site_max": 1e-8,
                "final_truncation_error_max": 1e-9,
                "sector_tolerance": 1e-8,
                "q_count_min": 401,
            },
            "offline": True,
            "execution": "direct SSH; concurrency=1; stop on first failed cell",
        },
        "provenance": {
            "negative_alpha_included": True,
            "r1_reason": "修复 Julia full-q CSV 字面反斜杠换行后独立重跑",
            "standard_sha256": sha256(STANDARD),
            "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
            "code_sha256": code_hashes,
            "exploratory_data_not_accepted": True,
        },
    }
    write_json(run_spec_path, run_spec)
    with source_hashes_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(f"{digest}  {relative}\n" for relative, digest in code_hashes.items()))
    print(json.dumps({"run_spec": str(run_spec_path), "source_hashes": str(source_hashes_path), "cells": len(cells)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
