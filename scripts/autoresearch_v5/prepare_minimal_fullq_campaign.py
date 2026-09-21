#!/usr/bin/env python3
"""生成正区精简全动量 TEBD 顺序任务。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "results" / "research_progress" / "minimal_fullq_campaign_20260807"
RUN_ROOT = "results/autoresearch_v5_20260807/minimal_fullq_campaign"
STANDARD = ROOT / "docs" / "pentamer_reproduction_standard.md"
MANIFEST = ROOT / "Manifest.toml"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cells() -> list[dict[str, object]]:
    points = (
        ("uniform", 1.0, 1.0, "均匀 Heisenberg 精确基准"),
        ("weak", 1.0, 0.1, "受控五聚体有效链"),
        ("agreement", 0.23, 0.5, "既有 q=pi Agreement 点"),
    )
    result: list[dict[str, object]] = []
    for label, alpha, beta, role in points:
        for refinement, tstep, n_steps in (
            ("dt025", 0.025, 1200),
            ("dt0125", 0.0125, 2400),
        ):
            result.append(
                {
                    "cell_id": f"fullq-{label}-{refinement}",
                    "point": label,
                    "role": role,
                    "alpha": alpha,
                    "beta": beta,
                    "n_units": 8,
                    "L": 40,
                    "tstep": tstep,
                    "n_steps": n_steps,
                    "tmax": 30.0,
                    "dmrg_maxdim": 800,
                    "tebd_maxdim": 320,
                    "dmrg_cutoff": 1e-10,
                    "tebd_cutoff": 1e-10,
                    "nsweeps": 32,
                    "q_points": 121,
                    "omega_points": 301,
                    "omega_max": 3.0,
                    "space_window": 18,
                    "time_window": "exponential",
                    "window_eta": 0.1,
                    "max_negative_weight_fraction": 0.15,
                    "threads": 16,
                }
            )
    return result


def command(cell: dict[str, object], manifest_hash: str, standard_hash: str) -> str:
    cell_id = str(cell["cell_id"])
    values = {
        "cell-id": cell_id,
        "outdir": f"{RUN_ROOT}/{cell_id}",
        "alpha": cell["alpha"],
        "beta": cell["beta"],
        "n-units": cell["n_units"],
        "tstep": cell["tstep"],
        "n-steps": cell["n_steps"],
        "dmrg-maxdim": cell["dmrg_maxdim"],
        "tebd-maxdim": cell["tebd_maxdim"],
        "dmrg-cutoff": cell["dmrg_cutoff"],
        "tebd-cutoff": cell["tebd_cutoff"],
        "nsweeps": cell["nsweeps"],
        "q-points": cell["q_points"],
        "omega-points": cell["omega_points"],
        "omega-max": cell["omega_max"],
        "space-window": cell["space_window"],
        "time-window": cell["time_window"],
        "window-eta": cell["window_eta"],
        "max-negative-weight-fraction": cell["max_negative_weight_fraction"],
        "threads": cell["threads"],
        "standard-sha256": standard_hash,
        "expected-manifest-sha256": manifest_hash,
        "expected-julia-version": "1.12.3",
        "source-commit": "minimal-fullq-20260807",
    }
    args = " ".join(f"--{key} {value}" for key, value in values.items())
    return f"python3 scripts/autoresearch_v5/run_tebd_production.py {args}"


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    manifest_hash = sha256(MANIFEST)
    standard_hash = sha256(STANDARD)
    campaign_cells = cells()
    plan = {
        "schema_version": 1,
        "created_at": "2026-08-07T00:00:00+08:00",
        "scope": {
            "alpha_beta": "[0,1]",
            "negative_alpha_excluded": True,
            "figure_9_excluded": True,
        },
        "execution": "sequential_stop_on_failure",
        "estimated_server_hours": [18, 42],
        "manifest_sha256": manifest_hash,
        "standard_sha256": standard_hash,
        "cells": campaign_cells,
        "acceptance": {
            "single_run": [
                "t0 included",
                "ground variance per site <= 1e-8",
                "Sz=0",
                "raw negative weight fraction <= 0.15",
            ],
            "pair": [
                "dt/2",
                "global and q=pi peak drift <= 0.05 J1",
                "low-window weight drift <= 5%",
            ],
        },
    }
    (OUTDIR / "campaign_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    lines = ["#!/usr/bin/env bash", "set -euo pipefail", ""]
    by_point: dict[str, list[dict[str, object]]] = {}
    for cell in campaign_cells:
        by_point.setdefault(str(cell["point"]), []).append(cell)
    for point, pair in by_point.items():
        lines.extend(command(cell, manifest_hash, standard_hash) for cell in pair)
        lines.append(
            "python3 scripts/autoresearch_v5/analyze_tebd_crosscheck.py "
            f"--coarse-dir {RUN_ROOT}/{pair[0]['cell_id']} "
            f"--refined-dir {RUN_ROOT}/{pair[1]['cell_id']} "
            f"--output {RUN_ROOT}/{point}_dt_crosscheck.json"
        )
        lines.append("")
    (OUTDIR / "launch_campaign.sh").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"cells": len(campaign_cells), "outdir": str(OUTDIR)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
