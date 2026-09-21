#!/usr/bin/env python3
"""生成带候选脊线双初态复核的正区静态扫描。"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SELECTION = ROOT / "results" / "autoresearch_v5_20260730" / "round6_positive_static_selection" / "validation_cells.csv"
RUN_DIR = ROOT / "results" / "autoresearch_v5_20260731" / "round10_positive_static_multistart_production"
STANDARD = ROOT / "docs" / "pentamer_reproduction_standard.md"
LENGTHS = (40, 60, 80)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def git_value(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    with SELECTION.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 9:
        raise SystemExit(f"候选路径数量必须为 9，当前为 {len(rows)}")

    base_paths: list[dict[str, object]] = []
    variants: list[dict[str, object]] = []
    for index, row in enumerate(rows, start=1):
        alpha = float(row["alpha"])
        beta = float(row["beta"])
        if alpha < 0 or beta < 0:
            raise SystemExit("禁止生成负耦合任务")
        path = {
            "path_id": f"p{index:02d}",
            "group": int(row["group"]),
            "role": row["role"],
            "alpha": alpha,
            "beta": beta,
            "map_beta": float(row["map_beta"]),
        }
        base_paths.append(path)
        modes = ("center", "domain") if row["role"] == "ridge" else ("center",)
        for mode in modes:
            variants.append({
                **path,
                "variant_id": f"{path['path_id']}-{mode}",
                "init_mode": mode,
            })

    cells: list[dict[str, object]] = []
    for variant in variants:
        for length in LENGTHS:
            cells.append({
                "cell_id": f"cell-{len(cells) + 1:04d}",
                "params": {"variant_id": variant["variant_id"], "L": length},
                "settings": {"init_mode_sz0": variant["init_mode"]},
            })
    if len(variants) != 12 or len(cells) != 36:
        raise SystemExit("双初态扫描必须包含 12 个变体和 36 个 cell")

    settings = {
        "method": "finite_dmrg",
        "boundary": "OBC",
        "sectors": ["Sz=0", "Sz=1"],
        "maxdim_by_L": {"40": 800, "60": 1000, "80": 1200},
        "nsweeps": 32,
        "cutoff": 1e-11,
        "threads": 8,
        "init_mode_sz0_default": "center",
        "init_mode_sz1": "center",
        "initialization_modes_by_role": {
            "left": ["center"],
            "ridge": ["center", "domain"],
            "right": ["center"],
        },
        "string_margin": 3,
        "schmidt_levels": 16,
        "save_state_rule": "ridge_L80_center_only",
        "offline": True,
        "execution": "sequential_nice_10",
        "acceptance": {
            "variance_per_site_max": 1e-8,
            "max_truncation_error": 1e-9,
            "sector_tolerance": 1e-8,
            "minimum_spin_gap": -1e-8,
        },
        "initialization_validation": {
            "energy_density_abs_max": 1e-10,
            "spin_gap_abs_max": 1e-8,
            "string_profile_abs_max": 1e-5,
            "bond_correlation_abs_max": 1e-5,
            "schmidt_probability_l1_max": 1e-4,
        },
    }
    provenance = {
        "source_commit": git_value("rev-parse", "HEAD"),
        "git_dirty": bool(git_value("status", "--porcelain")),
        "standard_sha256": sha256(STANDARD),
        "manifest_sha256": sha256(ROOT / "Manifest.toml"),
        "server_julia_version": "1.12.3",
        "selection_sha256": sha256(SELECTION),
        "negative_alpha_excluded": True,
        "remote_target": "wangjieren@39.96.207.180:6000",
        "submission_state": "not_uploaded_waiting_for_confirmation",
    }
    axes = {
        "variant_id": [row["variant_id"] for row in variants],
        "L": list(LENGTHS),
    }
    plan = {
        "run_id": "pentamer-positive-static-multistart-20260731",
        "run_dir": str(RUN_DIR.relative_to(ROOT)).replace("\\", "/"),
        "axes": axes,
        "cells": cells,
    }
    run_spec = {
        "run_id": plan["run_id"],
        "run_dir": plan["run_dir"],
        "settings": settings,
        "provenance": provenance,
        "cells": cells,
    }
    paths_payload = {
        "scope": "alpha>=0,beta>=0",
        "selection_source": str(SELECTION.relative_to(ROOT)).replace("\\", "/"),
        "selection_source_sha256": sha256(SELECTION),
        "base_paths": base_paths,
        "variants": variants,
    }
    write_json(RUN_DIR / "paths.json", paths_payload)
    write_json(RUN_DIR / "axes.json", axes)
    write_json(RUN_DIR / "settings.json", settings)
    write_json(RUN_DIR / "provenance.json", provenance)
    write_json(RUN_DIR / "parameter-scan.plan.json", plan)
    write_json(RUN_DIR / "run_spec.json", run_spec)
    print(json.dumps({
        "run_dir": str(RUN_DIR),
        "base_paths": len(base_paths),
        "variants": len(variants),
        "cells": len(cells),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
