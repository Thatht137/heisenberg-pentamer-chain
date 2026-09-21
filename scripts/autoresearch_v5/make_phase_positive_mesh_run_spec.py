#!/usr/bin/env python3
"""生成正区扩展 beta 截面的离线计算清单。"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v5_20260802" / "round19_phase_diagram_positive_mesh"
POLICY = RUN / "phase-diagram" / "phase-policy.json"
ALPHAS = [0.0, 0.125, 0.25, 0.5, 1.0]
NEW_BETAS = [0.05, 0.25, 0.75, 1.0]
SIZES = [40, 60, 80]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / "phase-diagram").mkdir(parents=True, exist_ok=True)
    policy = {
        "schema_version": 1,
        "goal_id": "pentamer-positive-structure-ratio-mesh-20260802",
        "pattern": "finite_size_crossing",
        "axes": {
            "control": {
                "name": "alpha",
                "bounds": [0.0, 1.0],
                "initial_points": ALPHAS,
                "edge_controls": [0.0],
            },
            "size": {"name": "L", "values": SIZES, "initial_count": 3},
            "slice": {"name": "beta", "values": [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0]},
        },
        "observable": {
            "name": "central_structure_factor_ratio",
            "value_field": "observables.structure_factor_ratio.value",
            "error_field": "observables.structure_factor_ratio.error",
            "budget_field": "settings.budget",
        },
        "criteria": {
            "sigma": 2.0,
            "target_width": 0.025,
            "max_statistics_multiplier": 4,
            "final_pair_required": True,
        },
        "execution": {
            "controller": "local",
            "runner": "uv",
            "base_budget": 32,
            "poll_seconds": 1800,
            "max_actions": 200,
        },
    }
    POLICY.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cells = []
    for beta in NEW_BETAS:
        for alpha in ALPHAS:
            for length in SIZES:
                cells.append({
                    "cell_id": f"mesh-cell-{len(cells) + 1:04d}",
                    "params": {"alpha": alpha, "beta": beta, "L": length, "n_units": length // 5},
                    "budget": 32,
                })
    run_spec = {
        "schema_version": 1,
        "run_id": "pentamer-positive-phase-diagram-20260802-mesh",
        "scope": "alpha>=0,beta>=0; four new beta cuts; negative alpha excluded",
        "policy": "phase-diagram/phase-policy.json",
        "controller": "local_only",
        "reuse_observations": "../round18_final_phase_diagram_positive_L80/phase-diagram/observations_merged.json",
        "cells": cells,
        "settings": {
            "method": "finite_dmrg_multistart",
            "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"],
            "maxdim_by_L": {"40": 800, "60": 1000, "80": 1200},
            "nsweeps": 32,
            "cutoff": 1e-11,
            "threads": 8,
            "init_modes": ["center", "domain"],
            "budget_definition": "nsweeps per independent start",
            "observable_definition": "R(L)=1-S(pi-2pi/M)/S(pi), connected Sz structure factor in central M-site window",
            "error_definition": "half range of center/domain plus 10x largest discarded weight, floor 1e-4",
            "acceptance": {
                "variance_per_site_max": 1e-8,
                "max_truncation_error": 1e-9,
                "sector_tolerance": 1e-8,
                "observable_error_floor": 1e-4,
                "negative_alpha_excluded": True,
            },
            "offline": True,
            "execution": "server direct connection; one heavy cell at a time",
        },
        "provenance": {
            "policy_sha256": sha256(POLICY),
            "standard_sha256": sha256(ROOT / "docs" / "pentamer_reproduction_standard.md"),
            "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "source_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
            ).stdout.strip(),
            "negative_alpha_excluded": True,
            "reused_beta_cuts": [0.1, 0.5, 0.9],
        },
    }
    output = RUN / "parameter-scan.run_spec.json"
    output.write_text(json.dumps(run_spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"policy": str(POLICY), "run_spec": str(output), "cells": len(cells)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
