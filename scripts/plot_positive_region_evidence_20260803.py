"""绘制正区机制与已验收动力学锚点的论文级证据图。"""

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
PHASE_CSV = ROOT / "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/phase-size-differences.csv"
PHASE_MERGED_JSON = ROOT / "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/observations_merged.json"
PROJECTION_CSV = ROOT / "results/autoresearch_v3_20260729/round1_doublet_projection/projection_scan.csv"
SW_CSV = ROOT / "results/autoresearch_v5_20260731/round14_schrieffer_wolff/schrieffer_wolff_scan.csv"
CV_DIR = ROOT / "results/autoresearch_v5_20260802/round21_cv_triplet_warmstart/cell-0002-L40-qpi-w025-w035"
OUT_BASE = ROOT / "figures/positive_region_evidence_20260803"
REPORT_PNG = ROOT / "results/research_progress/positive_region_evidence_20260803.png"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def style_axes(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_linewidth(0.8)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(width=0.7, length=3, pad=2)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.45, alpha=0.65)


def panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(-0.12, 1.04, label, transform=ax.transAxes, fontsize=9, fontweight="bold")


def main() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
            "font.size": 7.4,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "axes.linewidth": 0.8,
            "legend.frameon": False,
        }
    )

    phase = read_csv(PHASE_CSV)
    projection = read_csv(PROJECTION_CSV)
    sw = read_csv(SW_CSV)
    cv_points = []
    for point in sorted((CV_DIR / "points").glob("omega-*.csv")):
        cv_points.extend(read_csv(point))

    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.15), constrained_layout=False)
    ax_a, ax_b, ax_c, ax_d = axes.ravel()

    # a: 用两种尺寸差的均值显示 beta-alpha 矩阵，边界 alpha=0 单独保留。
    beta_values = sorted({float(row["beta"]) for row in phase})
    alpha_values = sorted({float(row["alpha"]) for row in phase})
    mean_matrix = np.zeros((len(beta_values), len(alpha_values)))
    for i, beta in enumerate(beta_values):
        for j, alpha_value in enumerate(alpha_values):
            vals = [
                float(row["delta_R"])
                for row in phase
                if float(row["beta"]) == beta and float(row["alpha"]) == alpha_value
            ]
            mean_matrix[i, j] = np.mean(vals)
    norm = matplotlib.colors.TwoSlopeNorm(vmin=-0.05, vcenter=0.0, vmax=0.005)
    im = ax_a.imshow(
        mean_matrix,
        cmap="RdBu_r",
        norm=norm,
        aspect="auto",
        interpolation="nearest",
        extent=(-0.0625, 1.0625, -0.5, len(beta_values) - 0.5),
    )
    for i, beta in enumerate(beta_values):
        for j, alpha_value in enumerate(alpha_values):
            value = mean_matrix[i, j]
            ax_a.text(alpha_value, i, f"{value:.3f}", ha="center", va="center", fontsize=5.8)
    ax_a.set_xlabel(r"$\alpha=J_2/J_1$")
    ax_a.set_ylabel(r"$\beta=J_3/J_1$")
    ax_a.set_xticks(alpha_values)
    ax_a.set_xticklabels([f"{v:g}" for v in alpha_values])
    ax_a.set_yticks(range(len(beta_values)))
    ax_a.set_yticklabels([f"{v:g}" for v in beta_values])
    cbar = fig.colorbar(im, ax=ax_a, fraction=0.046, pad=0.04)
    cbar.set_label(r"mean $\Delta R$", fontsize=6.8)
    cbar.ax.tick_params(labelsize=6)
    ax_a.set_title("mean of 40-60 and 60-80 size pairs", fontsize=7, pad=4)
    style_axes(ax_a)
    panel_label(ax_a, "a")

    # b: 一阶投影给出正的有效交换。
    alpha = np.array([float(row["alpha"]) for row in projection])
    jeff = np.array([float(row["jeff_over_beta"]) for row in projection])
    ax_b.plot(alpha, jeff, color="#0F4D92", linewidth=1.5)
    ax_b.fill_between(alpha, jeff, 0.0, color="#B4C0E4", alpha=0.32)
    ax_b.axhline(0.0, color="#272727", linewidth=0.8)
    ax_b.set_xlabel(r"$\alpha=J_2/J_1$")
    ax_b.set_ylabel(r"$J_{\mathrm{eff}}/\beta$")
    ax_b.set_xlim(0, 1)
    ax_b.set_ylim(0.24, 0.46)
    ax_b.text(0.04, 0.08, r"$0.4189$ to $0.4396>0$", transform=ax_b.transAxes, fontsize=7)
    style_axes(ax_b)
    panel_label(ax_b, "b")

    # c: 在受控边缘，二阶诱导 J2 保持弱且为正。
    alpha_sw = np.array([float(row["alpha"]) for row in sw])
    ratio = 100.0 * np.array([float(row["controlled_edge_J2_over_J1"]) for row in sw])
    ax_c.plot(alpha_sw, ratio, color="#B64342", linewidth=1.5)
    ax_c.fill_between(alpha_sw, ratio, 0.0, color="#E9A6A1", alpha=0.32)
    ax_c.axhline(0.0, color="#272727", linewidth=0.8)
    ax_c.set_xlabel(r"$\alpha=J_2/J_1$")
    ax_c.set_ylabel(r"controlled $J_2/J_1$ (%)")
    ax_c.set_xlim(0, 1)
    ax_c.set_ylim(0, 6.0)
    ax_c.text(0.04, 0.08, "second order: 3.95-5.19%", transform=ax_c.transAxes, fontsize=7)
    style_axes(ax_c)
    panel_label(ax_c, "c")

    # d: 仅展示已经通过验收的 L=40 CV 频点，不外推为完整谱。
    omega = np.array([float(row["omega"]) for row in cv_points])
    intensity = np.array([float(row["intensity"]) for row in cv_points])
    residual = np.array([float(row["relative_residual"]) for row in cv_points])
    order = np.argsort(omega)
    ax_d.plot(omega[order], intensity[order], color="#42949E", linewidth=1.4, marker="o", markersize=4.5)
    for x, y in zip(omega, intensity):
        ax_d.annotate(f"{y:.3f}", (x, y), xytext=(0, 6), textcoords="offset points", ha="center", fontsize=6)
    ax_d.set_xlabel(r"$\omega/J_1$ at $q=\pi$")
    ax_d.set_ylabel(r"$S(q,\omega)$")
    ax_d.set_xlim(0.23, 0.37)
    ax_d.set_ylim(0.32, 0.62)
    ax_d.text(0.04, 0.08, rf"L=40 CV; max residual={residual.max():.2e}", transform=ax_d.transAxes, fontsize=6.8)
    style_axes(ax_d)
    panel_label(ax_d, "d")

    fig.suptitle(
        "1x5 pentamer positive-region evidence: AFM chain, induced J2 and CV anchor",
        fontsize=9.5,
        fontweight="bold",
        x=0.02,
        ha="left",
    )
    fig.text(
        0.02,
        0.005,
        "a: 70 new positive-region size differences (105 merged records); b: cell projection; c: controlled-edge second order term; d: three CV points.",
        fontsize=6.4,
        color="#4D4D4D",
    )
    fig.subplots_adjust(left=0.09, right=0.985, top=0.89, bottom=0.12, wspace=0.30, hspace=0.38)

    OUT_BASE.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(f"{OUT_BASE}.svg", bbox_inches="tight")
    fig.savefig(f"{OUT_BASE}.pdf", bbox_inches="tight")
    fig.savefig(f"{OUT_BASE}.tiff", dpi=600, bbox_inches="tight")
    fig.savefig(f"{OUT_BASE}.png", dpi=600, bbox_inches="tight")
    REPORT_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(REPORT_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)

    manifest = {
        "figure": "positive_region_evidence_20260803",
        "backend": "Python/matplotlib",
        "claim": "正区没有可验收的 alpha>0 内部 crossing；五聚体低能交换为 AFM，二阶 J2 弱而系统；L=40 CV 三频点通过验收。",
        "source_files": [
            {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
            for path in [PHASE_CSV, PHASE_MERGED_JSON, PROJECTION_CSV, SW_CSV, CV_DIR / "manifest.json", *sorted((CV_DIR / "points").glob("omega-*.csv"))]
        ],
        "acceptance": {
            "phase_records_new_mesh": len(phase),
            "phase_records_merged": len(json.loads(PHASE_MERGED_JSON.read_text(encoding="utf-8"))["records"]),
            "positive_alpha_internal_crossing": False,
            "cv_points": len(cv_points),
            "cv_max_residual": float(residual.max()),
        },
        "exports": [str(path.relative_to(ROOT)) for path in [Path(f"{OUT_BASE}.svg"), Path(f"{OUT_BASE}.pdf"), Path(f"{OUT_BASE}.tiff"), Path(f"{OUT_BASE}.png")]],
    }
    (ROOT / "figures/positive_region_evidence_20260803.sources.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
