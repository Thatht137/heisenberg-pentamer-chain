#!/usr/bin/env python3
"""绘制严格 q=pi L=40 TEBD 收敛与稀疏 CV 锚点图。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


WIDTH_MM = 183.0
HEIGHT_MM = 105.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_columns(path: Path) -> dict[str, np.ndarray]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"空数据文件: {path}")
    return {
        key: np.asarray([float(row[key]) for row in rows], dtype=float)
        for key in rows[0]
        if key != "source_run"
    }


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "font.size": 7,
            "axes.labelsize": 7,
            "axes.titlesize": 7.5,
            "xtick.labelsize": 6.5,
            "ytick.labelsize": 6.5,
            "legend.fontsize": 6.3,
            "axes.linewidth": 0.7,
            "xtick.major.width": 0.7,
            "ytick.major.width": 0.7,
            "xtick.major.size": 3,
            "ytick.major.size": 3,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
        }
    )


def panel_label(axis: plt.Axes, label: str) -> None:
    axis.text(
        -0.085,
        1.03,
        label,
        transform=axis.transAxes,
        fontsize=8,
        fontweight="bold",
        va="bottom",
        ha="left",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-dir", required=True)
    parser.add_argument("--cv-dir", required=True)
    parser.add_argument("--output-base", required=True)
    args = parser.parse_args()

    analysis = Path(args.analysis_dir).resolve()
    cv_dir = Path(args.cv_dir).resolve()
    output_base = Path(args.output_base).resolve()
    summary_path = analysis / "summary.json"
    comparison_path = analysis / "spectrum_comparison.csv"
    cv_path = cv_dir / "spectrum.csv"
    cv_manifest_path = cv_dir / "manifest.json"
    summary = read_json(summary_path)
    cv_manifest = read_json(cv_manifest_path)
    comparison = read_columns(comparison_path)
    cv = read_columns(cv_path)
    if summary.get("tebd_qpi_tag") != "Agreement":
        raise SystemExit("严格 q=pi 时间步与窗口未通过，不生成通过型论文图")
    params = summary.get("params", {})
    cv_params = cv_manifest.get("params", {})
    cv_settings = cv_manifest.get("settings", {})
    same_instance = (
        float(params.get("alpha", -1.0)) == float(cv_params.get("alpha", -2.0))
        and float(params.get("beta", -1.0)) == float(cv_params.get("beta", -2.0))
        and int(params.get("L", -1)) == int(cv_params.get("L", -2))
        and float(params.get("q_over_pi", -1.0)) == float(cv_params.get("q_over_pi", -2.0))
        and float(params.get("eta", -1.0)) == float(cv_settings.get("eta", -2.0))
        and params.get("boundary") == cv_settings.get("boundary") == "OBC"
        and params.get("sector") == cv_settings.get("sector") == "Sz=0"
    )
    if not same_instance:
        raise SystemExit("TEBD 分析与 CV anchor 不是同一物理实例")
    targets = [
        output_base.with_suffix(suffix)
        for suffix in (".svg", ".pdf", ".tiff", ".png", ".sources.json")
    ]
    existing = [str(path) for path in targets if path.exists()]
    if existing:
        raise SystemExit(f"拒绝覆盖已有图: {existing}")
    output_base.parent.mkdir(parents=True, exist_ok=True)

    configure_style()
    figure = plt.figure(figsize=(WIDTH_MM / 25.4, HEIGHT_MM / 25.4))
    grid = figure.add_gridspec(
        2,
        2,
        height_ratios=[1.55, 1.0],
        width_ratios=[1.28, 0.72],
        hspace=0.42,
        wspace=0.34,
        left=0.085,
        right=0.985,
        bottom=0.13,
        top=0.96,
    )
    spectrum_axis = figure.add_subplot(grid[0, :])
    difference_axis = figure.add_subplot(grid[1, 0])
    gate_axis = figure.add_subplot(grid[1, 1])

    omega = comparison["omega"]
    refined = comparison["refined"]
    coarse = comparison["coarse"]
    diagnostics = summary["diagnostics"]
    coverage = summary.get("coverage", {})
    short_key = next(key for key in comparison if key.startswith("refined_tmax_"))
    short = comparison[short_key]
    maxdim_keys = sorted(key for key in comparison if key.startswith("maxdim_"))
    colors = {
        "refined": "#A63D40",
        "coarse": "#2F6690",
        "short": "#737373",
        "cv": "#2E7D5B",
        "maxdim": "#1B998B",
        "accent": "#D69E2E",
    }
    spectrum_axis.plot(omega, refined, color=colors["refined"], lw=1.8, label=r"TEBD $dt=0.0125$, $t_{max}=30$")
    spectrum_axis.plot(omega, coarse, color=colors["coarse"], lw=1.1, ls="--", label=r"TEBD $dt=0.025$, $t_{max}=30$")
    spectrum_axis.plot(omega, short, color=colors["short"], lw=1.0, ls=":", label=r"TEBD $dt=0.0125$, $t_{max}=25$")
    for maxdim_key in maxdim_keys:
        maxdim_value = comparison[maxdim_key]
        maxdim_label = maxdim_key.removeprefix("maxdim_")
        spectrum_axis.plot(
            omega,
            maxdim_value,
            color=colors["maxdim"],
            lw=1.0,
            ls="-.",
            label=fr"TEBD maxdim={maxdim_label}",
        )
    spectrum_axis.scatter(
        cv["omega"],
        cv["intensity"],
        s=24,
        facecolor="white",
        edgecolor=colors["cv"],
        linewidth=1.2,
        zorder=5,
        label=(
            "CV-DMRG grid"
            if coverage.get("cv_main_peak") and coverage.get("cv_major_weight")
            else "CV-DMRG sparse anchors"
        ),
    )
    spectrum_axis.set_xlim(float(omega.min()), float(omega.max()))
    spectrum_axis.set_ylim(bottom=0.0)
    spectrum_axis.set_xlabel(r"Frequency $\omega/J_1$")
    spectrum_axis.set_ylabel(r"$S^{zz}(q=\pi,\omega)$")
    spectrum_axis.legend(loc="upper right", ncol=2, columnspacing=1.1, handlelength=2.5)
    spectrum_axis.text(
        0.015,
        0.94,
        r"$\alpha=0.23$, $\beta=0.5$, $L=40$, $\eta=0.1$",
        transform=spectrum_axis.transAxes,
        va="top",
        color="#333333",
    )
    panel_label(spectrum_axis, "a")

    scale = max(float(refined.max()), 1e-30)
    difference_axis.plot(
        omega,
        np.abs(coarse - refined) / scale,
        color=colors["coarse"],
        lw=1.2,
        label=r"$dt$ vs $dt/2$",
    )
    difference_axis.plot(
        omega,
        np.abs(short - refined) / scale,
        color=colors["short"],
        lw=1.1,
        ls=":",
        label=r"$t_{max}=25$ vs 30",
    )
    for maxdim_key in maxdim_keys:
        reference_maxdim = diagnostics.get("maxdim", {}).get("reference_maxdim", 320)
        difference_axis.plot(
            omega,
            np.abs(comparison[maxdim_key] - refined) / scale,
            color=colors["maxdim"],
            lw=1.0,
            ls="-.",
            label=fr"maxdim={maxdim_key.removeprefix('maxdim_')} vs {reference_maxdim}",
        )
    difference_axis.set_xlim(float(omega.min()), float(omega.max()))
    difference_axis.set_xlabel(r"Frequency $\omega/J_1$")
    difference_axis.set_ylabel(r"$|\Delta S|/S_{max}$")
    difference_axis.legend(loc="upper right")
    difference_axis.axhline(0.0, color="#B7B7B7", lw=0.6)
    panel_label(difference_axis, "b")

    budgets = summary["budgets"]
    labels = ["dt peak", "dt weight", "time window"]
    ratios_list = [
        diagnostics["dt_peak_delta"] / budgets["dt_peak_omega"],
        diagnostics["dt_weight_relative_delta"]
        / budgets["dt_integrated_weight_relative"],
        diagnostics["time_window_peak_delta"] / budgets["tmax_peak_omega"],
    ]
    bar_colors = [colors["coarse"], colors["refined"], colors["short"]]
    maxdim_diagnostics = diagnostics.get("maxdim", {})
    if maxdim_keys and maxdim_diagnostics.get("peak_delta") is not None:
        labels.extend(["maxdim peak", "maxdim weight"])
        ratios_list.extend(
            [
                maxdim_diagnostics["peak_delta"] / budgets["maxdim_peak_omega"],
                maxdim_diagnostics["weight_relative_delta"]
                / budgets["maxdim_integrated_weight_relative"],
            ]
        )
        bar_colors.extend([colors["maxdim"], colors["maxdim"]])
    cv_diagnostics = diagnostics.get("cv", {})
    if cv_diagnostics.get("peak_delta") is not None:
        labels.extend(["CV peak", "CV weight"])
        ratios_list.extend(
            [
                cv_diagnostics["peak_delta"] / budgets["cv_peak_omega"],
                cv_diagnostics["integrated_weight_relative_delta"]
                / budgets["cv_integrated_weight_relative"],
            ]
        )
        bar_colors.extend([colors["cv"], colors["cv"]])
    ratios = np.asarray(ratios_list, dtype=float)
    positions = np.arange(len(labels))
    gate_axis.barh(
        positions,
        ratios,
        color=bar_colors,
        height=0.58,
    )
    gate_axis.axvline(1.0, color=colors["accent"], lw=1.1, ls="--", label="acceptance limit")
    gate_axis.set_yticks(positions, labels)
    gate_axis.invert_yaxis()
    gate_axis.set_xlabel("Fraction of acceptance limit")
    gate_axis.set_xlim(0.0, max(1.08, float(ratios.max()) * 1.15))
    gate_axis.legend(loc="lower right")
    for position, ratio in zip(positions, ratios):
        gate_axis.text(
            ratio + 0.025,
            position,
            f"{ratio:.3f}",
            va="center",
            ha="left",
            fontsize=6.2,
        )
    panel_label(gate_axis, "c")

    figure.savefig(output_base.with_suffix(".svg"))
    figure.savefig(output_base.with_suffix(".pdf"))
    figure.savefig(output_base.with_suffix(".tiff"), dpi=600)
    figure.savefig(output_base.with_suffix(".png"), dpi=300)
    plt.close(figure)

    sidecar = {
        "schema_version": 1,
        "figure_contract": {
            "core_conclusion": "L=40 q=pi TEBD is stable under dt/2, tmax=25 to 30, and an exercised second maxdim when supplied; CV is promoted to an Agreement only when its peak and weight windows are covered.",
            "archetype": "quantitative grid",
            "backend": "Python matplotlib only",
            "final_size_mm": [WIDTH_MM, HEIGHT_MM],
            "panel_map": {
                "a": "hero spectrum with TEBD convergence, optional maxdim curve, and CV anchors",
                "b": "frequency-resolved deviations from refined TEBD",
                "c": "pre-registered acceptance-budget usage for TEBD and optional cross-method gates",
            },
            "reviewer_risk": "A missing or unexercised maxdim cap remains an evidence gap; incomplete CV coverage is labeled NotEvaluable rather than treated as agreement.",
        },
        "inputs": {
            str(summary_path): sha256(summary_path),
            str(comparison_path): sha256(comparison_path),
            str(cv_path): sha256(cv_path),
            str(cv_manifest_path): sha256(cv_manifest_path),
        },
        "outputs": {
            path.suffix.lstrip("."): sha256(path)
            for path in targets[:-1]
        },
        "qa": {
            "editable_svg_text": True,
            "pdf_fonttype": 42,
            "tiff_dpi": 600,
            "png_dpi": 300,
            "statistics": "deterministic tensor-network convergence; no sampling error bars",
            "source_data": str(comparison_path),
            "image_adjustments": "none",
        },
        "scope": {
            "negative_alpha_excluded": True,
            "figure_9_excluded": True,
            "full_dynamic_status": summary.get("full_dynamic_status"),
            "cross_method_tag": summary.get("cross_method_tag"),
        },
    }
    sidecar_path = output_base.with_suffix(".sources.json")
    sidecar_path.write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"figure": str(output_base), "status": "pass"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
