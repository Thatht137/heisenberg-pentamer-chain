"""按参考 Fig. 3 的热图和切片结构绘制正区相图诊断。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/observations_merged.json"
OUT = ROOT / "figures"
COLORS = ["#2166AC", "#2A9D8F", "#D55E00", "#6B6B6B"]


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


def load() -> list[dict[str, float]]:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    return [
        {
            "alpha": float(row["params"]["alpha"]),
            "beta": float(row["params"]["beta"]),
            "L": float(row["params"]["L"]),
            "R": float(row["value"]),
        }
        for row in data["records"]
        if row.get("status") == "success" and float(row["params"]["alpha"]) >= 0
    ]


def label(ax: plt.Axes, text: str) -> None:
    ax.text(-0.08, 1.04, text, transform=ax.transAxes, fontweight="bold", fontsize=10)


def main() -> None:
    style()
    rows = load()
    alphas = np.array(sorted({row["alpha"] for row in rows}))
    betas = np.array(sorted({row["beta"] for row in rows}))
    def values(size: float) -> np.ndarray:
        return np.array([[next(row["R"] for row in rows if row["L"] == size and row["alpha"] == alpha and row["beta"] == beta) for alpha in alphas] for beta in betas])
    r40, r60, r80 = values(40), values(60), values(80)

    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.4), gridspec_kw={"hspace": 0.36, "wspace": 0.28})
    image = axes[0, 0].imshow(r80, origin="lower", aspect="auto", extent=[alphas.min() - 0.0625, alphas.max() + 0.0625, betas.min() - 0.05, betas.max() + 0.05], cmap="YlGnBu", vmin=0, vmax=max(r80.max(), 0.4))
    axes[0, 0].set_xlabel(r"$\alpha=J_2/J_1$")
    axes[0, 0].set_ylabel(r"$\beta=J_3/J_1$")
    axes[0, 0].set_title(r"$R(L=80)$ diagnostic", fontsize=8)
    axes[0, 0].set_xticks(alphas)
    axes[0, 0].set_yticks(betas)
    fig.colorbar(image, ax=axes[0, 0], fraction=0.046, pad=0.04, label="R")
    label(axes[0, 0], "a")

    for alpha, color in zip((0.0, 0.25, 0.5, 1.0), COLORS):
        index = np.where(alphas == alpha)[0][0]
        axes[0, 1].plot(betas, r80[:, index], marker="o", ms=2.8, lw=1.2, color=color, label=fr"$\alpha={alpha:g}$")
    axes[0, 1].set_xlabel(r"$\beta$")
    axes[0, 1].set_ylabel(r"$R(L=80)$")
    axes[0, 1].legend(fontsize=6.2, ncol=2)
    label(axes[0, 1], "b")

    for beta, color in zip((0.1, 0.5, 1.0), COLORS[:3]):
        index = np.where(betas == beta)[0][0]
        axes[1, 0].plot(alphas, r80[index], marker="o", ms=2.8, lw=1.2, color=color, label=fr"$\beta={beta:g}$")
    axes[1, 0].set_xlabel(r"$\alpha$")
    axes[1, 0].set_ylabel(r"$R(L=80)$")
    axes[1, 0].legend(fontsize=6.2)
    label(axes[1, 0], "c")

    for beta, color in zip((0.1, 0.5, 1.0), COLORS[:3]):
        index = np.where(betas == beta)[0][0]
        axes[1, 1].plot(alphas, r60[index] - r40[index], marker="o", ms=2.8, lw=1.2, color=color, label=fr"$\beta={beta:g}$")
    axes[1, 1].axhline(0, color="#767676", lw=0.8, ls="--")
    axes[1, 1].set_xlabel(r"$\alpha$")
    axes[1, 1].set_ylabel(r"$\Delta R=R_{60}-R_{40}$")
    axes[1, 1].legend(fontsize=6.2)
    axes[1, 1].text(0.03, 0.08, "crossing diagnostic; not a phase boundary", transform=axes[1, 1].transAxes, fontsize=6.2, color="#5F6368")
    label(axes[1, 1], "d")

    fig.suptitle("Reference-aligned Fig. 3: positive-region phase diagnostics", y=0.995, fontsize=10, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96], pad=0.8)
    OUT.mkdir(parents=True, exist_ok=True)
    base = OUT / "reference_aligned_fig3_pentamer_positive_20260803"
    for suffix, kwargs in ((".svg", {}), (".pdf", {}), (".png", {"dpi": 450}), (".tiff", {"dpi": 600})):
        fig.savefig(base.with_suffix(suffix), bbox_inches="tight", **kwargs)
    plt.close(fig)
    provenance = {
        "backend": "Python/matplotlib",
        "reference_mapping": "Fig. 3 heatmap + beta slices + alpha slices + size-difference diagnostic",
        "source_data": str(SOURCE.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "sizes": [40, 60, 80],
        "scope": {"alpha_min": 0.0, "alpha_max": 1.0, "negative_alpha_excluded": True, "figure_9_excluded": True},
        "boundary_statement": "R and Delta R are diagnostics; this figure does not claim a phase boundary.",
    }
    (OUT / "reference_aligned_fig3_pentamer_positive_20260803.sources.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(provenance, ensure_ascii=False))


if __name__ == "__main__":
    main()
