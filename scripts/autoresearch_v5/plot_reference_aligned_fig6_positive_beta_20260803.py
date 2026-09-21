"""绘制参考 Fig. 6 的正 alpha=1 beta 扫描诊断版。"""

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
OUT = ROOT / "figures/reference_aligned_fig6_alpha1_beta_scan_exploratory_20260803"
REPORT_PNG = ROOT / "results/research_progress/reference_aligned_fig6_alpha1_beta_scan_exploratory_20260803.png"
BETAS = (1.0, 0.7, 0.5, 0.4, 0.1)


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
    paths = [DATA / f"Sqw_tebd_pentamer_alpha=1.0_beta={beta:.1f}.csv" for beta in BETAS]
    if any(not path.is_file() for path in paths):
        raise SystemExit("缺少正区 beta 扫描数据")
    arrays = [np.loadtxt(path, delimiter=",") for path in paths]
    vmin = min(float(array.min()) for array in arrays)
    vmax = max(float(array.max()) for array in arrays)
    fig, axes = plt.subplots(1, len(BETAS), figsize=(10.5, 2.55), sharex=True, sharey=True)
    image = None
    for index, (beta, array) in enumerate(zip(BETAS, arrays)):
        axis = axes[index]
        q = np.linspace(0.0, 2.0 * np.pi, array.shape[0])
        omega = np.linspace(0.0, 3.0, array.shape[1])
        image = axis.pcolormesh(q, omega, array.T, shading="auto", cmap="magma", vmin=vmin, vmax=vmax, rasterized=True)
        axis.set_title(rf"$\beta={beta:g}$", fontsize=8)
        axis.set_xlim(0.0, 2.0 * np.pi)
        axis.set_ylim(0.0, 3.0)
        axis.set_xticks([0.0, np.pi, 2.0 * np.pi])
        axis.set_xticklabels([r"$0$", r"$\pi$", r"$2\pi$"])
        axis.text(0.04, 0.94, f"({chr(97 + index)})", transform=axis.transAxes, color="white", fontweight="bold", va="top")
        if index == 0:
            axis.set_ylabel(r"$\omega/J_1$")
        axis.set_xlabel(r"$q$")
    fig.subplots_adjust(left=0.06, right=0.94, bottom=0.23, top=0.80, wspace=0.18)
    fig.suptitle(r"Reference-aligned Fig. 6 diagnostic: $\alpha=1$ across positive $\beta$", y=0.97, fontsize=9, fontweight="bold")
    colorbar = fig.colorbar(image, ax=axes, fraction=0.018, pad=0.02)
    colorbar.set_label(r"raw $S^{zz}(q,\omega)$")
    fig.text(0.5, 0.04, "Exploratory TEBD grid; raw files retained, not production CV/TEBD evidence", ha="center", fontsize=6.5, color="#555555")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for suffix, kwargs in ((".svg", {}), (".pdf", {}), (".png", {"dpi": 450}), (".tiff", {"dpi": 600})):
        fig.savefig(OUT.with_suffix(suffix), bbox_inches="tight", **kwargs)
    plt.close(fig)
    shutil.copy2(OUT.with_suffix(".png"), REPORT_PNG)
    provenance = {
        "schema_version": 1,
        "figure": OUT.name,
        "backend": "Python/matplotlib",
        "reference_mapping": "Fig. 6: alpha=1 dynamic spectrum across beta",
        "scope": {"alpha": 1.0, "betas": list(BETAS), "negative_alpha_excluded": True, "figure_9_excluded": True},
        "status": "exploratory_not_production",
        "display": {"raw_data": True, "smoothing": False, "clip": False, "vmin": vmin, "vmax": vmax},
        "source_files": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)} for path in paths],
        "outputs": [str(OUT.with_suffix(suffix).relative_to(ROOT)).replace("\\", "/") for suffix in (".svg", ".pdf", ".png", ".tiff")],
        "interpretation": "只复刻参考图的 beta 多面板角色；数据为既有探索性 alpha=1 TEBD 网格，不用于最终动态门或谱支命名。",
    }
    OUT.with_suffix(".sources.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"figure": OUT.name, "status": provenance["status"], "betas": BETAS}, ensure_ascii=False))


if __name__ == "__main__":
    main()
