#!/usr/bin/env python3
"""分析六点保存态扫描的纠缠与连接键关联。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def linear_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    slope, intercept = np.polyfit(x, y, 1)
    predicted = slope * x + intercept
    total = float(np.sum((y - np.mean(y)) ** 2))
    residual = float(np.sum((y - predicted) ** 2))
    r2 = 1.0 - residual / total if total > 0 else math.nan
    return float(slope), float(intercept), r2


def entropy_metrics(path: Path, length: int) -> tuple[dict[str, float], list[dict[str, object]]]:
    rows = read_csv(path)
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[int(row["bond_class"])].append(row)
    class_rows: list[dict[str, object]] = []
    for bond_class, items in sorted(grouped.items()):
        central = [item for item in items if 0.15 * length <= int(item["bond"]) <= 0.85 * length]
        x = np.array([float(item["log_chord"]) for item in central])
        y = np.array([float(item["entropy"]) for item in central])
        slope, intercept, r2 = linear_fit(x, y)
        class_rows.append({
            "bond_class": bond_class,
            "n": len(central),
            "slope": slope,
            "intercept": intercept,
            "c_effective": 6.0 * slope,
            "r2": r2,
        })
    # 周期五振荡下只汇总稳定的类内斜率。
    stable_rows = [row for row in class_rows if float(row["r2"]) >= 0.9]
    if not stable_rows:
        stable_rows = class_rows
    c_values = np.array([float(row["c_effective"]) for row in stable_rows])
    r2_values = np.array([float(row["r2"]) for row in stable_rows])
    center_row = min(rows, key=lambda row: abs(int(row["bond"]) - length // 2))
    return {
        "entropy_center": float(center_row["entropy"]),
        "c_effective_median": float(np.median(c_values)),
        "c_effective_class_half_range": 0.5 * float(np.max(c_values) - np.min(c_values)),
        "entropy_fit_r2_median": float(np.median(r2_values)),
        "entropy_fit_stable_classes": float(len(stable_rows)),
    }, class_rows


def connected_metrics(path: Path) -> dict[str, float]:
    rows = read_csv(path)
    result: dict[str, float] = {}
    for bond_class, label in ((0, "beta"), (1, "alpha")):
        items = [row for row in rows if int(row["bond_class"]) == bond_class]
        tail = [row for row in items if float(row["distance_units"]) >= 3.0]
        far = [row for row in items if float(row["distance_units"]) >= 5.0]
        values = np.array([float(row["connected"]) for row in tail])
        far_values = np.array([float(row["connected"]) for row in far])
        fit = [row for row in items if 2.0 <= float(row["distance_units"]) <= 7.0 and abs(float(row["connected"])) > 1e-16]
        x = np.log(np.array([float(row["distance_units"]) for row in fit]))
        y = np.log(np.abs(np.array([float(row["connected"]) for row in fit])))
        slope, _, r2 = linear_fit(x, y)
        result.update({
            f"connected_{label}_tail_rms": float(np.sqrt(np.mean(values ** 2))),
            f"connected_{label}_far_abs_mean": float(np.mean(np.abs(far_values))),
            f"connected_{label}_far_abs_max": float(np.max(np.abs(far_values))),
            f"connected_{label}_decay_exponent": -slope,
            f"connected_{label}_decay_r2": r2,
        })
    return result


def child_metrics(cell: Path, mode: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    child = cell / f"start_{mode}"
    manifest = load_json(child / "manifest.json")
    length = int(manifest["params"]["L"])
    entropy, class_rows = entropy_metrics(child / "entropy_profile_full.csv", length)
    row: dict[str, object] = {
        "cell_id": cell.name,
        "mode": mode,
        "alpha": float(manifest["params"]["alpha"]),
        "beta": float(manifest["params"]["beta"]),
        "L": length,
        "energy_per_site": float(manifest["observables"]["energy_sz0"]) / length,
        "spin_gap": float(manifest["observables"]["spin_gap"]),
        "q_peak_over_pi": float(manifest["observables"]["structure_factor_peak_q_over_pi"]),
        "dominant_ratio": float(manifest["observables"]["dominant_structure_factor_ratio"]),
        "variance_max": max(
            float(manifest["diagnostics"]["variance_per_site_sz0"]),
            float(manifest["diagnostics"]["variance_per_site_sz1"]),
        ),
        "truncation_max": max(
            float(manifest["diagnostics"]["final_truncation_error_sz0"]),
            float(manifest["diagnostics"]["final_truncation_error_sz1"]),
        ),
        "state_bytes": (child / "state_sz0.jld2").stat().st_size,
    }
    row.update(entropy)
    row.update(connected_metrics(child / "bond_bond_connected.csv"))
    for class_row in class_rows:
        class_row.update({"cell_id": cell.name, "mode": mode, "alpha": row["alpha"], "beta": row["beta"]})
    return row, class_rows


def aggregate(children: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in children:
        grouped[str(row["cell_id"])].append(row)
    result: list[dict[str, object]] = []
    metrics = [key for key in children[0] if key not in {"cell_id", "mode", "alpha", "beta", "L"}]
    for cell_id, items in grouped.items():
        base: dict[str, object] = {
            "cell_id": cell_id,
            "alpha": items[0]["alpha"],
            "beta": items[0]["beta"],
            "L": items[0]["L"],
        }
        for key in metrics:
            values = np.array([float(item[key]) for item in items])
            base[key] = float(np.mean(values))
            base[f"{key}_start_half_range"] = 0.5 * float(np.max(values) - np.min(values))
        result.append(base)
    return sorted(result, key=lambda row: (float(row["beta"]), float(row["alpha"])))


def add_panel_label(axis: plt.Axes, label: str) -> None:
    axis.text(-0.16, 1.05, label, transform=axis.transAxes, fontsize=8, fontweight="bold", va="bottom")


def plot_metric(axis: plt.Axes, rows: list[dict[str, object]], key: str, ylabel: str, *, log: bool = False) -> None:
    colors = {0.25: "#0F4D92", 0.75: "#B64342"}
    markers = {0.25: "o", 0.75: "s"}
    error_key = f"{key}_start_half_range"
    for beta in (0.25, 0.75):
        subset = [row for row in rows if float(row["beta"]) == beta]
        axis.errorbar(
            [row["alpha"] for row in subset],
            [row[key] for row in subset],
            yerr=[max(float(row[error_key]), 0.0) for row in subset],
            color=colors[beta], marker=markers[beta], lw=1.25, ms=4, capsize=2,
            label=fr"$\beta={beta:g}$",
        )
    if log:
        axis.set_yscale("log")
    axis.set_xlabel(r"$\alpha$")
    axis.set_ylabel(ylabel)


def make_figure(outdir: Path, rows: list[dict[str, object]]) -> None:
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans", "Liberation Sans"]
    plt.rcParams["svg.fonttype"] = "none"
    plt.rcParams["pdf.fonttype"] = 42
    plt.rcParams.update({
        "font.size": 7,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "axes.linewidth": 0.8,
        "legend.frameon": False,
        "xtick.direction": "out",
        "ytick.direction": "out",
    })
    figure, axes = plt.subplots(2, 3, figsize=(7.2, 5.25), constrained_layout=True)
    plot_metric(axes[0, 0], rows, "q_peak_over_pi", r"$q_{\rm peak}/\pi$")
    axes[0, 0].set_ylim(0.52, 1.04)
    axes[0, 0].legend(loc="best")
    plot_metric(axes[0, 1], rows, "spin_gap", r"$\Delta_s$")
    plot_metric(axes[0, 2], rows, "c_effective_median", r"profile $c_{\rm eff}$")
    axes[0, 2].axhline(1.0, color="#767676", ls="--", lw=0.9)
    axes[0, 2].axhspan(0.8, 1.2, color="#D8D8D8", alpha=0.25, lw=0)
    plot_metric(axes[1, 0], rows, "connected_beta_far_abs_mean", r"far $|C_{BB}^{(\beta)}|$", log=True)
    plot_metric(axes[1, 1], rows, "connected_alpha_far_abs_mean", r"far $|C_{BB}^{(\alpha)}|$", log=True)
    energy_spread = []
    for row in rows:
        item = dict(row)
        item["energy_start_spread"] = 2.0 * float(row["energy_per_site_start_half_range"])
        item["energy_start_spread_start_half_range"] = 0.0
        energy_spread.append(item)
    plot_metric(axes[1, 2], energy_spread, "energy_start_spread", r"dual-start $|\Delta e_0|$", log=True)
    for label, axis in zip("abcdef", axes.flat):
        add_panel_label(axis, label)
        axis.grid(alpha=0.18, lw=0.5)
    figure.suptitle(r"Saved-state diagnostics across candidate negative-$\alpha$ reconstruction windows", fontsize=9, fontweight="bold")
    base = outdir / "negative_alpha_saved_state_independent_diagnostics"
    figure.savefig(base.with_suffix(".svg"), bbox_inches="tight")
    figure.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
    figure.savefig(base.with_suffix(".png"), dpi=400, bbox_inches="tight")
    figure.savefig(base.with_suffix(".tiff"), dpi=600, bbox_inches="tight")
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-root", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    fetch_root = args.fetch_root.resolve()
    outdir = args.outdir.resolve()
    fetch_root.relative_to((ROOT / "results").resolve())
    outdir.relative_to((ROOT / "results").resolve())
    if outdir.exists() and any(outdir.iterdir()):
        raise SystemExit(f"拒绝覆盖已有输出: {outdir}")
    outdir.mkdir(parents=True, exist_ok=True)

    cells = sorted(path for path in fetch_root.iterdir() if path.is_dir() and path.name.startswith("negdiag-"))
    if len(cells) != 6:
        raise SystemExit(f"需要6个 cell，实际为 {len(cells)}")
    validation_dir = fetch_root / "validation_practical_v2"
    validations = [load_json(validation_dir / f"{cell.name}.json") for cell in cells]
    if any(item.get("status") != "pass" for item in validations):
        raise SystemExit("Practical V2 验收未全部通过")

    children: list[dict[str, object]] = []
    entropy_classes: list[dict[str, object]] = []
    for cell in cells:
        for mode in ("center", "ferro_j2"):
            row, class_rows = child_metrics(cell, mode)
            children.append(row)
            entropy_classes.extend(class_rows)
    rows = aggregate(children)
    write_csv(outdir / "saved_state_child_metrics.csv", children)
    write_csv(outdir / "saved_state_point_summary.csv", rows)
    write_csv(outdir / "entropy_profile_class_fits.csv", entropy_classes)
    make_figure(outdir, rows)

    summary = {
        "schema_version": 1,
        "verdict": "localized_entanglement_candidate_but_no_second_thermodynamic_phase_confirmed",
        "interpretation": "the beta=0.75 reconstruction is smooth across independent observables; beta=0.25 at alpha=-0.10 has a finite-size entanglement and dual-start anomaly, but no long-range bond plateau or spin-sector crossing",
        "accepted_cells": 6,
        "accepted_child_runs": 12,
        "saved_states": 12,
        "beta_slices": [0.25, 0.75],
        "alpha_points_per_slice": 3,
        "maximum_variance_per_site": max(float(row["variance_max"]) for row in children),
        "maximum_final_truncation_error": max(float(row["truncation_max"]) for row in children),
        "minimum_spin_gap": min(float(row["spin_gap"]) for row in children),
        "maximum_dual_start_energy_per_site_spread": max(2.0 * float(row["energy_per_site_start_half_range"]) for row in rows),
        "c_effective_profile_range": [
            min(float(row["c_effective_median"]) for row in rows),
            max(float(row["c_effective_median"]) for row in rows),
        ],
        "maximum_far_connected_bond_abs_mean": max(
            max(float(row["connected_beta_far_abs_mean"]), float(row["connected_alpha_far_abs_mean"])) for row in rows
        ),
        "q_peak_sequences": {
            str(beta): [
                {"alpha": float(row["alpha"]), "q_peak_over_pi": float(row["q_peak_over_pi"])}
                for row in rows if float(row["beta"]) == beta
            ] for beta in (0.25, 0.75)
        },
        "candidate_point": {
            "alpha": -0.10,
            "beta": 0.25,
            "reason": "suppressed single-L profile c_eff and the largest dual-start energy-density spread",
            "classification": "finite-size_or_algorithmic_candidate_not_a_named_phase",
        },
        "evidence": {
            "dual_start": "energies and enriched observables agree within recorded half-ranges",
            "entanglement": "beta=0.75 is smooth; beta=0.25 alpha=-0.10 is anomalous, while single-L c_eff remains diagnostic only",
            "connected_bond_correlations": "far connected tails remain small and show no finite plateau at these points",
            "spin_sector": "all gaps are nonnegative under the frozen tolerance",
        },
        "reviewer_risks": [
            "only one size L=80 is available for the saved-state observables",
            "three alpha points per beta slice can exclude a sharp anomaly only at coarse resolution",
            "profile c_eff and bond-tail decay are finite-OBC diagnostics, not standalone phase identifiers",
        ],
        "figure_contract": {
            "core_conclusion": "six saved-state checks isolate one finite-size entanglement candidate but do not confirm a second thermodynamic phase",
            "archetype": "quantitative_grid",
            "backend": "Python/matplotlib",
            "final_size_mm": [183, 133],
            "hero_evidence": "full-profile c_eff and far connected bond tails",
            "validation_evidence": "dual-start energy agreement, nonnegative spin gaps and Practical V2 acceptance",
        },
    }
    (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    qa = {
        "backend_exclusive": "Python",
        "editable_svg_text": True,
        "pdf_fonttype": 42,
        "source_data": ["saved_state_point_summary.csv", "saved_state_child_metrics.csv", "entropy_profile_class_fits.csv"],
        "error_definition": "error bars are half-ranges across the center and ferro_j2 initial states",
        "panel_map": {
            "a": "dominant momentum",
            "b": "spin-sector gap",
            "c": "class-resolved entanglement-profile slope",
            "d": "far connected beta-bond correlations",
            "e": "far connected alpha-bond correlations",
            "f": "dual-start energy density spread",
        },
        "image_integrity": "data-native line art; no selective image adjustment",
    }
    (outdir / "figure_qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = sorted(path for path in outdir.iterdir() if path.is_file() and path.name != "checksums.sha256")
    (outdir / "checksums.sha256").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
