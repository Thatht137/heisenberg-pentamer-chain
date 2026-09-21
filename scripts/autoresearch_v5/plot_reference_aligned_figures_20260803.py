"""按参考 Fig. 1--2 的证据结构绘制五聚体正区对应图。"""

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


ROOT = Path(__file__).resolve().parents[2]
MULTIPLETS = ROOT / "results/autoresearch_v4_20260730/round2_local_spectral_channels_v4/multiplet_scan.csv"
OUT = ROOT / "figures"
ALPHA_REP = 0.23
COLORS = {0.5: "#2166AC", 1.5: "#D55E00", 2.5: "#5B5B5B"}
LABELS = {0.5: r"$S=1/2$", 1.5: r"$S=3/2$", 2.5: r"$S=5/2$"}


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 7.5,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
        }
    )


def load_rows() -> list[dict[str, float | str]]:
    with MULTIPLETS.open(encoding="utf-8", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle):
            alpha = float(row["alpha"])
            if alpha < 0.0:
                continue
            rows.append(
                {
                    "alpha": alpha,
                    "branch": row["branch"],
                    "spin": float(row["spin_S"]),
                    "parity": float(row["parity"]),
                    "energy": float(row["energy"]),
                    "excitation": float(row["excitation"]),
                    "qpi_weight": float(row["qpi_weight"]),
                }
            )
    return rows


def add_label(ax, label: str) -> None:
    ax.text(-0.08, 1.04, label, transform=ax.transAxes, fontweight="bold", fontsize=10)


def draw_chain(ax: plt.Axes) -> None:
    x = np.arange(10, dtype=float)
    for i in range(9):
        color = "#E09F3E" if i % 5 in (0, 3) else "#2B5D8F"
        if i == 4:
            color = "#2A9D8F"
        ax.plot([x[i], x[i + 1]], [0, 0], color=color, lw=3.2, solid_capstyle="round")
    ax.scatter(x, np.zeros_like(x), s=120, facecolor="white", edgecolor="#2B5D8F", linewidth=1.5, zorder=3)
    for value in x:
        ax.text(value, 0, "↑", ha="center", va="center", color="#2B5D8F", fontsize=8, zorder=4)
    for start, end in ((0, 4), (5, 9)):
        ax.add_patch(
            plt.Rectangle((start - 0.35, -0.28), end - start + 0.7, 0.56, facecolor="#EAF2F8", edgecolor="#A9C4DC", lw=0.9, zorder=0)
        )
        ax.text((start + end) / 2, -0.24, f"pentamer {start // 5 + 1}", ha="center", va="top", color="#5F6368")
    ax.text(2, 0.22, r"$J_2=\alpha$", ha="center", color="#D89022")
    ax.text(3, 0.22, r"$J_1=1$", ha="center", color="#245A8D")
    ax.text(7, 0.22, r"$J_2=\alpha$", ha="center", color="#D89022")
    ax.text(8, 0.22, r"$J_1=1$", ha="center", color="#245A8D")
    ax.text(4.5, 0.30, r"$J_3=\beta$", ha="center", color="#2A9D8F")
    ax.annotate("low-energy projection", xy=(4.5, -0.02), xytext=(4.5, -0.52), ha="center", color="#5F6368", arrowprops={"arrowstyle": "-|>", "color": "#777777"})
    ax.plot([3.7, 5.3], [-0.80, -0.80], color="#2A9D8F", lw=2.8)
    ax.scatter([3.7, 5.3], [-0.80, -0.80], s=90, facecolor="white", edgecolor="#2A9D8F", linewidth=1.4, zorder=3)
    ax.text(4.5, -0.64, r"$J_{\rm eff}=\beta c_1c_5>0$", ha="center", color="#2A9D8F")
    ax.set_xlim(-0.7, 9.7)
    ax.set_ylim(-1.0, 0.55)
    ax.axis("off")


def draw_local_levels(ax: plt.Axes, rows: list[dict[str, float | str]], alpha: float) -> None:
    selected = [row for row in rows if abs(float(row["alpha"]) - alpha) < 1e-9]
    if not selected:
        alpha = min({float(row["alpha"]) for row in rows}, key=lambda value: abs(value - alpha))
        selected = [row for row in rows if abs(float(row["alpha"]) - alpha) < 1e-9]
    selected = sorted(selected, key=lambda row: float(row["excitation"]))
    for index, row in enumerate(selected):
        spin = float(row["spin"])
        y = float(row["excitation"])
        ax.plot([0.08, 0.72], [y, y], color=COLORS[spin], lw=1.6)
        ax.text(0.76, y, str(row["branch"]), va="center", fontsize=6.2, color=COLORS[spin])
        weight = float(row["qpi_weight"])
        if weight > 1e-5:
            ax.scatter(0.40, y, s=22 + 80 * min(weight, 0.35), facecolor="white", edgecolor="#2A9D8F", linewidth=0.8, zorder=3)
    ax.set_xlim(0.0, 1.25)
    ax.set_ylim(-0.05, max(float(row["excitation"]) for row in selected) * 1.06)
    ax.set_xticks([])
    ax.set_ylabel(r"local excitation $(E-E_0)/J_1$")
    ax.set_title(fr"single pentamer, $\alpha={alpha:.2f}$", loc="left", fontsize=8)
    ax.text(0.04, 0.90, r"circle size $\propto$ q=$\pi$ weight", transform=ax.transAxes, va="top", fontsize=6.3, color="#4D4D4D")


def draw_fig1(rows: list[dict[str, float | str]]) -> str:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.05), gridspec_kw={"width_ratios": [1.55, 1.0]})
    draw_chain(axes[0])
    draw_local_levels(axes[1], rows, ALPHA_REP)
    add_label(axes[0], "a")
    add_label(axes[1], "b")
    fig.suptitle("Reference-aligned Fig. 1: 1×5 pentamer chain and local multiplets", y=0.99, fontsize=10, fontweight="bold")
    handles = [plt.Line2D([], [], color=COLORS[spin], lw=2, label=LABELS[spin]) for spin in (0.5, 1.5, 2.5)]
    fig.legend(handles=handles, ncol=3, loc="upper center", bbox_to_anchor=(0.73, 0.95), fontsize=6.2)
    fig.subplots_adjust(left=0.05, right=0.98, bottom=0.10, top=0.84, wspace=0.22)
    return save_figure(fig, "reference_aligned_fig1_pentamer_20260803")


def draw_fig2(rows: list[dict[str, float | str]]) -> str:
    by_alpha: dict[float, list[dict[str, float | str]]] = defaultdict(list)
    for row in rows:
        by_alpha[float(row["alpha"])].append(row)
    alphas = np.array(sorted(by_alpha))
    ground = np.array([min(float(row["energy"]) for row in by_alpha[value]) for value in alphas])
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.1), gridspec_kw={"width_ratios": [1.1, 1.0]})
    branches = sorted({str(row["branch"]) for row in rows})
    for branch in branches:
        curve = []
        spin = None
        for alpha in alphas:
            record = next(row for row in by_alpha[float(alpha)] if row["branch"] == branch)
            curve.append(float(record["energy"]) - float(ground[np.where(alphas == alpha)[0][0]]))
            spin = float(record["spin"])
        axes[0].plot(alphas, curve, color=COLORS[spin], lw=0.85, alpha=0.9)
    axes[0].set_xlabel(r"intra-cell coupling $\alpha=J_2/J_1$")
    axes[0].set_ylabel(r"multiplet gap $(E-E_0)/J_1$")
    axes[0].set_xlim(0, 1)
    axes[0].text(0.03, 0.96, "five doublets + four quartets + one sextet", transform=axes[0].transAxes, va="top", fontsize=6.5)

    weights: dict[float, dict[float, float]] = defaultdict(lambda: defaultdict(float))
    for alpha in alphas:
        for row in by_alpha[float(alpha)]:
            weights[float(row["spin"])][float(alpha)] += float(row["qpi_weight"])
    for spin, label in LABELS.items():
        y = np.array([weights[spin][float(alpha)] for alpha in alphas])
        axes[1].plot(alphas, 100 * y, color=COLORS[spin], lw=1.7, label=label)
    axes[1].axvline(ALPHA_REP, color="#767676", ls="--", lw=0.8)
    axes[1].text(0.30, 0.93, r"$\alpha=0.23$", transform=axes[1].transAxes, fontsize=6.5, color="#4D4D4D")
    axes[1].set_xlabel(r"intra-cell coupling $\alpha=J_2/J_1$")
    axes[1].set_ylabel(r"q=π spectral weight (%)")
    axes[1].set_xlim(0, 1)
    axes[1].set_ylim(bottom=0)
    add_label(axes[0], "a")
    add_label(axes[1], "b")
    fig.suptitle("Reference-aligned Fig. 2: positive-region level flow and momentum filtering", y=0.99, fontsize=10, fontweight="bold")
    handles = [plt.Line2D([], [], color=COLORS[spin], lw=2, label=LABELS[spin]) for spin in (0.5, 1.5, 2.5)]
    fig.legend(handles=handles, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 0.95), fontsize=6.2)
    fig.subplots_adjust(left=0.08, right=0.98, bottom=0.15, top=0.83, wspace=0.28)
    return save_figure(fig, "reference_aligned_fig2_pentamer_positive_20260803")


def save_figure(fig: plt.Figure, stem: str) -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    base = OUT / stem
    fig.savefig(base.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(base.with_suffix(".png"), dpi=450, bbox_inches="tight")
    fig.savefig(base.with_suffix(".tiff"), dpi=600, bbox_inches="tight")
    plt.close(fig)
    return str(base)


def main() -> None:
    style()
    rows = load_rows()
    first = draw_fig1(rows)
    second = draw_fig2(rows)
    source_hash = hashlib.sha256(MULTIPLETS.read_bytes()).hexdigest()
    provenance = {
        "backend": "Python/matplotlib",
        "archetype": "quantitative grid",
        "reference_mapping": {"Fig. 1": "chain + local multiplets", "Fig. 2": "level flow + q=pi channel weights"},
        "scope": {"alpha_min": 0.0, "alpha_max": 1.0, "negative_alpha_excluded": True, "figure_9_excluded": True},
        "alpha_representative": ALPHA_REP,
        "source_data": str(MULTIPLETS.relative_to(ROOT)),
        "source_sha256": source_hash,
        "outputs": [first + suffix for suffix in (".svg", ".pdf", ".png", ".tiff")] + [second + suffix for suffix in (".svg", ".pdf", ".png", ".tiff")],
        "interpretation": "仅复刻参考文献的证据组织和面板角色，不移植四聚体相名或激发命名。",
    }
    (OUT / "reference_aligned_figures_20260803.sources.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(provenance, ensure_ascii=False))


if __name__ == "__main__":
    main()
