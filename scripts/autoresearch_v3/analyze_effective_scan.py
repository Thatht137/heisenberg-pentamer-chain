#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析完整五聚体链与一阶有效 Heisenberg 链的一致性。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PROJECTION = ROOT / "results" / "autoresearch_v3_20260729" / "round1_doublet_projection" / "representative.csv"
ORACLE = ROOT / "results" / "autoresearch_v3_20260729" / "round2_effective_oracle" / "heisenberg_obc_oracle.csv"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def verify_cell(cell: Path) -> dict[str, object]:
    status_path = cell / "status.json"
    manifest_path = cell / "manifest.json"
    checksum_path = cell / "checksums.sha256"
    for path in (status_path, manifest_path, checksum_path):
        if not path.is_file():
            raise ValueError(f"cell 文件缺失: {path}")
    status = json.loads(status_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if status.get("status") != "success" or manifest.get("status") != "success":
        raise ValueError(f"cell 未成功: {cell}")
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        path = cell / name
        if not path.is_file() or sha256(path) != expected:
            raise ValueError(f"cell 校验失败: {path}")
    return manifest


def load_cells(run_dir: Path) -> list[dict[str, object]]:
    cells_dir = run_dir / "cells"
    cells = sorted(path for path in cells_dir.iterdir() if path.is_dir())
    if not cells:
        raise ValueError(f"没有找到 cell: {cells_dir}")
    manifests = []
    for cell in cells:
        manifest = verify_cell(cell)
        manifest["analysis_source"] = str(run_dir.relative_to(ROOT))
        manifests.append(manifest)
    return manifests


def lookup_tables() -> tuple[dict[float, dict[str, float]], dict[int, dict[str, float]]]:
    projection = {
        round(float(row["alpha"]), 12): {key: float(value) for key, value in row.items() if key != "alpha"}
        for row in read_csv(PROJECTION)
    }
    oracle = {
        int(row["N_units"]): {key: float(value) for key, value in row.items() if key != "N_units"}
        for row in read_csv(ORACLE)
    }
    return projection, oracle


def candidate_key(manifest: dict[str, object]) -> tuple[float, float, int, int]:
    params = manifest["params"]
    return (
        float(params["alpha"]),
        float(params["beta"]),
        int(params["N_units"]),
        int(params["target_sz"]),
    )


def sector_error(manifest: dict[str, object]) -> float:
    target = int(manifest["params"]["target_sz"])
    return abs(float(manifest["observables"]["total_sz"]) - target)


def candidate_passes(manifest: dict[str, object]) -> bool:
    diagnostics = manifest["diagnostics"]
    return (
        math.isfinite(float(manifest["observables"]["energy"]))
        and float(diagnostics["variance_per_site"]) <= 1e-8
        and float(diagnostics["max_truncation_error"]) <= 1e-8
        and sector_error(manifest) <= 1e-8
    )


def initial_state_family(manifest: dict[str, object]) -> str:
    mode = str(manifest["settings"]["init_mode"])
    if int(manifest["params"]["target_sz"]) == 0 and mode in {"center", "left", "right"}:
        return "neel"
    return mode


def select_candidates(
    manifests: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    grouped: dict[tuple[float, float, int, int], list[dict[str, object]]] = defaultdict(list)
    for manifest in manifests:
        grouped[candidate_key(manifest)].append(manifest)

    selected = []
    audit = []
    for key, candidates in sorted(grouped.items()):
        accepted = [candidate for candidate in candidates if candidate_passes(candidate)]
        if not accepted:
            raise ValueError(f"没有通过验收的候选: alpha={key[0]}, beta={key[1]}, N={key[2]}, Sz={key[3]}")
        chosen = min(accepted, key=lambda item: float(item["observables"]["energy"]))
        selected.append(chosen)
        for candidate in candidates:
            diagnostics = candidate["diagnostics"]
            audit.append(
                {
                    "alpha": key[0],
                    "beta": key[1],
                    "N_units": key[2],
                    "target_sz": key[3],
                    "source_run": candidate["analysis_source"],
                    "init_mode": candidate["settings"]["init_mode"],
                    "initial_state_family": initial_state_family(candidate),
                    "energy": candidate["observables"]["energy"],
                    "energy_density": candidate["observables"]["energy_density"],
                    "variance_per_site": diagnostics["variance_per_site"],
                    "max_truncation_error": diagnostics["max_truncation_error"],
                    "sector_error": sector_error(candidate),
                    "final_energy_change": diagnostics["final_energy_change"],
                    "actual_maxdim": diagnostics["actual_maxdim"],
                    "accepted": candidate_passes(candidate),
                    "selected": candidate is chosen,
                }
            )
    return selected, audit


def initial_state_spread(candidates: list[dict[str, object]]) -> dict[tuple[float, float, int, int], float]:
    grouped: dict[tuple[float, float, int, int], dict[str, float]] = defaultdict(dict)
    for candidate in candidates:
        if not candidate_passes(candidate):
            continue
        key = candidate_key(candidate)
        mode = initial_state_family(candidate)
        density = float(candidate["observables"]["energy_density"])
        grouped[key][mode] = min(density, grouped[key].get(mode, math.inf))
    return {
        key: max(values.values()) - min(values.values())
        for key, values in grouped.items()
        if len(values) >= 2
    }


def pair_sectors(
    manifests: list[dict[str, object]], spreads: dict[tuple[float, float, int, int], float]
) -> list[dict[str, object]]:
    grouped: dict[tuple[float, float, int], dict[int, dict[str, object]]] = defaultdict(dict)
    for manifest in manifests:
        alpha, beta, n_units, sector = candidate_key(manifest)
        key = (alpha, beta, n_units)
        if sector in grouped[key]:
            raise ValueError(f"候选选择后仍有重复扇区: {key}, Sz={sector}")
        grouped[key][sector] = manifest
    pairs = []
    for key, sectors in sorted(grouped.items()):
        if set(sectors) != {0, 1}:
            raise ValueError(f"扇区不完整: {key}")
        pairs.append(
            {
                "alpha": key[0],
                "beta": key[1],
                "N_units": key[2],
                "sz0": sectors[0],
                "sz1": sectors[1],
                "sz0_initial_state_spread": spreads.get((*key, 0), math.nan),
                "sz1_initial_state_spread": spreads.get((*key, 1), math.nan),
            }
        )
    return pairs


def compare(pairs: list[dict[str, object]]) -> list[dict[str, object]]:
    projection, oracle = lookup_tables()
    rows = []
    for pair in pairs:
        alpha = float(pair["alpha"])
        beta = float(pair["beta"])
        n_units = int(pair["N_units"])
        local = projection[round(alpha, 12)]
        heisenberg = oracle[n_units]
        sz0 = pair["sz0"]
        sz1 = pair["sz1"]
        energy0 = float(sz0["observables"]["energy"])
        energy1 = float(sz1["observables"]["energy"])
        jeff = beta * local["jeff_over_beta"]
        predicted_energy = n_units * local["ground_energy"] + jeff * heisenberg["E_sz0"]
        full_gap = energy1 - energy0
        predicted_gap = jeff * heisenberg["spin_gap"]
        residual = energy0 - predicted_energy
        links = n_units - 1
        diagnostics = [sz0["diagnostics"], sz1["diagnostics"]]
        rows.append(
            {
                "alpha": alpha,
                "beta": beta,
                "N_units": n_units,
                "L": 5 * n_units,
                "local_gap": local["local_gap"],
                "jeff": jeff,
                "beta_over_local_gap": beta / local["local_gap"],
                "energy_full": energy0,
                "energy_effective": predicted_energy,
                "energy_residual": residual,
                "energy_residual_per_link": residual / links,
                "energy_residual_per_link_beta2": residual / links / beta**2,
                "gap_full": full_gap,
                "gap_effective": predicted_gap,
                "gap_ratio": full_gap / predicted_gap,
                "gap_relative_error": (full_gap - predicted_gap) / predicted_gap,
                "sz0_source_run": sz0["analysis_source"],
                "sz1_source_run": sz1["analysis_source"],
                "sz0_init_mode": sz0["settings"]["init_mode"],
                "sz1_init_mode": sz1["settings"]["init_mode"],
                "sz0_initial_state_spread": pair["sz0_initial_state_spread"],
                "sz1_initial_state_spread": pair["sz1_initial_state_spread"],
                "max_variance_per_site": max(float(item["variance_per_site"]) for item in diagnostics),
                "max_truncation_error": max(float(item["max_truncation_error"]) for item in diagnostics),
                "max_final_energy_change": max(float(item["final_energy_change"]) for item in diagnostics),
                "max_actual_maxdim": max(float(item["actual_maxdim"]) for item in diagnostics),
                "max_sector_error": max(
                    abs(float(sz0["observables"]["total_sz"])),
                    abs(float(sz1["observables"]["total_sz"]) - 1.0),
                ),
                "cells_pass": all(
                    float(item["variance_per_site"]) <= 1e-8
                    and float(item["max_truncation_error"]) <= 1e-8
                    for item in diagnostics
                ),
            }
        )
    return rows


def residual_powers(rows: list[dict[str, object]]) -> dict[str, float]:
    powers = {}
    for n_units in sorted({int(row["N_units"]) for row in rows}):
        subset = [row for row in rows if row["alpha"] == 0.23 and row["N_units"] == n_units and row["beta"] <= 0.1]
        x = np.log([float(row["beta"]) for row in subset])
        y = np.log([abs(float(row["energy_residual_per_link"])) for row in subset])
        powers[str(n_units)] = float(np.polyfit(x, y, 1)[0])
    return powers


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_figure(path: Path, rows: list[dict[str, object]]) -> None:
    plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": 0.25})
    figure, axes = plt.subplots(2, 2, figsize=(10, 7.4), constrained_layout=True)
    center = [row for row in rows if row["alpha"] == 0.23]
    for n_units in sorted({int(row["N_units"]) for row in center}):
        subset = [row for row in center if row["N_units"] == n_units]
        beta = [row["beta"] for row in subset]
        axes[0, 0].loglog(beta, [abs(row["energy_residual_per_link"]) for row in subset], "o-", label=f"N={n_units}")
        axes[0, 1].plot(beta, [row["gap_ratio"] for row in subset], "o-", label=f"N={n_units}")
        axes[1, 0].plot(beta, [row["energy_residual_per_link_beta2"] for row in subset], "o-", label=f"N={n_units}")
    reference_beta = np.array([0.02, 0.2])
    anchor = min(abs(row["energy_residual_per_link"]) / row["beta"] ** 2 for row in center)
    axes[0, 0].loglog(reference_beta, anchor * reference_beta**2, "k--", label=r"$\beta^2$")
    alpha_slice = [row for row in rows if math.isclose(float(row["beta"]), 0.05)]
    for n_units in sorted({int(row["N_units"]) for row in alpha_slice}):
        subset = [row for row in alpha_slice if row["N_units"] == n_units]
        axes[1, 1].plot([row["alpha"] for row in subset], [row["gap_ratio"] for row in subset], "o-", label=f"N={n_units}")
    axes[0, 0].set(xlabel=r"$\beta$", ylabel=r"$|E-E_{eff}|/(N-1)$", title="Energy residual")
    axes[0, 1].set(xlabel=r"$\beta$", ylabel=r"$\Delta/\Delta_{eff}$", title="Spin-gap ratio")
    axes[1, 0].set(xlabel=r"$\beta$", ylabel=r"$(E-E_{eff})/[(N-1)\beta^2]$", title="Second-order coefficient")
    axes[1, 1].set(xlabel=r"$\alpha$", ylabel=r"$\Delta/\Delta_{eff}$", title=r"Alpha dependence at $\beta=0.05$")
    for axis in axes.flat:
        axis.legend(frameon=False)
    figure.savefig(path, dpi=220)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", default="results/autoresearch_v3_20260729/round2_effective_scan")
    parser.add_argument("--override-run-dir", action="append", default=[])
    parser.add_argument("--outdir")
    args = parser.parse_args()
    run_dir = (ROOT / args.run_dir).resolve()
    run_dir.relative_to((ROOT / "results").resolve())
    outdir = (ROOT / args.outdir).resolve() if args.outdir else run_dir / "analysis"
    outdir.relative_to((ROOT / "results").resolve())
    if outdir.exists() and any(outdir.iterdir()):
        raise SystemExit(f"拒绝覆盖分析目录: {outdir}")
    outdir.mkdir(parents=True, exist_ok=True)

    run_dirs = [run_dir]
    for override in args.override_run_dir:
        override_dir = (ROOT / override).resolve()
        override_dir.relative_to((ROOT / "results").resolve())
        run_dirs.append(override_dir)
    candidates = [manifest for directory in run_dirs for manifest in load_cells(directory)]
    selected, audit = select_candidates(candidates)
    spreads = initial_state_spread(candidates)
    rows = compare(pair_sectors(selected, spreads))
    powers = residual_powers(rows)
    tested_spreads = list(spreads.values())
    summary = {
        "candidate_cells": len(candidates),
        "accepted_candidate_cells": sum(candidate_passes(item) for item in candidates),
        "selected_cells": len(selected),
        "physical_points": len(rows),
        "all_cells_pass": all(bool(row["cells_pass"]) and float(row["max_sector_error"]) <= 1e-8 for row in rows),
        "max_variance_per_site": max(float(row["max_variance_per_site"]) for row in rows),
        "max_truncation_error": max(float(row["max_truncation_error"]) for row in rows),
        "max_final_energy_change": max(float(row["max_final_energy_change"]) for row in rows),
        "initial_state_tests": len(tested_spreads),
        "max_initial_state_energy_density_spread": max(tested_spreads) if tested_spreads else None,
        "initial_state_stability_pass": bool(tested_spreads) and all(value <= 1e-7 for value in tested_spreads),
        "small_beta_energy_residual_power": powers,
        "small_beta_gap_ratio_mean": float(np.mean([row["gap_ratio"] for row in rows if row["alpha"] == 0.23 and row["beta"] <= 0.05])),
        "beta_020_gap_ratio_mean": float(np.mean([row["gap_ratio"] for row in rows if row["alpha"] == 0.23 and row["beta"] == 0.2])),
        "claim_gate": {
            "second_order_residual": all(1.7 <= power <= 2.3 for power in powers.values()),
            "small_beta_gap_within_10_percent": all(abs(float(row["gap_ratio"]) - 1.0) <= 0.1 for row in rows if row["alpha"] == 0.23 and row["beta"] <= 0.05),
        },
    }
    write_csv(outdir / "effective_comparison.csv", rows)
    write_csv(outdir / "candidate_audit.csv", audit)
    (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    make_figure(outdir / "effective_theory_validation.png", rows)
    outputs = sorted(path for path in outdir.iterdir() if path.name != "checksums.sha256")
    (outdir / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in outputs), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
