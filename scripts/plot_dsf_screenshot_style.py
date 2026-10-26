"""按参考截图版式重绘保存谱，保持原始采样网格。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, Normalize

ROOT = Path(__file__).resolve().parents[1]


def draw(spectrum, q, omega, alpha, beta, ymax, vmax, destination, *, norm=None, colorbar=False,
         colorbar_ticks=None):
    cmap = LinearSegmentedColormap.from_list("reference_jet", [
        (0, "#1700b4"), (0.125, "#0000ff"), (0.375, "#00ffff"),
        (0.625, "#ffff00"), (0.875, "#ff0000"), (1, "#ff0000"),
    ], N=256)
    fig, ax = plt.subplots(figsize=(10.3, 8.86))
    bottom = 0.20
    top = 0.91 if ymax < 1 else 0.947
    fig.subplots_adjust(left=0.16 if ymax < 1 else 0.13, right=0.80 if colorbar else 0.935,
                        bottom=bottom, top=top)
    mesh = ax.pcolormesh(q, omega, spectrum.T, shading="nearest", cmap=cmap,
                         norm=Normalize(0, vmax) if norm is None else norm,
                         rasterized=True, antialiased=False)
    ax.set(xlim=(0, 2 * np.pi), ylim=(0, ymax))
    ax.set_xticks([0, np.pi, 2 * np.pi], [r"$\mathbf{0}$", r"$\boldsymbol{\pi}$", r"$\mathbf{2}\boldsymbol{\pi}$"])
    ax.set_yticks(np.arange(0, ymax + 1e-9, 1) if ymax >= 1 else [0, 0.2, 0.4, 0.6])
    if ymax < 1:
        ax.set_yticklabels(["0", "0.2", "0.4", "0.6"])
    ax.tick_params(direction="in", length=6, width=0.8, labelsize=40, pad=13)
    if ymax < 1:
        ax.tick_params(axis="y", labelsize=32)
    for tick in ax.get_yticklabels():
        tick.set_fontweight("bold")
    ax.set_xlabel("q", fontsize=46, fontweight="bold", labelpad=24)
    ax.set_ylabel(r"$\boldsymbol{\omega}$", fontsize=46, labelpad=18)
    ax.text(0.5, 1.035 if ymax < 1 else 0.92, rf"$J_2\!=\!{alpha:g},\ J_3\!=\!{beta:g}$",
            transform=ax.transAxes, color="black" if ymax < 1 else "white",
            fontsize=26 if ymax < 1 else 34, ha="center", va="bottom" if ymax < 1 else "top")
    for spine in ax.spines.values():
        spine.set_linewidth(0.65)
        spine.set_color("0.45")
    labels = [ax.xaxis.label, ax.yaxis.label, *ax.get_xticklabels(),
              *ax.get_yticklabels(), *ax.texts]
    if colorbar:
        cax = fig.add_axes([0.845, bottom, 0.024, top - bottom])
        bar = fig.colorbar(mesh, cax=cax)
        candidates = (0, 0.02, 0.1, 0.5, 1, 3, 6) if colorbar_ticks is None else colorbar_ticks
        ticks = [value for value in candidates
                 if mesh.norm.vmin <= value <= mesh.norm.vmax]
        bar.set_ticks(ticks)
        bar.set_ticklabels([f"{value:g}" for value in ticks])
        bar.ax.tick_params(labelsize=16)
        bar.set_label(r"$J_1S^{zz}(q,\omega)$", fontsize=20, labelpad=10)
        labels.extend([bar.ax.yaxis.label, *bar.ax.get_yticklabels()])
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for label in labels:
        bounds = label.get_window_extent(renderer)
        if bounds.x0 < -1 or bounds.y0 < -1 or bounds.x1 > fig.bbox.width + 1 or bounds.y1 > fig.bbox.height + 1:
            raise ValueError(f"文字越界：{label.get_text()}")
    for extension in ("png", "pdf", "svg"):
        fig.savefig(destination.parent / f"{destination.name}.{extension}", dpi=300, facecolor="white")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, default=ROOT / "results/dsf_resolution_20261001")
    parser.add_argument("--output", type=Path, default=ROOT / "figures/dsf_screenshot_style_20261001")
    parser.add_argument("--vmax", type=float, default=3.0)
    args = parser.parse_args()
    if args.vmax <= 0:
        parser.error("vmax 必须为正数")
    args.output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "Arial", "mathtext.fontset": "stixsans",
                         "pdf.fonttype": 42, "svg.fonttype": "none"})
    with (args.inputs / "metadata.csv").open(encoding="utf-8", newline="") as handle:
        metadata = list(csv.DictReader(handle))
    sources = []
    for meta in metadata:
        alpha, beta = float(meta["alpha"]), float(meta["beta"])
        stem = f"a{alpha}"
        source = args.inputs / f"{stem}_stored.csv"
        spectrum = np.loadtxt(source, delimiter=",")
        q = np.loadtxt(args.inputs / f"{stem}_q.csv", delimiter=",")
        omega = np.loadtxt(args.inputs / f"{stem}_omega.csv", delimiter=",")
        if spectrum.shape != (len(q), len(omega)) or not np.isfinite(spectrum).all():
            raise ValueError(f"谱网格无效：{source}")
        for label, ymax in (("full", float(omega[-1])), ("low", 0.6)):
            draw(spectrum, q, omega, alpha, beta, ymax, args.vmax,
                 args.output / f"Sqw_J2={alpha:g}_J3={beta:g}_{label}")
        sources.append({**meta, "input_csv_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                        "source_grid_shape": list(spectrum.shape), "omega_range": [float(omega[0]), float(omega[-1])],
                        "display_saturated_grid_fraction": float(np.mean(spectrum > args.vmax))})
    manifest = {"style": "reference screenshot: single panel, rainbow map, large ticks, internal parameter label",
                "vmin": 0, "vmax": args.vmax, "colorbar": False,
                "display_saturation": "values above vmax share the top color; source values are unchanged",
                "smoothing": False, "interpolation": False, "mirror_average": False,
                "source_type": "stored legacy spectrum, already clipped in the original calculation",
                "sources": sources, "missing_requested_parameter": {"J2": 0.5, "J3": 0.5}}
    (args.output / "plot_settings.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(metadata) * 2} figures (PNG/PDF/SVG): {args.output}")


if __name__ == "__main__":
    main()
