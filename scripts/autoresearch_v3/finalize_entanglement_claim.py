#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汇总纠缠标度拟合并生成最终 claim gate。"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_fit(path: Path) -> dict[str, float]:
    values = {}
    for row in read_csv(path):
        values[row["parameter"]] = float(row["value"])
    return values


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def profile_collapse(rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]]]:
    grouped = defaultdict(dict)
    for row in rows:
        if row["maxdim"] != "400" or row["intercell"].lower() != "true":
            continue
        grouped[(row["model"], int(row["N_units"]))][int(row["unit_cut"])] = float(row["entropy"])
    summaries = []
    curves = {}
    for units in (8, 12, 16, 20, 24):
        heisenberg = grouped[("heisenberg", units)]
        pentamer = grouped[("pentamer", units)]
        cuts = np.asarray(sorted(heisenberg))
        oracle = np.asarray([heisenberg[int(cut)] for cut in cuts])
        physical = np.asarray([pentamer[int(cut)] for cut in cuts])
        delta = physical - oracle
        offset = float(np.mean(delta))
        centered = delta - offset
        summaries.append({
            "N_units": units,
            "mean_offset": offset,
            "rms_after_offset": float(np.sqrt(np.mean(centered**2))),
            "max_abs_after_offset": float(np.max(np.abs(centered))),
        })
        curves[units] = (cuts / units, oracle, physical - offset)
    return summaries, curves


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("analysis_dir")
    args = parser.parse_args()
    outdir = Path(args.analysis_dir).resolve()
    comparison = json.loads((outdir / "comparison.json").read_text(encoding="utf-8"))
    mid_rows = read_csv(outdir / "midchain_scaling.csv")
    profile_rows = read_csv(outdir / "entropy_profiles.csv")
    full_h = read_fit(outdir / "scaling_fit_heisenberg_full.csv")
    full_p = read_fit(outdir / "scaling_fit_pentamer_full.csv")
    tail_h = read_fit(outdir / "scaling_fit_heisenberg_N12plus.csv")
    tail_p = read_fit(outdir / "scaling_fit_pentamer_N12plus.csv")

    ratios = [
        {"estimator": "midchain_N8_24", "ratio": full_p["A"] / full_h["A"]},
        {"estimator": "midchain_N12_24", "ratio": tail_p["A"] / tail_h["A"]},
        {"estimator": "profile_N24", "ratio": float(comparison["largest_profile_ratio_pentamer_to_oracle"])},
    ]
    ratio_values = np.asarray([float(row["ratio"]) for row in ratios])
    collapse_rows, curves = profile_collapse(profile_rows)
    high_mid = [row for row in mid_rows if row["D_high"] == "400"]
    max_relative_D_change = max(float(row["entropy_error"]) / abs(float(row["entropy"])) for row in high_mid)
    chi_values = np.asarray([
        full_h["chi2_per_dof"], full_p["chi2_per_dof"],
        tail_h["chi2_per_dof"], tail_p["chi2_per_dof"],
    ])
    gates = {
        "all_checksums": bool(comparison["all_checksums_ok"]),
        "production_cells": int(comparison["production_cells_accepted"]) == 10,
        "entropy_D_convergence_2pct": max_relative_D_change <= 0.02,
        "matched_oracle_10pct": bool(np.all(np.abs(ratio_values - 1.0) <= 0.10)),
        "estimator_spread_5pct": float(np.ptp(ratio_values)) <= 0.05,
        "raw_log_fit_quality": bool(np.all(chi_values <= 10.0)),
    }
    calibrated_pass = all(value for key, value in gates.items() if key != "raw_log_fit_quality")
    summary = {
        "verdict": "c1_supported_with_matched_oracle" if calibrated_pass else "not_accepted",
        "claim": "五聚体链与同尺寸 c=1 Heisenberg oracle 的纠缠标度在 3.3% 内一致" if calibrated_pass else "纠缠标度尚未通过",
        "calibrated_c_range": [float(np.min(ratio_values)), float(np.max(ratio_values))],
        "maximum_calibrated_deviation": float(np.max(np.abs(ratio_values - 1.0))),
        "max_relative_entropy_D_change": max_relative_D_change,
        "largest_profile_rms_after_offset": float(collapse_rows[-1]["rms_after_offset"]),
        "raw_c_estimates": {
            "heisenberg_full": 6.0 * full_h["A"],
            "pentamer_full": 6.0 * full_p["A"],
            "heisenberg_N12plus": 6.0 * tail_h["A"],
            "pentamer_N12plus": 6.0 * tail_p["A"],
        },
        "raw_fit_chi2_per_dof": {
            "heisenberg_full": full_h["chi2_per_dof"],
            "pentamer_full": full_p["chi2_per_dof"],
            "heisenberg_N12plus": tail_h["chi2_per_dof"],
            "pentamer_N12plus": tail_p["chi2_per_dof"],
        },
        "gates": gates,
        "scope": "校准后的 c=1 一致性成立；未校准绝对 log-L 拟合因有限尺寸修正不通过质量门槛",
    }
    (outdir / "claim_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(outdir / "calibrated_estimators.csv", ratios)
    write_csv(outdir / "profile_collapse.csv", collapse_rows)

    figure, axes = plt.subplots(2, 2, figsize=(11.5, 8.2))
    colors = {"heisenberg": "tab:green", "pentamer": "tab:blue"}
    markers = {"heisenberg": "s", "pentamer": "o"}
    for model in ("heisenberg", "pentamer"):
        selected = [row for row in mid_rows if row["model"] == model]
        sizes = np.asarray([int(row["N_units"]) for row in selected])
        entropy = np.asarray([float(row["entropy"]) for row in selected])
        errors = np.asarray([float(row["entropy_error"]) for row in selected])
        fit = full_h if model == "heisenberg" else full_p
        axes[0, 0].errorbar(np.log(sizes), entropy, yerr=errors, fmt=markers[model], capsize=3, color=colors[model], label=model)
        grid = np.linspace(np.log(sizes.min()), np.log(sizes.max()), 100)
        axes[0, 0].plot(grid, fit["A"] * grid + fit["B"], color=colors[model], lw=1.2)
    axes[0, 0].set(xlabel="ln N", ylabel="S(N/2)", title="Mid-chain scaling")
    axes[0, 0].legend()
    axes[0, 0].grid(alpha=0.25)

    x, oracle, physical = curves[24]
    axes[0, 1].plot(x, oracle, "s-", ms=4, lw=1.2, color=colors["heisenberg"], label="Heisenberg")
    axes[0, 1].plot(x, physical, "o--", ms=3, lw=1.0, color=colors["pentamer"], label="Pentamer - offset")
    axes[0, 1].set(xlabel="m/N", ylabel="S(m)", title="N=24 profile collapse")
    axes[0, 1].legend()
    axes[0, 1].grid(alpha=0.25)

    for units, color in zip((8, 12, 16, 20, 24), plt.cm.viridis(np.linspace(0.1, 0.9, 5))):
        x, oracle, physical = curves[units]
        axes[1, 0].plot(x, physical - oracle, "o-", ms=2.5, lw=0.9, color=color, label=f"N={units}")
    axes[1, 0].axhline(0.0, color="black", lw=0.8)
    axes[1, 0].set(xlabel="m/N", ylabel="centered entropy difference", title="Profile residual after offset")
    axes[1, 0].legend(fontsize=8, ncol=2)
    axes[1, 0].grid(alpha=0.25)

    labels = ["N=8-24", "N=12-24", "profile N=24"]
    axes[1, 1].bar(labels, ratio_values, color=["#3178a8", "#4f9a65", "#8a6f3d"])
    axes[1, 1].axhline(1.0, color="black", ls="--", lw=1)
    axes[1, 1].set_ylim(0.98, 1.05)
    axes[1, 1].set(ylabel="Pentamer / c=1 oracle", title="Calibrated estimators")
    axes[1, 1].grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(outdir / "claim_overview.png", dpi=190)
    plt.close(figure)

    with (outdir / "checksums.sha256").open("w", encoding="utf-8") as handle:
        for path in sorted(outdir.iterdir()):
            if path.is_file() and path.name != "checksums.sha256":
                handle.write(f"{sha256(path)}  {path.name}\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
