#!/usr/bin/env python3
"""从旧正区地图中选择最小静态验证路径。"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import gaussian_filter


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "results" / "five_rounds_20260729" / "round1_inventory" / "positive_phase_map_clean.csv"
OUTDIR = ROOT / "results" / "autoresearch_v5_20260730" / "round6_positive_static_selection"
FIGURE = OUTDIR / "positive_static_selection_20260730.png"
TARGET_BETAS = (0.10, 0.50, 0.90)
SMOOTHING_SCALES = (0.0, 0.6, 1.0, 1.4)
MAX_RIDGE_ALPHA = 0.30


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_grid() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rows: list[dict[str, float]] = []
    with SOURCE.open(encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            row = {key: float(raw[key]) for key in ("alpha", "beta", "O_str", "energy")}
            if not all(math.isfinite(value) for value in row.values()):
                raise ValueError(f"发现非有限值: {row}")
            if row["alpha"] < 0 or row["beta"] < 0:
                raise ValueError(f"发现范围外点: {row}")
            rows.append(row)

    alphas = np.asarray(sorted({row["alpha"] for row in rows}))
    betas = np.asarray(sorted({row["beta"] for row in rows}))
    order = np.full((betas.size, alphas.size), np.nan)
    energy = np.full_like(order, np.nan)
    alpha_index = {value: index for index, value in enumerate(alphas)}
    beta_index = {value: index for index, value in enumerate(betas)}
    for row in rows:
        i = beta_index[row["beta"]]
        j = alpha_index[row["alpha"]]
        if np.isfinite(order[i, j]):
            raise ValueError(f"发现重复网格点: alpha={row['alpha']}, beta={row['beta']}")
        order[i, j] = row["O_str"]
        energy[i, j] = row["energy"]
    if np.isnan(order).any() or np.isnan(energy).any():
        raise ValueError("正区网格不完整")
    return alphas, betas, order, energy


def ridge_track(
    alphas: np.ndarray,
    order: np.ndarray,
    sigma: float,
) -> tuple[np.ndarray, np.ndarray]:
    if sigma == 0:
        smooth = order.copy()
    else:
        smooth = gaussian_filter(order, sigma=(0.65 * sigma, sigma), mode="nearest")
    gradient = np.abs(np.gradient(smooth, alphas, axis=1))
    valid = np.flatnonzero((alphas > alphas[0]) & (alphas <= MAX_RIDGE_ALPHA))
    track = np.empty(order.shape[0])
    for i, row in enumerate(gradient):
        local = [j for j in valid if row[j] >= row[j - 1] and row[j] >= row[j + 1]]
        candidates = np.asarray(local if local else valid, dtype=int)
        track[i] = alphas[candidates[int(np.argmax(row[candidates]))]]
    return track, gradient


def nearest_index(values: np.ndarray, target: float) -> int:
    return int(np.argmin(np.abs(values - target)))


def build_anchor_rows(
    alphas: np.ndarray,
    betas: np.ndarray,
    tracks: dict[float, np.ndarray],
    gradients: dict[float, np.ndarray],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    anchor_rows: list[dict[str, object]] = []
    validation_rows: list[dict[str, object]] = []
    alpha_step = float(np.median(np.diff(alphas)))

    for group, requested_beta in enumerate(TARGET_BETAS, start=1):
        beta_index = nearest_index(betas, requested_beta)
        beta_window = range(max(0, beta_index - 2), min(len(betas), beta_index + 3))
        samples = np.asarray([
            tracks[sigma][i]
            for sigma in SMOOTHING_SCALES
            for i in beta_window
        ])
        consensus_alpha = float(alphas[nearest_index(alphas, float(np.median(samples)))])
        consensus_fraction = float(np.mean(np.abs(samples - consensus_alpha) <= alpha_step + 1e-12))
        target_samples = np.asarray([tracks[sigma][beta_index] for sigma in SMOOTHING_SCALES])
        target_span = float(np.ptp(target_samples))
        alpha_index = nearest_index(alphas, consensus_alpha)
        reference_gradient = gradients[1.0][beta_index]
        valid = (alphas > alphas[0]) & (alphas <= MAX_RIDGE_ALPHA)
        ridge_gradient = float(reference_gradient[alpha_index])
        gradient_ratio = ridge_gradient / float(np.median(reference_gradient[valid]))
        peak_fraction = ridge_gradient / float(np.max(reference_gradient[valid]))
        anchor_rows.append({
            "group": group,
            "requested_beta": requested_beta,
            "map_beta": float(betas[beta_index]),
            "ridge_alpha": consensus_alpha,
            "consensus_fraction": consensus_fraction,
            "target_scale_span": target_span,
            "gradient_to_row_median": gradient_ratio,
            "gradient_to_row_peak": peak_fraction,
            "interpretation": "candidate_cross_over_scale_not_phase_boundary",
        })

        for offset, role in ((-1, "left"), (0, "ridge"), (1, "right")):
            point_index = min(max(alpha_index + offset, 0), len(alphas) - 1)
            validation_rows.append({
                "group": group,
                "alpha": float(alphas[point_index]),
                "beta": requested_beta,
                "map_beta": float(betas[beta_index]),
                "role": role,
                "sizes": "40;60;80",
                "required_observables": "energy;variance;truncation;actual_D;spin_gap;bond_corr;O_str;Schmidt",
                "reuse_exact_beta_half": bool(
                    abs(requested_beta - 0.5) < 1e-12
                    and any(abs(alphas[point_index] - value) < 1e-12 for value in (0.10, 0.20, 0.25, 0.30, 0.40, 0.50))
                ),
            })
    return anchor_rows, validation_rows


def plot_selection(
    alphas: np.ndarray,
    betas: np.ndarray,
    order: np.ndarray,
    tracks: dict[float, np.ndarray],
    anchors: list[dict[str, object]],
    validation_rows: list[dict[str, object]],
) -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
        "font.size": 7,
        "axes.linewidth": 0.8,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "legend.frameon": False,
        "svg.fonttype": "none",
    })
    fig, axes = plt.subplots(2, 2, figsize=(8.0, 6.0), constrained_layout=True)
    ax_map, ax_track, ax_slice, ax_score = axes.ravel()

    image = ax_map.pcolormesh(alphas, betas, order, shading="nearest", cmap="viridis")
    fig.colorbar(image, ax=ax_map, label=r"legacy $O_{str}$")
    for sigma, color in zip(SMOOTHING_SCALES, ("#F6C85F", "#F28E2B", "#E15759", "#B13F64")):
        ax_map.plot(tracks[sigma], betas, color=color, lw=0.85, alpha=0.78, label=rf"$\sigma={sigma:g}$")
    ax_map.scatter(
        [float(row["ridge_alpha"]) for row in anchors],
        [float(row["map_beta"]) for row in anchors],
        s=34, marker="x", color="white", linewidths=1.5, zorder=5,
    )
    ax_map.set(xlabel=r"$\alpha$", ylabel=r"$\beta$", title="Legacy map and multiscale ridge")
    ax_map.legend(loc="lower right", ncol=2, fontsize=5.8)

    stack = np.stack([tracks[sigma] for sigma in SMOOTHING_SCALES])
    median = np.median(stack, axis=0)
    ax_track.fill_between(betas, np.min(stack, axis=0), np.max(stack, axis=0), color="#B8C4CE", alpha=0.7)
    ax_track.plot(betas, median, color="#1F4E79", lw=1.7, label="scale median")
    ax_track.scatter(
        [float(row["map_beta"]) for row in anchors],
        [float(row["ridge_alpha"]) for row in anchors],
        color="#C23B22", s=24, zorder=4, label="selected anchor",
    )
    ax_track.set(xlabel=r"$\beta$", ylabel=r"ridge $\alpha$", title="Ridge drift and scale envelope")
    ax_track.set_ylim(0.0, 0.31)
    ax_track.legend(loc="upper left")

    colors = ("#1F77B4", "#2A9D8F", "#C23B22")
    for anchor, color in zip(anchors, colors):
        beta_index = nearest_index(betas, float(anchor["map_beta"]))
        ax_slice.plot(alphas, order[beta_index], color=color, lw=1.5,
                      label=rf"$\beta\approx{float(anchor['map_beta']):.3f}$")
        selected = [row for row in validation_rows if int(row["group"]) == int(anchor["group"])]
        for row in selected:
            alpha_index = nearest_index(alphas, float(row["alpha"]))
            ax_slice.scatter(alphas[alpha_index], order[beta_index, alpha_index], s=18,
                             facecolor="white", edgecolor=color, zorder=4)
    ax_slice.set_xlim(0.0, 0.32)
    ax_slice.set(xlabel=r"$\alpha$", ylabel=r"legacy $O_{str}$", title="Three bracketed validation paths")
    ax_slice.legend(loc="lower right")

    x = np.arange(len(anchors))
    consensus = np.asarray([float(row["consensus_fraction"]) for row in anchors])
    peak = np.asarray([float(row["gradient_to_row_peak"]) for row in anchors])
    width = 0.34
    ax_score.bar(x - width / 2, consensus, width, color="#4E79A7", label="multiscale persistence")
    ax_score.bar(x + width / 2, peak, width, color="#E28E2C", label="relative peak strength")
    ax_score.axhline(0.75, color="#555555", ls="--", lw=0.9)
    ax_score.set_xticks(x, [rf"$\beta={float(row['requested_beta']):.1f}$" for row in anchors])
    ax_score.set_ylim(0.0, 1.08)
    ax_score.set(ylabel="score", title="Reconnaissance stability scores")
    ax_score.legend(loc="lower right")

    for label, axis in zip("abcd", axes.ravel()):
        axis.text(-0.14, 1.04, label, transform=axis.transAxes, fontsize=9, fontweight="bold")
    fig.savefig(FIGURE, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    alphas, betas, order, energy = load_grid()
    tracks: dict[float, np.ndarray] = {}
    gradients: dict[float, np.ndarray] = {}
    for sigma in SMOOTHING_SCALES:
        tracks[sigma], gradients[sigma] = ridge_track(alphas, order, sigma)

    anchor_rows, validation_rows = build_anchor_rows(alphas, betas, tracks, gradients)
    write_csv(OUTDIR / "ridge_anchors.csv", anchor_rows)
    write_csv(OUTDIR / "validation_cells.csv", validation_rows)
    plot_selection(alphas, betas, order, tracks, anchor_rows, validation_rows)

    median_track = np.median(np.stack([tracks[sigma] for sigma in SMOOTHING_SCALES]), axis=0)
    monotone_fraction = float(np.mean(np.diff(median_track) >= -1e-12))
    checks = {
        "complete_40x60_grid": bool(order.shape == (60, 40)),
        "positive_domain_only": bool(alphas.min() >= 0 and betas.min() >= 0),
        "finite_values": bool(np.isfinite(order).all() and np.isfinite(energy).all()),
        "three_anchor_groups": len(anchor_rows) == 3,
        "nine_bracket_cells": len(validation_rows) == 9,
        "anchor_persistence_at_least_75pct": all(
            float(row["consensus_fraction"]) >= 0.75 for row in anchor_rows
        ),
        "anchor_scale_span_at_most_005": all(
            float(row["target_scale_span"]) <= 0.05 + 1e-12 for row in anchor_rows
        ),
    }
    summary = {
        "verdict": "stable_reconnaissance_ridge" if all(checks.values()) else "ridge_needs_review",
        "scope": "alpha>=0,beta>=0",
        "source_role": "reconnaissance_only",
        "source_sha256": sha256(SOURCE),
        "grid": {
            "alpha_count": int(alphas.size),
            "beta_count": int(betas.size),
            "point_count": int(order.size),
            "alpha_range": [float(alphas.min()), float(alphas.max())],
            "beta_range": [float(betas.min()), float(betas.max())],
        },
        "method": {
            "smoothing_scales_cells": list(SMOOTHING_SCALES),
            "ridge_axis": "maximum local abs(dO_str/dalpha) for alpha<=0.30",
            "beta_neighborhood_rows": 2,
            "selection": "three beta anchors, each bracketed by one alpha grid step",
        },
        "anchors": anchor_rows,
        "validation_cells": validation_rows,
        "median_track_non_decreasing_fraction": monotone_fraction,
        "checks": checks,
        "boundary": (
            "The legacy map lacks variance, truncation error, actual bond dimension, and size provenance. "
            "The selected ridge is a candidate crossover scale, not a phase boundary."
        ),
    }
    summary_path = OUTDIR / "selection_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    files = sorted(path for path in OUTDIR.iterdir() if path.is_file() and path.name != "checksums.sha256")
    (OUTDIR / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
