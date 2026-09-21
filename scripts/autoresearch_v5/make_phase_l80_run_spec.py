#!/usr/bin/env python3
"""生成正区 L=80 尺寸晋级的独立 run spec。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE_RUN = ROOT / "results" / "autoresearch_v5_20260731" / "round17_phase_diagram_positive"
RUN = ROOT / "results" / "autoresearch_v5_20260731" / "round18_phase_diagram_positive_L80"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    policy = json.loads((BASE_RUN / "phase-diagram" / "phase-policy.json").read_text(encoding="utf-8"))
    cells = []
    for beta in policy["axes"]["slice"]["values"]:
        for alpha in policy["axes"]["control"]["initial_points"]:
            if alpha < 0 or beta < 0:
                raise SystemExit("禁止生成负耦合任务")
            cells.append({
                "cell_id": f"l80-cell-{len(cells) + 1:04d}",
                "params": {"alpha": alpha, "beta": beta, "L": 80, "n_units": 16},
                "budget": 32,
            })
    run_spec = {
        "schema_version": 1,
        "run_id": "pentamer-positive-phase-diagram-20260802-L80",
        "scope": "alpha>=0,beta>=0; L=80 promotion; Fig.9 excluded",
        "policy": "../round17_phase_diagram_positive/phase-diagram/phase-policy.json",
        "controller": "local_only",
        "promotion_reason": "首段 40/60 粗扫完成；固定边界无显著 bracket，补充第三尺寸趋势",
        "cells": cells,
        "settings": {
            "method": "finite_dmrg_multistart",
            "boundary": "OBC",
            "hamiltonian": "five-site unit cell Heisenberg chain, J1=1, J2=alpha, J3=beta",
            "sectors": ["Sz=0", "Sz=1"],
            "maxdim_by_L": {"80": 1200},
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
            "execution": "server_after_first_stage_confirmation; one heavy job at a time",
        },
        "provenance": {
            "policy_sha256": sha256(BASE_RUN / "phase-diagram" / "phase-policy.json"),
            "standard_sha256": sha256(ROOT / "docs" / "pentamer_reproduction_standard.md"),
            "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "negative_alpha_excluded": True,
        },
    }
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / "parameter-scan.run_spec.json").write_text(
        json.dumps(run_spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"run_spec": str(RUN / "parameter-scan.run_spec.json"), "cells": len(cells)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
