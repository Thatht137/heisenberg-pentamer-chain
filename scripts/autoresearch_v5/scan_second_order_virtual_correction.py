#!/usr/bin/env python3
"""扫描五聚体有效链的二阶虚激发修正。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PROJECTION = ROOT / "results" / "autoresearch_v3_20260729" / "round1_doublet_projection" / "projection_scan.csv"
LEGACY = ROOT / "results" / "autoresearch_v3_20260729" / "round3_two_pentamer_ed" / "comparison.csv"
OUTDIR = ROOT / "results" / "autoresearch_v5_20260731" / "round13_second_order_scan"
sys.path.insert(0, str(ROOT / "scripts" / "autoresearch_v3"))
from two_pentamer_effective_ed import bonds, ground_energy  # noqa: E402


mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 7,
        "axes.linewidth": 0.8,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    }
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_projection() -> list[dict[str, float]]:
    rows = []
    for row in read_csv(PROJECTION):
        rows.append({key: float(value) for key, value in row.items()})
    return rows


def fit_intercept(betas: np.ndarray, coefficients: np.ndarray) -> tuple[float, float]:
    slope, intercept = np.polyfit(betas, coefficients, 1)
    return float(intercept), float(slope)


def calculate(projection: list[dict[str, float]], betas: tuple[float, ...]) -> list[dict[str, object]]:
    rows = []
    for index, local in enumerate(projection, start=1):
        alpha = local["alpha"]
        for beta in betas:
            e0, residual0, dim0 = ground_energy(0, bonds(alpha, beta))
            e1, residual1, dim1 = ground_energy(1, bonds(alpha, beta))
            jeff = beta * local["jeff_over_beta"]
            e_eff = 2.0 * local["ground_energy"] - 0.75 * jeff
            coefficient = (e0 - e_eff) / beta**2
            rows.append(
                {
                    "alpha": alpha,
                    "beta": beta,
                    "local_gap": local["local_gap"],
                    "c1c5": local["c1"] * local["c5"],
                    "J_eff_over_beta": local["jeff_over_beta"],
                    "energy_residual": e0 - e_eff,
                    "coefficient_C2_at_beta": coefficient,
                    "gap_ratio": (e1 - e0) / jeff,
                    "max_eigensolver_residual": max(residual0, residual1),
                    "dimension_sz0": dim0,
                    "dimension_sz1": dim1,
                    "alpha_index": index,
                }
            )
        if index % 10 == 0:
            print(f"已完成 alpha {index}/{len(projection)}", flush=True)
    return rows


def summarize(rows: list[dict[str, object]], betas: tuple[float, ...]) -> list[dict[str, object]]:
    grouped: dict[float, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[float(row["alpha"])].append(row)
    summary = []
    for alpha in sorted(grouped):
        points = sorted(grouped[alpha], key=lambda row: float(row["beta"]))
        beta_array = np.asarray([float(row["beta"]) for row in points])
        coefficient_array = np.asarray([float(row["coefficient_C2_at_beta"]) for row in points])
        c0, c1 = fit_intercept(beta_array, coefficient_array)
        c0_pair, _ = fit_intercept(beta_array[:2], coefficient_array[:2])
        local_gap = float(points[0]["local_gap"])
        c1c5 = float(points[0]["c1c5"])
        scaled = -c0 * local_gap / c1c5
        scaled_pair = -c0_pair * local_gap / c1c5
        summary.append(
            {
                "alpha": alpha,
                "local_gap": local_gap,
                "c1c5": c1c5,
                "C2_intercept": c0,
                "C2_slope_in_beta": c1,
                "C2_intercept_first_two": c0_pair,
                "scaled_virtual_coefficient": scaled,
                "scaled_first_two": scaled_pair,
                "window_shift": scaled - scaled_pair,
                "max_eigensolver_residual": max(float(row["max_eigensolver_residual"]) for row in points),
                "gap_ratio_at_smallest_beta": float(points[0]["gap_ratio"]),
                "beta_min": min(betas),
                "beta_max": max(betas),
            }
        )
    return summary


def legacy_crosscheck(summary: list[dict[str, object]]) -> list[dict[str, object]]:
    legacy = read_csv(LEGACY)
    grouped: dict[float, list[dict[str, str]]] = defaultdict(list)
    for row in legacy:
        if float(row["beta"]) <= 0.01:
            grouped[float(row["alpha"])].append(row)
    by_alpha = {float(row["alpha"]): row for row in summary}
    rows = []
    for alpha, points in sorted(grouped.items()):
        x = np.asarray([float(row["beta"]) for row in points])
        y = np.asarray([float(row["energy_residual_over_beta2"]) for row in points])
        intercept, _ = fit_intercept(x, y)
        current = float(by_alpha[alpha]["C2_intercept"])
        rows.append(
            {
                "alpha": alpha,
                "legacy_C2_intercept": intercept,
                "new_C2_intercept": current,
                "relative_difference": (current - intercept) / abs(intercept),
            }
        )
    return rows


def make_figure(summary: list[dict[str, object]], rows: list[dict[str, object]]) -> None:
    colors = ["#3B6FB6", "#2A9D8F", "#D28E2C"]
    alpha_array = np.asarray([float(row["alpha"]) for row in summary])
    scaled = np.asarray([float(row["scaled_virtual_coefficient"]) for row in summary])
    scaled_pair = np.asarray([float(row["scaled_first_two"]) for row in summary])
    x = np.asarray([-float(row["c1c5"]) / float(row["local_gap"]) for row in summary])
    c2 = np.asarray([float(row["C2_intercept"]) for row in summary])
    width = 183 / 25.4
    fig, axes = plt.subplots(1, 3, figsize=(width, 3.0), gridspec_kw={"width_ratios": [1.25, 1.2, 1]})
    axes[0].plot(alpha_array, scaled, color="#2A6FBB", lw=1.2, label="3-point intercept")
    axes[0].plot(alpha_array, scaled_pair, color="#888888", lw=0.8, ls="--", label="2-point check")
    axes[0].axhline(np.mean(scaled), color="black", lw=0.9, ls=":")
    axes[0].fill_between(alpha_array, np.min(scaled), np.max(scaled), color="#2A6FBB", alpha=0.06)
    axes[0].set(xlabel=r"$\alpha$", ylabel=r"$-C_2\,\Delta_{\rm local}/(c_1c_5)$")
    axes[0].legend(fontsize=5.5)
    axes[1].scatter(x, -c2, c=alpha_array, cmap="viridis", s=13, zorder=3)
    slope = np.sum(x * (-c2)) / np.sum(x * x)
    grid = np.linspace(x.min(), x.max(), 100)
    axes[1].plot(grid, slope * grid, color="black", lw=1.0, label=rf"zero-intercept slope={slope:.3f}")
    axes[1].set(xlabel=r"$c_1c_5/\Delta_{\rm local}$", ylabel=r"$-C_2$", title="virtual correction")
    axes[1].legend(fontsize=5.5)
    for color, alpha in zip(colors, (0.14, 0.23, 0.33)):
        points = sorted([row for row in rows if math.isclose(float(row["alpha"]), alpha)], key=lambda row: float(row["beta"]))
        axes[2].plot(
            [float(row["beta"]) for row in points],
            [float(row["coefficient_C2_at_beta"]) for row in points],
            "o-",
            color=color,
            ms=3,
            label=rf"$\alpha={alpha:g}$",
        )
    axes[2].set(xlabel=r"$\beta$", ylabel=r"$C_2(\beta)$")
    axes[2].legend(fontsize=5.5)
    for index, axis in enumerate(axes):
        axis.text(-0.18, 1.04, chr(ord("a") + index), transform=axis.transAxes, fontweight="bold", fontsize=8)
    fig.tight_layout(w_pad=1.5)
    base = OUTDIR / "second_order_virtual_correction"
    fig.savefig(base.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(base.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(base.with_suffix(".tiff"), dpi=600, bbox_inches="tight", pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--betas", nargs="+", type=float, default=[0.001, 0.0025, 0.005])
    args = parser.parse_args()
    betas = tuple(sorted(args.betas))
    if len(betas) < 3 or min(betas) <= 0:
        raise SystemExit("至少需要三个正 beta")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    projection = load_projection()
    rows = calculate(projection, betas)
    summary = summarize(rows, betas)
    crosscheck = legacy_crosscheck(summary)
    scaled = np.asarray([float(row["scaled_virtual_coefficient"]) for row in summary])
    summary_json = {
        "status": "candidate_new_direction",
        "claim": "全正 alpha 扫描显示二阶虚激发修正近似由 c1*c5/local_gap 控制，但目前只由两胞 ED 支持。",
        "alpha_points": len(summary),
        "beta_points_per_alpha": len(betas),
        "ed_cells": len(rows) * 2,
        "betas": betas,
        "scaled_coefficient_mean": float(np.mean(scaled)),
        "scaled_coefficient_std": float(np.std(scaled, ddof=1)),
        "scaled_coefficient_min": float(np.min(scaled)),
        "scaled_coefficient_max": float(np.max(scaled)),
        "scaled_coefficient_cv": float(np.std(scaled, ddof=1) / abs(np.mean(scaled))),
        "max_window_shift": float(max(abs(float(row["window_shift"])) for row in summary)),
        "max_eigensolver_residual": float(max(float(row["max_eigensolver_residual"]) for row in summary)),
        "legacy_window_crosscheck": crosscheck,
        "figure_contract": {
            "core_conclusion": "C2 的 alpha 依赖主要被 local_gap 和边界投影系数吸收，剩余无量纲系数是否普适仍待三胞 Schrieffer-Wolff 交叉验证。",
            "evidence_chain": ["a: 全正 alpha 的缩放系数", "b: C2 与 c1c5/local_gap 的线性关系", "c: beta 窗口稳定性"],
            "archetype": "quantitative grid",
            "backend": "Python/matplotlib",
            "export": "183 mm；SVG/PDF；PNG 300 dpi；LZW TIFF 600 dpi",
        },
    }
    write_csv(OUTDIR / "two_pentamer_second_order.csv", rows)
    write_csv(OUTDIR / "second_order_summary.csv", summary)
    write_csv(OUTDIR / "legacy_window_crosscheck.csv", crosscheck)
    make_figure(summary, rows)
    (OUTDIR / "summary.json").write_text(json.dumps(summary_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUTDIR / "run-command.txt").write_text(" ".join([sys.executable, str(Path(__file__)), "--betas", *[str(beta) for beta in betas]]) + "\n", encoding="utf-8")
    files = sorted(path for path in OUTDIR.iterdir() if path.name != "checksums.sha256")
    (OUTDIR / "checksums.sha256").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in files if path.is_file()), encoding="utf-8")
    print(json.dumps(summary_json, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
