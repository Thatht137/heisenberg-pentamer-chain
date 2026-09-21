#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成弱耦合纠缠熵与 Heisenberg oracle 参数清单。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "scripts" / "autoresearch_v3" / "entanglement_scan_run_spec.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    cells = []
    index = 1
    for model in ("heisenberg", "pentamer"):
        for maxdim in (80, 400):
            for units in (8, 12, 16, 20, 24):
                cells.append({
                    "cell_id": f"cell-{index:04d}",
                    "model": model,
                    "alpha": 0.23,
                    "beta": 0.05,
                    "N_units": units,
                    "maxdim": maxdim,
                })
                index += 1
    spec = {
        "run_id": "pentamer-entanglement-scaling-20260730",
        "run_dir": "results/autoresearch_v4_20260730/round1_entanglement_scaling",
        "settings": {
            "method": "finite_dmrg",
            "boundary": "OBC",
            "nsweeps": 40,
            "cutoff": 1e-12,
            "threads": 16,
            "init_mode": "center",
            "offline": True,
        },
        "provenance": {
            "manifest_sha256": sha256(ROOT / "Manifest.toml"),
            "server_julia_version": "1.12.3",
            "negative_alpha_excluded": True,
            "hypothesis": "positive-alpha pentamer chain has a gapless c=1 effective spin chain",
            "fit_form": "OBC CFT logarithmic entanglement scaling",
        },
        "cells": cells,
    }
    OUTPUT.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUTPUT} cells={len(cells)}")


if __name__ == "__main__":
    main()
