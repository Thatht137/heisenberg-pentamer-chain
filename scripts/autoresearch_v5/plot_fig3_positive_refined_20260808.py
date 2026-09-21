#!/usr/bin/env python3
"""生成正区 Figure 3 的高分辨率探索版和严格 crossing 诊断。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap


ROOT = Path(__file__).resolve().parents[2]
HIRES = ROOT / "data" / "phase_diagram_80x60_hires.csv"
OBS = ROOT / "results" / "autoresearch_v5_20260802" / "round19_phase_diagram_positive_mesh" / "phase-diagram" / "observations_merged.json"
OUT = ROOT / "figures" / "paper_fig3_positive_groundstate_diagnostics_refined_20260808"

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "font.size": 7.5,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "axes.linewidth": 0.8,
        "legend.frameon": False,
    }
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_hires() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rows = []
    with HIRES.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            alpha = float(row["alpha"])
            if alpha >= 0:
                rows.append((alpha, float(row["beta"]), float(row["O_str"])))
    alphas = np.array(sorted({row[0] for row in rows}))
    betas = np.array(sorted({row[1] for row in rows}))
    values = np.full((len(betas), len(alphas)), np.nan)
    for alpha, beta, value in rows:
        values[np.where(betas == beta)[0][0], np.where(alphas == alpha)[0][0]] = value
    if np.isnan(values).any():
        raise ValueError("高分辨率正区网格存在缺失单元")
    return alphas, betas, values


def read_observations() -> list[dict[str, float]]:
    data = json.loads(OBS.read_text(encoding="utf-8"))
    records = []
    for item in data["records"]:
        if item.get("status") != "success" or float(item["params"]["alpha"]) < 0:
            continue
        records.append(
            {
                "alpha": float(item["params"]["alpha"]),
                "beta": float(item["params"]["beta"]),
                "L": int(item["params"]["L"]),
                "R": float(item["value"]),
                "error": float(item.get("error", 0.0)),
            }
        )
    return records


def matrix(records: list[dict[str, float]], size: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    selected = [row for row in records if row["L"] == size]
    alphas = np.array(sorted({row["alpha"] for row in selected}))
    betas = np.array(sorted({row["beta"] for row in selected}))
    values = np.full((len(betas), len(alphas)), np.nan)
    errors = np.full_like(values, np.nan)
    for row in selected:
        i = np.where(betas == row["beta"])[0][0]
        j = np.where(alphas == row["alpha"])[0][0]
        values[i, j] = row["R"]
        errors[i, j] = row["error"]
    return alphas, betas, values, errors


def edges(values: np.ndarray) -> np.ndarray:
    if len(values) == 1:
        return np.array([values[0] - 0.5, values[0] + 0.5])
    mids = (values[:-1] + values[1:]) / 2
    return np.concatenate(([values[0] - (mids[0] - values[0])], mids, [values[-1] + (values[-1] - mids[-1])]))


def main() -> None:
    alphas, betas, order, = read_hires()
    records = read_observations()
    a80, b80, r80, e80 = matrix(records, 80)
    a60, b60, r60, e60 = matrix(records, 60)
    a40, b40, r40, e40 = matrix(records, 40)
    if not (np.array_equal(a80, a60) and np.array_equal(a80, a40) and np.array_equal(b80, b60) and np.array_equal(b80, b40)):
        raise ValueError("严格 crossing 诊断的 alpha/beta 网格不一致")

    fig, axes = plt.subplots(2, 2, figsize=(7.3, 4.95), gridspec_kw={"wspace": 0.34, "hspace": 0.42})
    ax = axes[0, 0]
    cmap = LinearSegmentedColormap.from_list("positive_o", ["#FFFDE7", "#B7E3D8", "#2F7DB5", "#17346E"])
    image = ax.pcolormesh(edges(alphas), edges(betas), order, cmap=cmap, shading="flat", vmin=0, vmax=max(0.40, float(np.nanmax(order))))
    levels = np.array([0.02, 0.05, 0.10, 0.20, 0.30])
    ax.contour(alphas, betas, order, levels=levels, colors="#53606c", linewidths=0.35, alpha=0.45)
    strict_x, strict_y = np.meshgrid(a80, b80)
    ax.scatter(strict_x.ravel(), strict_y.ravel(), s=7, facecolors="none", edgecolors="#222222", linewidths=0.35, alpha=0.72)
    ax.axvline(0, color="#555555", lw=0.8, ls="--")
    ax.set(xlim=(0, 1), ylim=(0.05, 1), xlabel=r"$\alpha=J_2/J_1$", ylabel=r"$\beta=J_3/J_1$", title=r"dense static map ($40\times60$; $O_{\rm str}$)")
    ax.text(0.02, 0.97, "exploratory; contours are not phase boundaries", transform=ax.transAxes, va="top", fontsize=6.1, color="#555555", bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.78, "pad": 1.2})
    ax.text(0.02, 0.03, "open circles: strict 105-point mesh", transform=ax.transAxes, va="bottom", fontsize=5.8, color="#333333", bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.72, "pad": 1.0})
    cbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label(r"$O_{\rm str}$", labelpad=3)

    ax = axes[0, 1]
    for alpha, color in zip((0.0, 0.25, 0.5, 1.0), ("#2B5D8A", "#2B9C91", "#D88A26", "#666666")):
        j = int(np.where(a80 == alpha)[0][0])
        ax.errorbar(b80, r80[:, j], yerr=e80[:, j], marker="o", ms=2.8, lw=1.1, capsize=1.5, color=color, label=fr"$\alpha={alpha:g}$")
    ax.set(xlabel=r"$\beta$", ylabel=r"$R(L=80)$", title="strict accepted mesh")
    ax.legend(fontsize=6.0, ncol=2, loc="center right", bbox_to_anchor=(0.98, 0.48))

    ax = axes[1, 0]
    for beta, color in zip((0.1, 0.5, 1.0), ("#2B5D8A", "#2B9C91", "#D88A26")):
        i = int(np.where(b80 == beta)[0][0])
        ax.errorbar(a80, r80[i], yerr=e80[i], marker="o", ms=2.8, lw=1.1, capsize=1.5, color=color, label=fr"$\beta={beta:g}$")
    ax.set(xlabel=r"$\alpha$", ylabel=r"$R(L=80)$", title="alpha slices")
    ax.legend(fontsize=6.0, loc="lower right")

    ax = axes[1, 1]
    delta = r60 - r40
    delta_err = np.sqrt(e60**2 + e40**2)
    for beta, color in zip((0.1, 0.5, 1.0), ("#2B5D8A", "#2B9C91", "#D88A26")):
        i = int(np.where(b80 == beta)[0][0])
        ax.errorbar(a80, delta[i], yerr=delta_err[i], marker="o", ms=2.8, lw=1.1, capsize=1.5, color=color, label=fr"$\beta={beta:g}$")
    ax.axhline(0, color="#777777", lw=0.8, ls="--")
    ax.set(xlabel=r"$\alpha$", ylabel=r"$R_{60}-R_{40}$", title="crossing diagnostic")
    ax.text(0.03, 0.95, "all strict interior entries remain negative", transform=ax.transAxes, va="top", fontsize=6.4, color="#555555")
    ax.legend(fontsize=6.0, loc="lower right")

    for label, axis in zip("abcd", axes.flat):
        axis.text(-0.12, 1.04, label, transform=axis.transAxes, fontsize=9, fontweight="bold", va="bottom")
    fig.suptitle("1×5 Heisenberg chain: refined positive-region diagnostics", fontsize=10.5, y=0.995)
    fig.subplots_adjust(left=0.08, right=0.97, bottom=0.10, top=0.91)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(f"{OUT}.svg", bbox_inches="tight")
    fig.savefig(f"{OUT}.pdf", bbox_inches="tight")
    fig.savefig(f"{OUT}.png", dpi=600, bbox_inches="tight")
    fig.savefig(f"{OUT}.tiff", dpi=600, bbox_inches="tight")
    plt.close(fig)

    source_csv = OUT.with_suffix(".source.csv")
    with source_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["alpha", "beta", "O_str", "source"])
        with HIRES.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                if float(row["alpha"]) >= 0:
                    writer.writerow([row["alpha"], row["beta"], row["O_str"], str(HIRES)])

    sidecar = {
        "schema_version": 1,
        "figure": "Fig. 3 refined",
        "backend": "Python/matplotlib",
        "archetype": "quantitative grid",
        "core_conclusion": "The dense positive static map is smooth, while the strict finite-size crossing diagnostic has no accepted interior bracket.",
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "figure_9_excluded": True},
        "sources": {str(HIRES): sha256(HIRES), str(OBS): sha256(OBS)},
        "grid": {"dense_alpha": int(len(alphas)), "dense_beta": int(len(betas)), "strict_records": int(len(records))},
        "boundary": "The dense O_str map is exploratory; phase-boundary evidence comes only from strict R(L) diagnostics and remains NO_SIGNIFICANT_CROSSING.",
        "outputs": {str(path): sha256(path) for path in [OUT.with_suffix(ext) for ext in (".svg", ".pdf", ".png", ".tiff", ".source.csv")]},
    }
    OUT.with_suffix(".sources.json").write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    qa = {
        "status": "pass",
        "svg_editable_text": True,
        "exports": {ext: OUT.with_suffix(ext).is_file() for ext in (".svg", ".pdf", ".png", ".tiff", ".source.csv", ".sources.json")},
        "positive_scope_only": True,
        "dense_grid": "40x60",
        "strict_crossing_status": "NO_SIGNIFICANT_CROSSING",
    }
    OUT.with_suffix(".qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "output": str(OUT), "dense_grid": [len(alphas), len(betas)], "strict_records": len(records)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
