#!/usr/bin/env python3
"""绘制五聚体模型、有效链和动量过滤机制的正式图。"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PROJECTION_DIR = ROOT / "results" / "autoresearch_v3_20260729" / "round1_doublet_projection"
SPECTRAL_DIR = ROOT / "results" / "autoresearch_v4_20260730" / "round2_local_spectral_channels_v4"
OUTDIR = ROOT / "results" / "autoresearch_v5_20260731" / "round9_model_mechanism_figures"
MODEL_BASE = ROOT / "figures" / "pentamer_model_effective_chain_20260731"
FILTER_BASE = ROOT / "figures" / "pentamer_momentum_filter_20260731"
ALPHA_REP = 0.23

BLUE = "#235789"
TEAL = "#2A9D8F"
ORANGE = "#E09F3E"
RED = "#B23A48"
GRAY = "#666666"
LIGHT_BLUE = "#EAF2F8"
LIGHT_TEAL = "#E8F5F2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def configure_matplotlib() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "font.size": 7,
        "axes.linewidth": 0.8,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "legend.frameon": False,
        "axes.labelpad": 2.5,
    })


def save_figure(fig: plt.Figure, base: Path) -> list[Path]:
    outputs: list[Path] = []
    for suffix in (".svg", ".pdf", ".png", ".tiff"):
        path = base.with_suffix(suffix)
        kwargs: dict[str, object] = {"bbox_inches": "tight"}
        if suffix in {".png", ".tiff"}:
            kwargs["dpi"] = 600
        if suffix == ".tiff":
            kwargs["pil_kwargs"] = {"compression": "tiff_lzw"}
        fig.savefig(path, **kwargs)
        outputs.append(path)
    plt.close(fig)
    return outputs


def panel_label(ax: plt.Axes, label: str, x: float = -0.08) -> None:
    ax.text(x, 1.03, label, transform=ax.transAxes, fontsize=9,
            fontweight="bold", va="bottom")


def draw_spin(ax: plt.Axes, x: float, y: float, color: str, radius: float = 0.17) -> None:
    ax.add_patch(Circle((x, y), radius, facecolor="white", edgecolor=color, lw=1.5, zorder=3))
    ax.add_patch(FancyArrowPatch(
        (x, y - 0.08), (x, y + 0.11), arrowstyle="-|>", mutation_scale=7,
        color=color, lw=1.1, zorder=4,
    ))


def draw_model_panel(ax: plt.Axes) -> None:
    ax.set_xlim(-0.65, 10.0)
    ax.set_ylim(-1.2, 1.5)
    ax.axis("off")
    for start in (0.0, 5.0):
        ax.add_patch(FancyBboxPatch(
            (start - 0.38, 0.34), 4.76, 0.88,
            boxstyle="round,pad=0.03,rounding_size=0.06",
            facecolor=LIGHT_BLUE, edgecolor="#AFC7DC", lw=0.8, zorder=0,
        ))
    bond_types = [
        (0, 1, ORANGE, r"$J_2=\alpha$"),
        (1, 2, BLUE, r"$J_1=1$"),
        (2, 3, BLUE, ""),
        (3, 4, ORANGE, ""),
        (4, 5, TEAL, r"$J_3=\beta$"),
        (5, 6, ORANGE, r"$J_2=\alpha$"),
        (6, 7, BLUE, r"$J_1=1$"),
        (7, 8, BLUE, ""),
        (8, 9, ORANGE, ""),
    ]
    for left, right, color, label in bond_types:
        ax.plot([left, right], [0.78, 0.78], color=color, lw=3.0, solid_capstyle="round", zorder=1)
        if label:
            y = 1.31 if left != 4 else 0.17
            ax.text((left + right) / 2, y, label, color=color, ha="center", va="center")
    for site in range(10):
        draw_spin(ax, float(site), 0.78, BLUE)
    ax.text(2.0, 0.40, "pentamer $n$", ha="center", va="center", color=GRAY)
    ax.text(7.0, 0.40, "pentamer $n+1$", ha="center", va="center", color=GRAY)

    ax.annotate("low-energy projection", xy=(4.5, -0.19), xytext=(4.5, 0.04),
                ha="center", va="center", color=GRAY,
                arrowprops={"arrowstyle": "-|>", "color": GRAY, "lw": 0.9})
    for x in (2.0, 7.0):
        draw_spin(ax, x, -0.78, TEAL, radius=0.24)
        ax.text(x, -1.10, r"$\mathbf{T}_{%s}$" % ("n" if x == 2.0 else "n+1"),
                ha="center", va="center")
    ax.plot([2.0, 7.0], [-0.78, -0.78], color=TEAL, lw=3.2, solid_capstyle="round")
    ax.text(4.5, -0.53, r"$J_{\mathrm{eff}}=\beta c_1c_5>0$", color=TEAL,
            ha="center", va="center", fontsize=7.5)
    panel_label(ax, "a", -0.02)


def plot_model_figure(projection: list[dict[str, str]]) -> tuple[list[Path], dict[str, float]]:
    rep = min(projection, key=lambda row: abs(float(row["alpha"]) - ALPHA_REP))
    coefficients = np.array([float(rep[f"c{i}"]) for i in range(1, 6)])
    alpha = np.array([float(row["alpha"]) for row in projection])
    jeff = np.array([float(row["jeff_over_beta"]) for row in projection])

    fig = plt.figure(figsize=(7.2, 4.0), constrained_layout=True)
    grid = fig.add_gridspec(2, 2, height_ratios=(1.24, 1.0), width_ratios=(1.0, 1.02))
    ax_model = fig.add_subplot(grid[0, :])
    ax_coeff = fig.add_subplot(grid[1, 0])
    ax_jeff = fig.add_subplot(grid[1, 1])
    draw_model_panel(ax_model)

    sites = np.arange(1, 6)
    colors = [BLUE if value >= 0 else ORANGE for value in coefficients]
    ax_coeff.axhline(0.0, color="#888888", lw=0.7)
    ax_coeff.bar(sites, coefficients, color=colors, width=0.68)
    for x, value in zip(sites, coefficients):
        ax_coeff.text(x, value + (0.035 if value >= 0 else -0.045), f"{value:.3f}",
                      ha="center", va="bottom" if value >= 0 else "top", fontsize=6.1)
    ax_coeff.set_xlim(0.35, 5.65)
    ax_coeff.set_ylim(-0.36, 0.77)
    ax_coeff.set_xticks(sites)
    ax_coeff.set_xlabel("site $i$ within a pentamer")
    ax_coeff.set_ylabel(r"projection coefficient $c_i$")
    ax_coeff.text(0.50, 0.94,
                  rf"$\alpha={ALPHA_REP:.2f}$" + "\n" + rf"$\sum_i c_i={coefficients.sum():.12f}$",
                  transform=ax_coeff.transAxes, ha="center", va="top")
    panel_label(ax_coeff, "b", -0.12)

    ax_jeff.fill_between(alpha, 0.0, jeff, color=LIGHT_TEAL, zorder=0)
    ax_jeff.plot(alpha, jeff, color=TEAL, lw=1.7)
    for target in (0.14, 0.23, 0.33):
        index = int(np.argmin(abs(alpha - target)))
        ax_jeff.plot(alpha[index], jeff[index], "o", color=RED, ms=3.8)
    ax_jeff.axhline(0.0, color="#444444", lw=0.8, ls="--")
    ax_jeff.set_xlim(0.0, 1.0)
    ax_jeff.set_ylim(-0.015, max(jeff) * 1.12)
    ax_jeff.set_xlabel(r"intracell coupling $\alpha$")
    ax_jeff.set_ylabel(r"$J_{\mathrm{eff}}/\beta=c_1c_5$")
    ax_jeff.text(0.98, 0.94, rf"positive for all {len(alpha)} ED points",
                 transform=ax_jeff.transAxes, ha="right", va="top", color=TEAL)
    panel_label(ax_jeff, "c", -0.12)

    outputs = save_figure(fig, MODEL_BASE)
    return outputs, {
        "coefficient_sum": float(coefficients.sum()),
        "reflection_error": float(max(abs(coefficients[0] - coefficients[4]),
                                      abs(coefficients[1] - coefficients[3]))),
        "minimum_jeff_over_beta": float(jeff.min()),
        "maximum_jeff_over_beta": float(jeff.max()),
    }


def branch_rows(folded: list[dict[str, str]], branch: str) -> list[dict[str, str]]:
    rows = [row for row in folded
            if abs(float(row["alpha"]) - ALPHA_REP) < 1e-12 and row["branch"] == branch]
    return sorted(rows, key=lambda row: float(row["q_over_pi"]))


def qpi_channel_fractions(multiplets: list[dict[str, str]]) -> dict[float, dict[float, float]]:
    totals: dict[float, dict[float, float]] = defaultdict(lambda: defaultdict(float))
    for row in multiplets:
        if float(row["excitation"]) <= 1e-10:
            continue
        alpha = round(float(row["alpha"]), 12)
        totals[alpha][float(row["spin_S"])] += float(row["qpi_weight"])
    fractions: dict[float, dict[float, float]] = {}
    for alpha, channels in totals.items():
        total = sum(channels.values())
        fractions[alpha] = {spin: weight / total for spin, weight in channels.items()}
    return fractions


def plot_filter_figure(
    multiplets: list[dict[str, str]],
    folded: list[dict[str, str]],
) -> tuple[list[Path], dict[str, float]]:
    levels = [row for row in multiplets if abs(float(row["alpha"]) - ALPHA_REP) < 1e-12]
    level_index = {row["branch"]: row for row in levels}
    dark = level_index["S0.5_r-_1"]
    bright = level_index["S1.5_r+_1"]
    dark_curve = branch_rows(folded, "S0.5_r-_1")
    bright_curve = branch_rows(folded, "S1.5_r+_1")
    fractions = qpi_channel_fractions(multiplets)

    fig = plt.figure(figsize=(7.2, 3.25), constrained_layout=True)
    grid = fig.add_gridspec(1, 3, width_ratios=(0.82, 1.15, 1.22))
    ax_levels = fig.add_subplot(grid[0, 0])
    ax_q = fig.add_subplot(grid[0, 1])
    ax_fraction = fig.add_subplot(grid[0, 2])

    ax_levels.set_xlim(0.0, 1.0)
    ax_levels.set_ylim(-0.025, 0.285)
    ax_levels.set_xticks([])
    ax_levels.set_ylabel(r"excitation energy / $J_1$")
    ground_y = 0.0
    dark_y = float(dark["excitation"])
    bright_y = float(bright["excitation"])
    level_specs = [
        (ground_y, BLUE, r"ground: $S=1/2$, $r=+$"),
        (dark_y, GRAY, r"$S=1/2$, $r=-$"),
        (bright_y, TEAL, r"$S=3/2$, $r=+$"),
    ]
    for y, color, label in level_specs:
        ax_levels.plot([0.08, 0.68], [y, y], color=color, lw=2.0)
        ax_levels.text(0.72, y, label, color=color, va="center", fontsize=6.3)
    ax_levels.annotate("dark", xy=(0.26, dark_y), xytext=(0.26, 0.045),
                       ha="center", color=GRAY,
                       arrowprops={"arrowstyle": "-|>", "color": GRAY, "lw": 1.0, "ls": "--"})
    ax_levels.plot(0.26, dark_y, marker="x", color=RED, ms=5.0, mew=1.3)
    ax_levels.annotate("bright", xy=(0.54, bright_y), xytext=(0.54, 0.045),
                       ha="center", color=TEAL,
                       arrowprops={"arrowstyle": "-|>", "color": TEAL, "lw": 1.2})
    ax_levels.text(0.04, 0.96, r"$S^z(q=\pi)$ is reflection even",
                   transform=ax_levels.transAxes, va="top", fontsize=6.2)
    panel_label(ax_levels, "a", -0.16)

    q_dark = np.array([float(row["q_over_pi"]) for row in dark_curve])
    w_dark = np.array([float(row["weight"]) for row in dark_curve])
    q_bright = np.array([float(row["q_over_pi"]) for row in bright_curve])
    w_bright = np.array([float(row["weight"]) for row in bright_curve])
    ax_q.plot(q_bright, w_bright, color=TEAL, marker="o", ms=4.2, lw=1.5,
              label=r"even quartet, $S=3/2$")
    ax_q.plot(q_dark, w_dark, color=GRAY, marker="s", ms=3.8, lw=1.3,
              label=r"odd doublet, $S=1/2$")
    ax_q.plot(1.0, 0.0, marker="x", color=RED, ms=5.0, mew=1.3)
    ax_q.set_xlim(0.15, 1.85)
    ax_q.set_ylim(-0.012, max(w_bright) * 1.16)
    ax_q.set_xticks([0.2, 0.6, 1.0, 1.4, 1.8])
    ax_q.set_xlabel(r"physical momentum $q/\pi$")
    ax_q.set_ylabel(r"single-cell transition weight")
    ax_q.legend(loc="upper left", fontsize=6.1, handlelength=1.8)
    ax_q.text(0.98, 0.05, rf"$\alpha={ALPHA_REP:.2f}$", transform=ax_q.transAxes,
              ha="right", va="bottom")
    panel_label(ax_q, "b", -0.14)

    alphas = np.array(sorted(fractions))
    quartet = np.array([fractions[a].get(1.5, 0.0) for a in alphas]) * 100.0
    doublet = np.array([fractions[a].get(0.5, 0.0) for a in alphas]) * 100.0
    sextet = np.array([fractions[a].get(2.5, 0.0) for a in alphas]) * 100.0
    ax_fraction.fill_between(alphas, 0.0, quartet, color=LIGHT_TEAL)
    ax_fraction.plot(alphas, quartet, color=TEAL, lw=1.7)
    ax_fraction.plot(alphas, doublet, color=BLUE, lw=1.3)
    ax_fraction.plot(alphas, sextet, color=RED, lw=1.0, ls="--")
    ax_fraction.set_xlim(0.0, 1.0)
    ax_fraction.set_ylim(-2.0, 103.0)
    ax_fraction.set_xlabel(r"intracell coupling $\alpha$")
    ax_fraction.set_ylabel(r"fraction of inelastic $q=\pi$ weight (%)")
    ax_fraction.text(0.98, 0.90, r"all $S=3/2$ quartets", transform=ax_fraction.transAxes,
                     ha="right", color=TEAL)
    ax_fraction.text(0.98, 0.12, r"excited $S=1/2$ doublets", transform=ax_fraction.transAxes,
                     ha="right", color=BLUE)
    ax_fraction.text(0.98, 0.035, r"$S=5/2$: rank-one dark", transform=ax_fraction.transAxes,
                     ha="right", color=RED, fontsize=6.2)
    panel_label(ax_fraction, "c", -0.14)

    outputs = save_figure(fig, FILTER_BASE)
    return outputs, {
        "lowest_doublet_qpi_weight": float(dark["qpi_weight"]),
        "lowest_quartet_qpi_weight": float(bright["qpi_weight"]),
        "quartet_fraction_min": float(quartet.min() / 100.0),
        "quartet_fraction_max": float(quartet.max() / 100.0),
        "sextet_fraction_max": float(sextet.max() / 100.0),
    }


def main() -> None:
    configure_matplotlib()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    MODEL_BASE.parent.mkdir(parents=True, exist_ok=True)
    projection_path = PROJECTION_DIR / "projection_scan.csv"
    multiplet_path = SPECTRAL_DIR / "multiplet_scan.csv"
    folded_path = SPECTRAL_DIR / "folded_transition_weights.csv"
    projection = read_rows(projection_path)
    multiplets = read_rows(multiplet_path)
    folded = read_rows(folded_path)

    model_outputs, model_metrics = plot_model_figure(projection)
    filter_outputs, filter_metrics = plot_filter_figure(multiplets, folded)
    checks = {
        "coefficient_sum": abs(model_metrics["coefficient_sum"] - 1.0) <= 1e-12,
        "reflection_symmetry": model_metrics["reflection_error"] <= 1e-12,
        "antiferromagnetic_jeff": model_metrics["minimum_jeff_over_beta"] > 0.0,
        "lowest_doublet_dark_at_qpi": filter_metrics["lowest_doublet_qpi_weight"] <= 1e-24,
        "quartets_dominate_qpi": filter_metrics["quartet_fraction_min"] >= 0.80,
        "sextet_rank_one_dark": filter_metrics["sextet_fraction_max"] <= 1e-24,
    }
    source_paths = [projection_path, multiplet_path, folded_path]
    figure_paths = model_outputs + filter_outputs
    summary = {
        "tag": "pass" if all(checks.values()) else "fail",
        "figure_contract": {
            "model_core_conclusion": (
                "An odd five-spin unit cell retains an effective S=1/2, and positive beta "
                "projects to an antiferromagnetic Heisenberg chain."
            ),
            "filter_core_conclusion": (
                "At q=pi reflection parity suppresses the lowest excited doublet while "
                "even S=3/2 quartets carry most local inelastic weight."
            ),
            "archetype": "schematic-led composite",
            "backend": "Python/matplotlib",
            "final_width_mm": 183,
        },
        "model_metrics": model_metrics,
        "filter_metrics": filter_metrics,
        "checks": checks,
        "source_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in source_paths},
        "figure_sha256": {path.name: sha256(path) for path in figure_paths},
        "scope_boundary": (
            "The projection and selection rules are isolated-cell or first-order statements; "
            "finite-beta branch assignment still requires production DSF."
        ),
    }
    summary_path = OUTDIR / "model_mechanism_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = sorted(path for path in OUTDIR.iterdir() if path.is_file() and path.name != "checksums.sha256")
    (OUTDIR / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
