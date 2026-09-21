#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成正 alpha 有效理论验证参数清单。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC_DIR = ROOT / "scripts" / "autoresearch_v3"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_spec(run_id: str, run_dir: str, settings: dict[str, object], cells: list[dict[str, object]]) -> dict[str, object]:
    return {
        "run_id": run_id,
        "run_dir": run_dir,
        "settings": {
            "method": "finite_dmrg",
            "boundary": "OBC",
            "init_mode": "center",
            "offline": True,
            **settings,
        },
        "provenance": {
            "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "server_julia_version": "1.12.3",
            "negative_alpha_excluded": True,
            "hypothesis": "first-order doublet projection to an AFM spin-1/2 Heisenberg chain",
        },
        "cells": cells,
    }


def main() -> None:
    physical_points = set()
    for beta in (0.02, 0.05, 0.10, 0.20):
        for units in (8, 12, 16):
            physical_points.add((0.23, beta, units))
    for alpha in (0.14, 0.33):
        for units in (8, 12, 16):
            physical_points.add((alpha, 0.05, units))
    cells = []
    for index, (alpha, beta, units, target_sz) in enumerate(
        (point + (sector,) for point in sorted(physical_points) for sector in (0, 1)), start=1
    ):
        cells.append({"cell_id": f"cell-{index:04d}", "alpha": alpha, "beta": beta, "N_units": units, "target_sz": target_sz})
    smoke_cells = [
        {"cell_id": f"cell-{index:04d}", "alpha": 0.23, "beta": 0.05, "N_units": 8, "target_sz": sector}
        for index, sector in enumerate((0, 1), start=1)
    ]
    weak_cells = [
        {"cell_id": f"cell-{index:04d}", "alpha": 0.23, "beta": 0.02, "N_units": units, "target_sz": sector}
        for index, (units, sector) in enumerate(
            ((units, sector) for units in (12, 16) for sector in (0, 1)), start=1
        )
    ]
    specs = {
        SPEC_DIR / "effective_smoke_run_spec.json": make_spec(
            "pentamer-effective-chain-smoke-20260729",
            "results/autoresearch_v3_20260729/round2_effective_smoke",
            {"maxdim": 200, "nsweeps": 8, "cutoff": 1e-10, "threads": 8},
            smoke_cells,
        ),
        SPEC_DIR / "effective_smoke_fix1_run_spec.json": make_spec(
            "pentamer-effective-chain-smoke-fix1-20260729",
            "results/autoresearch_v3_20260729/round2_effective_smoke_fix1",
            {"maxdim": 400, "nsweeps": 16, "cutoff": 1e-11, "threads": 8},
            smoke_cells,
        ),
        SPEC_DIR / "effective_scan_run_spec.json": make_spec(
            "pentamer-effective-chain-scan-20260729",
            "results/autoresearch_v3_20260729/round2_effective_scan",
            {"maxdim": 800, "nsweeps": 24, "cutoff": 1e-11, "threads": 16},
            cells,
        ),
        SPEC_DIR / "effective_weak_fix_center_run_spec.json": make_spec(
            "pentamer-effective-chain-weak-fix-center-20260729",
            "results/autoresearch_v3_20260729/round2_effective_weak_fix_center",
            {"maxdim": 800, "nsweeps": 64, "cutoff": 1e-12, "threads": 16, "init_mode": "center"},
            weak_cells,
        ),
        SPEC_DIR / "effective_weak_fix_left_run_spec.json": make_spec(
            "pentamer-effective-chain-weak-fix-left-20260729",
            "results/autoresearch_v3_20260729/round2_effective_weak_fix_left",
            {"maxdim": 800, "nsweeps": 64, "cutoff": 1e-12, "threads": 16, "init_mode": "left"},
            weak_cells,
        ),
    }
    for output, spec in specs.items():
        output.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {output} cells={len(spec['cells'])}")


if __name__ == "__main__":
    main()
