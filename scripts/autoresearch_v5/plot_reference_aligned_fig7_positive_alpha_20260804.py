"""绘制参考 Fig. 7 的正 alpha=0.14/0.23/0.33 诊断版。"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = ROOT / "figures/reference_aligned_fig7_positive_alpha_pilot_20260804"
REPORT_PNG = ROOT / "results/research_progress/reference_aligned_fig7_positive_alpha_pilot_20260804.png"
ALPHAS = (0.14, 0.23, 0.33)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
        "font.size": 7,
        "axes.linewidth": 0.75,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "legend.frameon": False,
    })
    paths = [DATA / f"Sqw_tebd_pentamer_alpha={alpha:.2f}_beta=0.5_L40_t15.csv" for alpha in ALPHAS]
    arrays = [np.loadtxt(path, delimiter=",") for path in paths]
    vmin = min(float(array.min()) for array in arrays)
    vmax = max(float(array.max()) for array in arrays)
    figure, axes = plt.subplots(2, 3, figsize=(7.5, 4.4), sharex="row", sharey="row")
    colors = ["#2166AC", "#2A9D8F", "#D55E00"]
    image = None
    for index, (alpha, array, path, color) in enumerate(zip(ALPHAS, arrays, paths, colors)):
        q_over_pi = np.linspace(0.0, 2.0, array.shape[0])
        n_display = min(array.shape[1], int(round(array.shape[1] * 0.5)))
        omega = np.linspace(0.0, 1.5, n_display)
        display = array[:, :n_display]
        image = axes[0, index].pcolormesh(q_over_pi, omega, display.T, shading="auto", cmap="magma", vmin=vmin, vmax=vmax, rasterized=True)
        axes[0, index].set_title(rf"$\alpha={alpha:.2f}$", fontsize=8)
        axes[0, index].text(0.04, 0.93, f"({chr(97 + index)})", transform=axes[0, index].transAxes, color="white", fontweight="bold", va="top")
        axes[0, index].set_xticks([0.0, 1.0, 2.0])
        axes[0, index].set_yticks([0.0, 0.5, 1.0, 1.5])
        axes[0, index].set_xlabel(r"$q/\pi$")
        axes[0, index].set_ylim(0.0, 1.5)
        q_index = int(np.argmin(np.abs(q_over_pi - 1.0)))
        axes[1, index].plot(omega, display[q_index], color=color, lw=1.35)
        axes[1, index].set_title(rf"$q=\pi$ cut, $\alpha={alpha:.2f}$", fontsize=7.5)
        axes[1, index].text(0.04, 0.90, f"({chr(100 + index)})", transform=axes[1, index].transAxes, fontweight="bold", va="top")
        axes[1, index].set_xlim(0.0, 1.5)
        axes[1, index].set_xlabel(r"$\omega/J_1$")
    axes[0, 0].set_ylabel(r"$\omega/J_1$")
    axes[1, 0].set_ylabel(r"raw $S^{zz}(\pi,\omega)$")
    figure.subplots_adjust(left=0.08, right=0.91, bottom=0.18, top=0.82, wspace=0.22, hspace=0.42)
    figure.suptitle(r"Reference-aligned Fig. 7 diagnostic: positive $\alpha$ path at $\beta=0.5$", y=0.96, fontsize=9, fontweight="bold")
    colorbar = figure.colorbar(image, ax=axes[0, :], fraction=0.035, pad=0.03)
    colorbar.set_label(r"raw $S^{zz}(q,\omega)$")
    figure.text(0.5, 0.04, "L=40, tmax=15 pilot; raw files retained, not production cross-method evidence", ha="center", fontsize=6.5, color="#555555")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for suffix, kwargs in ((".svg", {}), (".pdf", {}), (".png", {"dpi": 450}), (".tiff", {"dpi": 600})):
        figure.savefig(OUT.with_suffix(suffix), bbox_inches="tight", **kwargs)
    plt.close(figure)
    shutil.copy2(OUT.with_suffix(".png"), REPORT_PNG)
    provenance = {
        "schema_version": 1,
        "figure": OUT.name,
        "backend": "Python/matplotlib",
        "reference_mapping": "Fig. 7: beta=0.5 positive alpha path with q=pi cuts",
        "scope": {"alphas": list(ALPHAS), "beta": 0.5, "L": 40, "tmax": 15, "negative_alpha_excluded": True, "figure_9_excluded": True},
        "status": "pilot_exploratory_not_production",
        "display": {"raw_data": True, "smoothing": False, "clip": False, "omega_max_display": 1.5, "vmin": vmin, "vmax": vmax},
        "source_files": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)} for path in paths],
        "outputs": [str(OUT.with_suffix(suffix).relative_to(ROOT)).replace("\\", "/") for suffix in (".svg", ".pdf", ".png", ".tiff")],
        "interpretation": "只复刻参考图 Fig. 7 的正区路径和切片角色；pilot 不用于关闭 TEBD/CV 动态门。",
    }
    OUT.with_suffix(".sources.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"figure": OUT.name, "status": provenance["status"], "alphas": ALPHAS}, ensure_ascii=False))


if __name__ == "__main__":
    main()
