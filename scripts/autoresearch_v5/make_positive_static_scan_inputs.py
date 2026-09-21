#!/usr/bin/env python3
"""生成正区静态生产扫描的路径、轴、设置与来源文件。"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SELECTION = ROOT / "results" / "autoresearch_v5_20260730" / "round6_positive_static_selection" / "validation_cells.csv"
RUN_DIR = ROOT / "results" / "autoresearch_v5_20260730" / "round8_positive_static_production"
STANDARD = ROOT / "docs" / "pentamer_reproduction_standard.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    with SELECTION.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 9:
        raise SystemExit(f"候选路径数量必须为 9，当前为 {len(rows)}")
    paths = []
    for index, row in enumerate(rows, start=1):
        alpha = float(row["alpha"])
        beta = float(row["beta"])
        if alpha < 0 or beta < 0:
            raise SystemExit("禁止生成负耦合任务")
        paths.append({
            "path_id": f"p{index:02d}",
            "group": int(row["group"]),
            "role": row["role"],
            "alpha": alpha,
            "beta": beta,
            "map_beta": float(row["map_beta"]),
        })

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip())
    manifest = ROOT / "Manifest.toml"
    paths_payload = {
        "scope": "alpha>=0,beta>=0",
        "selection_source": str(SELECTION.relative_to(ROOT)).replace("\\", "/"),
        "selection_source_sha256": sha256(SELECTION),
        "paths": paths,
    }
    axes = {"path_id": [row["path_id"] for row in paths], "L": [40, 60, 80]}
    settings = {
        "method": "finite_dmrg",
        "boundary": "OBC",
        "sectors": ["Sz=0", "Sz=1"],
        "maxdim_by_L": {"40": 800, "60": 1000, "80": 1200},
        "nsweeps": 32,
        "cutoff": 1e-11,
        "threads": 8,
        "init_mode_sz0": "center",
        "init_mode_sz1": "center",
        "string_margin": 3,
        "schmidt_levels": 16,
        "save_state_rule": "ridge_and_L80_only",
        "offline": True,
        "execution": "sequential_nice_10",
        "acceptance": {
            "variance_per_site_max": 1e-8,
            "max_truncation_error": 1e-9,
            "sector_tolerance": 1e-8,
            "minimum_spin_gap": -1e-8,
        },
    }
    provenance = {
        "source_commit": commit,
        "git_dirty": dirty,
        "standard_sha256": sha256(STANDARD),
        "manifest_sha256": sha256(manifest),
        "server_julia_version": "1.12.3",
        "selection_sha256": sha256(SELECTION),
        "negative_alpha_excluded": True,
        "remote_target": "wangjieren@39.96.207.180:6000",
        "submission_state": "not_uploaded_waiting_for_confirmation",
    }
    write_json(RUN_DIR / "paths.json", paths_payload)
    write_json(RUN_DIR / "axes.json", axes)
    write_json(RUN_DIR / "settings.json", settings)
    write_json(RUN_DIR / "provenance.json", provenance)
    print(json.dumps({"run_dir": str(RUN_DIR), "paths": len(paths), "cells": len(paths) * 3}, ensure_ascii=False))


if __name__ == "__main__":
    main()
