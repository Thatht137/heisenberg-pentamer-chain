#!/usr/bin/env python3
"""生成负 alpha 阶段 A 的 R2 单元重试包。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v5_20260809" / "round44_phase_diagram_full_alpha"
STAGE = RUN / "stage-a-beta050-calibration-r2-a0350-L060"
R1_SPEC = RUN / "stage-a-beta050-calibration-r1" / "parameter-scan.run_spec.json"
R1_VALIDATION = RUN / "fetches" / "stage-a-beta050-calibration-r1-20260810-1113" / "validation" / "nega-r1-a0350-b0500-L060.json"
STANDARD = ROOT / "docs" / "full_phase_diagram_negative_standard_20260809.md"
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-generated", action="store_true")
    args = parser.parse_args()
    run_spec_path = STAGE / "parameter-scan.run_spec.json"
    source_hashes_path = STAGE / "r2_source_hashes.sha256"
    if run_spec_path.exists() and not args.refresh_generated:
        raise SystemExit(f"拒绝覆盖既有 R2 run spec: {run_spec_path}")
    if args.refresh_generated:
        forbidden = [STAGE / "run_status.json", STAGE / "run.json", STAGE / "batch.pid"]
        cells_dir = STAGE / "cells"
        if any(path.exists() for path in forbidden) or (cells_dir.exists() and any(cells_dir.iterdir())):
            raise SystemExit("R2 已有提交或 cell 证据，拒绝刷新")

    r1_spec = json.loads(R1_SPEC.read_text(encoding="utf-8"))
    matches = [
        cell
        for cell in r1_spec["cells"]
        if float(cell["params"]["alpha"]) == -0.35
        and float(cell["params"]["beta"]) == 0.5
        and int(cell["params"]["L"]) == 60
    ]
    if len(matches) != 1:
        raise SystemExit("R1 中目标单元不唯一")
    r1_cell = matches[0]
    if r1_cell["cell_id"] != "nega-r1-a0350-b0500-L060" or int(r1_cell["budget"]) != 32:
        raise SystemExit("R1 目标单元合同与预期不符")

    validation = json.loads(R1_VALIDATION.read_text(encoding="utf-8"))
    if validation.get("status") != "fail" or validation.get("cell_id") != r1_cell["cell_id"]:
        raise SystemExit("R1 失败验收证据不匹配")
    if not any("variance/site sz0 超门" in item for item in validation.get("failures", [])):
        raise SystemExit("R1 失败原因不是声明的方差门")

    code_hashes = {relative: sha256(ROOT / relative) for relative in SOURCE_FILES}
    run_spec = {
        "schema_version": 1,
        "run_id": "pentamer-negative-phase-stage-a-r2-a0350-L060-20260810",
        "scope": "alpha=-0.35, beta=0.5, L=60; one-cell strict retry; Fig.9 excluded",
        "controller": "local_only",
        "cells": [
            {
                "cell_id": "nega-r2-a0350-b0500-L060",
                "params": {"alpha": -0.35, "beta": 0.5, "L": 60, "n_units": 12},
                "budget": 64,
                "stage": "A-R2",
                "retry_policy": "仅该失败单元 32->64 sweeps；门槛不变",
                "retry_of": r1_cell["cell_id"],
                "controller_action_id": r1_cell.get("controller_action_id"),
                "calibration_only": bool(r1_cell.get("calibration_only")),
            }
        ],
        "settings": {
            "method": "finite_dmrg_multistart_fullq",
            "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"],
            "maxdim_by_L": {"60": 1000},
            "nsweeps": 64,
            "cutoff": 1e-11,
            "threads": 8,
            "q_count": 401,
            "init_modes": ["center", "ferro_j2"],
            "budget_definition": "每个独立初态均为 64 sweeps",
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
            "r2_reason": "R1 双初态 Sz=0 方差/site 略高于 1e-8，按声明策略 32->64 单元重试",
            "retry_source_cell": r1_cell["cell_id"],
            "retry_source_validation_sha256": sha256(R1_VALIDATION),
            "standard_sha256": sha256(STANDARD),
            "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "project_sha256": sha256(ROOT / "Project.toml"),
            "source_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
            ).stdout.strip(),
            "code_sha256": code_hashes,
            "r1_evidence_preserved": True,
            "exploratory_data_not_accepted": True,
        },
    }
    write_json(run_spec_path, run_spec)
    with source_hashes_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("".join(f"{digest}  {relative}\n" for relative, digest in code_hashes.items()))
    print(json.dumps({"run_spec": str(run_spec_path), "source_hashes": str(source_hashes_path), "cells": 1}, ensure_ascii=False))


if __name__ == "__main__":
    main()
