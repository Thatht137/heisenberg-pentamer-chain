"""绘制 L=40 CV 三频点的强度、残差和求解成本证据图。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "results/autoresearch_v5_20260802/round21_cv_triplet_warmstart/cell-0002-L40-qpi-w025-w035"
POINTS = RUN / "spectrum.csv"
OUT = ROOT / "figures/cv_triplet_cost_quality_20260803"
REPORT_PNG = ROOT / "results/research_progress/cv_triplet_cost_quality_20260803.png"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_rows(path: Path) -> list[dict[str, float]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            {key: float(value) for key, value in row.items() if value is not None}
            for row in csv.DictReader(handle)
        ]


def style_axes(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(width=0.7, length=3, pad=2)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.45, alpha=0.65)


def panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(-0.14, 1.04, label, transform=ax.transAxes, fontsize=9, fontweight="bold")


def main() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
            "font.size": 7.5,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "axes.linewidth": 0.8,
            "legend.frameon": False,
        }
    )
    rows = sorted(read_rows(POINTS), key=lambda row: row["omega"])
    if len(rows) != 3:
        raise SystemExit(f"三频点数据数量错误: {len(rows)}")
    omega = np.array([row["omega"] for row in rows])
    intensity = np.array([row["intensity"] for row in rows])
    residual = np.array([row["relative_residual"] for row in rows])
    solve_minutes = np.array([row["solve_seconds"] for row in rows]) / 60.0
    if not np.all(np.isfinite(np.concatenate((omega, intensity, residual, solve_minutes)))):
        raise SystemExit("三频点数据含非有限值")
    if np.min(intensity) < -1e-10 or np.max(residual) > 1e-5:
        raise SystemExit("三频点未满足非负性或 residual 门槛")

    colors = {"signal": "#0F4D92", "quality": "#42949E", "cost": "#B64342"}
    fig = plt.figure(figsize=(7.2, 3.15))
    grid = fig.add_gridspec(1, 3, width_ratios=(1.45, 1.0, 1.0), wspace=0.42)
    axes = [fig.add_subplot(grid[0, index]) for index in range(3)]

    ax = axes[0]
    ax.plot(omega, intensity, color=colors["signal"], marker="o", markersize=4.8, linewidth=1.5)
    for x, y in zip(omega, intensity):
        ax.annotate(f"{y:.3f}", (x, y), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=6.6)
    ax.set_xlabel(r"$\omega/J_1$ at $q=\pi$")
    ax.set_ylabel(r"$S(q,\omega)$")
    ax.set_xlim(0.23, 0.37)
    ax.set_ylim(0.32, 0.62)
    ax.text(0.04, 0.06, "non-negative; 3/3 accepted", transform=ax.transAxes, fontsize=6.6)
    style_axes(ax)
    panel_label(ax, "a")

    ax = axes[1]
    ax.axhspan(0.0, 1e-5, color="#DDF3DE", alpha=0.8, zorder=0)
    ax.axhline(1e-5, color="#B64342", linestyle="--", linewidth=0.9, label="gate")
    ax.plot(omega, residual, color=colors["quality"], marker="o", markersize=4.8, linewidth=1.5)
    ax.set_xlabel(r"$\omega/J_1$")
    ax.set_ylabel("relative CV residual")
    ax.set_xlim(0.23, 0.37)
    ax.set_ylim(0.0, 1.2e-5)
    ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    ax.text(0.04, 0.06, f"max={np.max(residual):.2e}", transform=ax.transAxes, fontsize=6.6)
    style_axes(ax)
    panel_label(ax, "b")

    ax = axes[2]
    ax.plot(omega, solve_minutes, color=colors["cost"], marker="o", markersize=4.8, linewidth=1.5)
    for x, y in zip(omega, solve_minutes):
        ax.annotate(f"{y:.0f} min", (x, y), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=6.4)
    ax.set_xlabel(r"$\omega/J_1$")
    ax.set_ylabel("CV solve time (min)")
    ax.set_xlim(0.23, 0.37)
    ax.set_ylim(45, 115)
    ax.text(0.04, 0.06, "warm-start sequence", transform=ax.transAxes, fontsize=6.6)
    style_axes(ax)
    panel_label(ax, "c")

    fig.suptitle(
        "L=40 correction-vector warm-start: accepted signal, residual and cost",
        fontsize=9.5,
        fontweight="bold",
        x=0.02,
        ha="left",
    )
    fig.text(
        0.02,
        0.005,
        "alpha=0.23, beta=0.5, OBC, Sz=0, eta=0.1; points are accepted independently.",
        fontsize=6.4,
        color="#4D4D4D",
    )
    fig.subplots_adjust(left=0.085, right=0.99, top=0.83, bottom=0.22)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(f"{OUT}.svg", bbox_inches="tight")
    fig.savefig(f"{OUT}.pdf", bbox_inches="tight")
    fig.savefig(f"{OUT}.tiff", dpi=600, bbox_inches="tight")
    fig.savefig(f"{OUT}.png", dpi=600, bbox_inches="tight")
    fig.savefig(REPORT_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)

    source = {
        "figure": "cv_triplet_cost_quality_20260803",
        "backend": "Python/matplotlib",
        "archetype": "quantitative grid with a hero signal panel",
        "claim": "L=40 warm-start CV 三频点均通过非负性和 residual 门槛，但更高频率的线性求解成本显著增加。",
        "scope": {"alpha": 0.23, "beta": 0.5, "L": 40, "q": "pi", "eta": 0.1, "negative_alpha_excluded": True},
        "acceptance": {
            "points": len(rows),
            "max_relative_residual": float(np.max(residual)),
            "min_intensity": float(np.min(intensity)),
            "all_nonnegative": bool(np.min(intensity) >= -1e-10),
            "all_residual_below_1e-5": bool(np.max(residual) <= 1e-5),
        },
        "source_files": [
            {"path": str(POINTS.relative_to(ROOT)), "sha256": sha256(POINTS)},
            {"path": str((RUN / "manifest.json").relative_to(ROOT)), "sha256": sha256(RUN / "manifest.json")},
        ],
        "exports": [str(path.relative_to(ROOT)) for path in [Path(f"{OUT}.svg"), Path(f"{OUT}.pdf"), Path(f"{OUT}.tiff"), Path(f"{OUT}.png")]],
    }
    (ROOT / "figures/cv_triplet_cost_quality_20260803.sources.json").write_text(
        json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(source, ensure_ascii=False))


if __name__ == "__main__":
    main()
