#!/usr/bin/env python3
"""根据本地 phase policy 生成参数扫描初始 run spec。"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results" / "autoresearch_v5_20260731" / "round17_phase_diagram_positive"
POLICY = RUN / "phase-diagram" / "phase-policy.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    control = policy["axes"]["control"]
    sizes = policy["axes"]["size"]["values"]
    slices = policy["axes"]["slice"]["values"]
    initial_sizes = sizes[: policy["axes"]["size"]["initial_count"]]
    cells = []
    for beta in slices:
        for alpha in control["initial_points"]:
            if alpha < 0 or beta < 0:
                raise SystemExit("禁止生成负耦合任务")
            for length in initial_sizes:
                cells.append({
                    "cell_id": f"cell-{len(cells) + 1:04d}",
                    "params": {"alpha": alpha, "beta": beta, "L": length, "n_units": length // 5},
                    "budget": policy["execution"]["base_budget"],
                })
    run_spec = {
        "schema_version": 1,
        "run_id": "pentamer-positive-phase-diagram-20260731",
        "scope": "alpha>=0,beta>=0; Fig.9 excluded",
        "policy": "phase-diagram/phase-policy.json",
        "controller": "local_only",
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
            "execution": "server_after_user_confirmation; one heavy job at a time",
        },
        "provenance": {
            "policy_sha256": sha256(POLICY),
            "standard_sha256": sha256(ROOT / "docs" / "pentamer_reproduction_standard.md"),
            "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "source_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
            ).stdout.strip(),
            "remote_upload": "blocked_until_user_confirms_first_stage",
        },
    }
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / "parameter-scan.run_spec.json").write_text(
        json.dumps(run_spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"run_spec": str(RUN / "parameter-scan.run_spec.json"), "cells": len(cells)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
