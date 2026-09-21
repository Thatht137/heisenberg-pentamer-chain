"""绘制只含正 alpha 的五聚体纠缠谱对应图。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data/entanglement_spectrum"
OUT = ROOT / "figures/reference_aligned_fig4_pentamer_positive_20260803"
ALPHAS = (0.14, 0.33)


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
            "font.size": 7.2,
            "axes.linewidth": 0.75,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "legend.frameon": False,
        }
    )


def load(alpha: float) -> dict[int, list[tuple[float, float]]]:
    path = DATA / f"spectrum_a{alpha:.2f}_b0.50_L080.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    grouped: dict[int, list[tuple[float, float]]] = {}
    for row in rows:
        grouped.setdefault(int(row["bond_class"]), []).append(
            (float(row["level"]), float(row["entanglement_energy"]))
        )
    return grouped


def save(fig: plt.Figure) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(OUT.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(OUT.with_suffix(".png"), dpi=450, bbox_inches="tight")
    fig.savefig(OUT.with_suffix(".tiff"), dpi=600, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    style()
    data = {alpha: load(alpha) for alpha in ALPHAS}
    fig = plt.figure(figsize=(7.2, 4.1))
    grid = fig.add_gridspec(2, 5, hspace=0.42, wspace=0.22, left=0.07, right=0.98, bottom=0.13, top=0.88)
    for row_index, alpha in enumerate(ALPHAS):
        for cut in range(5):
            axis = fig.add_subplot(grid[row_index, cut])
            values = np.asarray(data[alpha][cut], dtype=float)
            axis.scatter(values[:, 0], values[:, 1] - values[0, 1], s=15, color="#2B6CA3", edgecolor="white", linewidth=0.25)
            axis.set_title(fr"$\alpha={alpha:.2f}$, cut {cut}", fontsize=7)
            axis.set_xlabel("level", fontsize=6.5)
            if cut == 0:
                axis.set_ylabel(r"$\xi_i-\xi_1$", fontsize=7)
            axis.set_xlim(0.4, max(values[:, 0]) + 0.6)
            axis.grid(alpha=0.18, linewidth=0.45)
    fig.suptitle("Reference-aligned Fig. 4: positive-region entanglement spectrum", fontsize=10, fontweight="bold")
    fig.text(0.5, 0.02, "Five inequivalent cuts of the 1×5 chain; only 0≤alpha≤1 data are shown", ha="center", fontsize=7)
    save(fig)
    source_paths = [DATA / f"spectrum_a{alpha:.2f}_b0.50_L080.csv" for alpha in ALPHAS]
    source_hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
    provenance = {
        "backend": "Python/matplotlib",
        "reference_mapping": {"Fig. 4": "entanglement spectrum across five cuts"},
        "scope": {"alpha_min": 0.0, "alpha_max": 1.0, "negative_alpha_excluded": True, "figure_9_excluded": True},
        "alphas": list(ALPHAS),
        "source_sha256": source_hashes,
        "outputs": [str(OUT.with_suffix(s).relative_to(ROOT)) for s in (".svg", ".pdf", ".png", ".tiff")],
        "interpretation": "正区有限尺寸纠缠谱的版式对应图；不把有限切口简并单独解释为相界。",
    }
    OUT.with_suffix(".sources.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(provenance, ensure_ascii=False))


if __name__ == "__main__":
    main()
