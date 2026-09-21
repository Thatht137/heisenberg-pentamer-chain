"""提取 Fig.7 pilot 的 q=pi 峰值和积分窗口诊断。"""

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
ALPHAS = (0.14, 0.23, 0.33)
BETA = 0.5
LENGTH = 40
TMAX = 15
OMEGA_MAX = 1.5
INTERIOR_MIN = 0.1
FIGURE = ROOT / "figures/reference_aligned_fig7_pilot_quantitative_20260804"
OUTPUT_DIR = ROOT / "results/autoresearch_v5_20260804/round33_fig7_pilot_quantitative"


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main() -> None:
    inputs = [ROOT / f"data/Sqw_tebd_pentamer_alpha={alpha:.2f}_beta=0.5_L40_t15.csv" for alpha in ALPHAS]
    records: list[dict[str, float | int]] = []
    cuts: list[tuple[float, np.ndarray, np.ndarray]] = []
    for alpha, path in zip(ALPHAS, inputs):
        array = np.loadtxt(path, delimiter=",")
        omega_points = min(array.shape[1], int(round(array.shape[1] * 0.5)))
        omega = np.linspace(0.0, OMEGA_MAX, omega_points)
        q_over_pi = np.linspace(0.0, 2.0, array.shape[0])
        q_index = int(np.argmin(np.abs(q_over_pi - 1.0)))
        cut = array[q_index, :omega_points]
        peak_index = int(np.argmax(cut))
        interior_mask = omega >= INTERIOR_MIN
        interior_indices = np.where(interior_mask)[0]
        interior_index = int(interior_indices[np.argmax(cut[interior_mask])])
        records.append({
            "alpha": alpha,
            "q_over_pi": float(q_over_pi[q_index]),
            "peak_omega": float(omega[peak_index]),
            "peak_intensity": float(cut[peak_index]),
            "interior_peak_omega": float(omega[interior_index]),
            "interior_peak_intensity": float(cut[interior_index]),
            "interior_min_omega": INTERIOR_MIN,
            "window_weight": float(np.trapezoid(cut, omega)),
            "omega_points": int(omega_points),
        })
        cuts.append((alpha, omega, cut))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUTPUT_DIR / "qpi_peak_summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    summary = {
        "schema_version": 1,
        "status": "pilot_exploratory_not_production",
        "params": {"alphas": list(ALPHAS), "beta": BETA, "L": LENGTH, "tmax": TMAX, "omega_window": [0.0, OMEGA_MAX], "interior_min_omega": INTERIOR_MIN},
        "observable": "raw Szz(q=pi,omega)",
        "records": records,
        "scope": {"negative_alpha_excluded": True, "figure_9_excluded": True},
        "interpretation": "只描述 raw pilot 的离散峰和窗口权重，不作收敛、相界或 CV/TEBD Agreement 结论。",
    }
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

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
    colors = ["#2166AC", "#2A9D8F", "#D55E00"]
    figure, axes = plt.subplots(1, 4, figsize=(10.0, 2.75), gridspec_kw={"width_ratios": [2.1, 1.0, 1.0, 1.0]})
    for alpha, omega, cut, color in zip(ALPHAS, [item[1] for item in cuts], [item[2] for item in cuts], colors):
        record = next(item for item in records if item["alpha"] == alpha)
        axes[0].plot(omega, cut, color=color, lw=1.3, label=rf"$\alpha={alpha:.2f}$")
        axes[0].scatter([record["peak_omega"]], [record["peak_intensity"]], color=color, s=18, zorder=3)
        axes[0].scatter([record["interior_peak_omega"]], [record["interior_peak_intensity"]], facecolors="white", edgecolors=color, s=22, zorder=4)
    axes[0].set(xlabel=r"$\omega/J_1$", ylabel=r"raw $S^{zz}(\pi,\omega)$", title="q=π cuts")
    axes[0].legend(loc="upper right", fontsize=6)
    alpha_values = np.array(ALPHAS)
    peak_omega = np.array([item["peak_omega"] for item in records])
    interior_peak_omega = np.array([item["interior_peak_omega"] for item in records])
    peak_intensity = np.array([item["peak_intensity"] for item in records])
    window_weight = np.array([item["window_weight"] for item in records])
    axes[1].plot(alpha_values, peak_omega, "o--", color="#444444", lw=1.1, label="full window")
    axes[1].plot(alpha_values, interior_peak_omega, "s-", color="#2166AC", lw=1.1, label=rf"$\omega\geq{INTERIOR_MIN:g}$")
    axes[1].set(xlabel=r"$\alpha$", ylabel=r"peak $\omega/J_1$", title="endpoint sensitivity")
    axes[1].legend(fontsize=5.5)
    axes[2].plot(alpha_values, peak_intensity, "o-", color="#A63D40", lw=1.2)
    axes[2].set(xlabel=r"$\alpha$", ylabel="peak intensity", title="peak height")
    axes[3].plot(alpha_values, window_weight, "o-", color="#2E7D5B", lw=1.2)
    axes[3].set(xlabel=r"$\alpha$", ylabel=r"$\int_0^{1.5}S\,d\omega$", title="window weight")
    for axis, label in zip(axes, "abcd"):
        axis.text(-0.12, 1.08, label, transform=axis.transAxes, fontsize=10, fontweight="bold", va="top")
        axis.set_xticks(ALPHAS if axis is not axes[0] else [0.0, 0.5, 1.0, 1.5])
    figure.suptitle(r"Reference-aligned Fig. 7 quantitative pilot: $\beta=0.5$, raw TEBD", fontsize=9, fontweight="bold", y=1.04)
    figure.text(0.5, -0.04, "L=40, tmax=15; discrete raw pilot only, not production convergence or cross-method evidence", ha="center", fontsize=6.5, color="#555555")
    figure.subplots_adjust(left=0.07, right=0.99, bottom=0.22, top=0.82, wspace=0.48)
    for suffix, kwargs in ((".svg", {}), (".pdf", {}), (".png", {"dpi": 450}), (".tiff", {"dpi": 600})):
        figure.savefig(FIGURE.with_suffix(suffix), bbox_inches="tight", **kwargs)
    plt.close(figure)
    outputs = [FIGURE.with_suffix(suffix) for suffix in (".svg", ".pdf", ".png", ".tiff")]
    provenance = {
        "schema_version": 1,
        "figure": FIGURE.name,
        "backend": "Python/matplotlib",
        "reference_mapping": "Fig. 7: beta=0.5 positive alpha path with q=pi quantitative cuts",
        "source_files": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)} for path in inputs],
        "outputs": [str(path.relative_to(ROOT)).replace("\\", "/") for path in outputs],
        "scope": {"alphas": list(ALPHAS), "beta": BETA, "L": LENGTH, "tmax": TMAX, "negative_alpha_excluded": True, "figure_9_excluded": True},
        "status": "pilot_exploratory_not_production",
    }
    FIGURE.with_suffix(".sources.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"figure": FIGURE.name, "status": provenance["status"], "records": records}, ensure_ascii=False))


if __name__ == "__main__":
    main()
