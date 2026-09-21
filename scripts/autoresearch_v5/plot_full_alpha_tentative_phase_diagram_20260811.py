#!/usr/bin/env python3
"""绘制完整 alpha 范围的物理假说相图。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "figures" / "full_alpha_tentative_phase_diagram_20260811"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.linewidth": 0.8,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    })
    fig, ax = plt.subplots(figsize=(183 / 25.4, 112 / 25.4))
    fig.subplots_adjust(left=0.10, right=0.985, bottom=0.20, top=0.87)

    # 背景颜色表示物理假说，不表示严格相界。
    ax.add_patch(Rectangle((-1, 0), 0.65, 1, facecolor="#f3d8ad", alpha=0.72, edgecolor="none"))
    ax.add_patch(Rectangle((-0.25, 0), 0.25, 1, facecolor="#dcebd8", alpha=0.80, edgecolor="none"))
    ax.add_patch(Rectangle((0, 0), 1, 1, facecolor="#d9e8f4", alpha=0.95, edgecolor="none"))
    ax.add_patch(Rectangle((-0.35, 0), 0.10, 1, facecolor="#f6e7d2", alpha=0.85,
                           hatch="////", edgecolor="#c97b21", linewidth=0.0))

    ax.axvline(0, color="#303030", lw=2.0, zorder=5)
    ax.axhline(0, color="#303030", lw=1.4, ls=":", zorder=5)
    ax.plot([-0.35, -0.25], [0.5, 0.5], color="#d97706", lw=5, solid_capstyle="butt", zorder=7)
    ax.scatter([-0.35, -0.25], [0.5, 0.5], s=38, facecolor="white", edgecolor="#d97706", zorder=8)

    ax.text(-0.68, 0.73, "Candidate IC critical regime", ha="center", va="center",
            color="#7c4713", weight="bold", fontsize=10)
    ax.text(-0.68, 0.62, r"effective $S\approx3/2$; $q\approx0.6\pi$", ha="center", color="#7c4713")
    ax.text(-0.68, 0.53, "string/edge active; gapless favored", ha="center", color="#7c4713")

    ax.text(-0.125, 0.76, "Candidate commensurate", ha="center", color="#315d38", weight="bold")
    ax.text(-0.125, 0.66, r"critical sector; $q=\pi$", ha="center", color="#315d38")
    ax.text(-0.125, 0.56, "low 2D confidence", ha="center", color="#315d38", style="italic")

    ax.text(0.50, 0.72, r"$q=\pi$ gapless AF", ha="center", color="#15558f", weight="bold", fontsize=11)
    ax.text(0.50, 0.61, r"effective $S=1/2$ pentamer doublets", ha="center", color="#15558f")
    ax.text(0.50, 0.51, "positive mesh: finite-size supported", ha="center", color="#15558f")

    ax.annotate(r"$\beta=0.5$ candidate momentum reconstruction",
                xy=(-0.30, 0.5), xytext=(-0.63, 0.28), color="#b45d08",
                arrowprops={"arrowstyle": "->", "color": "#b45d08", "lw": 1.2}, ha="center")
    ax.text(0.018, 0.15, r"$\alpha=0$: decoupled trimer + intercell dimer",
            rotation=90, ha="left", va="bottom", color="#303030", fontsize=8.5)
    ax.text(0.52, 0.035, r"$\beta=0$: isolated pentamer boundary", ha="center", color="#303030", fontsize=8.5)

    ax.set(xlim=(-1, 1), ylim=(0, 1), xlabel=r"$\alpha=J_2/J_1$", ylabel=r"$\beta=J_3/J_1$")
    ax.set_xticks([-1, -0.75, -0.5, -0.25, 0, 0.5, 1])
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1])
    ax.grid(color="#ffffff", lw=0.7, alpha=0.7)
    ax.set_title("Tentative physics phase map — regime labels are hypotheses", weight="bold", pad=9, fontsize=12)
    fig.text(0.5, 0.025,
             "Solid blue: positive mesh supported. Negative-alpha colors: strong-coupling hypothesis.\n"
             "Only the beta=0.5 orange bracket is calibrated; it may be a Lifshitz crossover rather than a phase boundary.",
             ha="center", va="bottom", fontsize=7.0, color="#404040")

    for suffix in ("svg", "pdf", "png", "tiff"):
        fig.savefig(OUT.with_suffix(f".{suffix}"), dpi=600 if suffix == "tiff" else 300)
    plt.close(fig)

    sources = {
        "schema_version": 1,
        "claim_level": "tentative_physics_hypothesis",
        "scope": {"alpha": [-1, 1], "beta": [0, 1], "fig9_excluded": True},
        "supported_region": "alpha>0 q=pi gapless AF from accepted positive mesh",
        "negative_interpretation": "strong-coupling S~3/2 and accepted beta=0.5 q_peak data",
        "candidate_bracket": {"beta": 0.5, "alpha": [-0.35, -0.25], "boundary_confirmed": False},
        "singular_controls": ["alpha=0", "beta=0"],
        "inputs": [
            "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/phase-diagram-v2/observations.json",
            "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/phase-diagram-v2/accepted_calibration_through_r16.json",
            "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/observations.json",
            "docs/beta_half_negative_critical_assessment.md",
            "docs/beta_half_results_draft.md",
        ],
    }
    OUT.with_suffix(".sources.json").write_text(json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    qa = {
        "status": "pass",
        "width_mm": 183,
        "python_only": True,
        "boundary_claimed": False,
        "svg_editable_text": "fonttype=none",
        "outputs": {suffix: {"sha256": sha256(OUT.with_suffix(f".{suffix}")), "bytes": OUT.with_suffix(f".{suffix}").stat().st_size}
                    for suffix in ("svg", "pdf", "png", "tiff")},
    }
    OUT.with_suffix(".qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "png": str(OUT.with_suffix('.png'))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
