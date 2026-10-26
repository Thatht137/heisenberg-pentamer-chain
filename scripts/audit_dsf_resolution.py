"""原始网格重绘及有限时间窗审计，不平滑、不镜像平均。"""

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
from matplotlib.colors import Normalize, TwoSlopeNorm

ROOT = Path(__file__).resolve().parents[1]
LOW_MAX = 0.6


def transform(data, q, omega, cutoff, space_window):
    mask = (data[:, 0] <= cutoff + 1e-10) & (np.abs(data[:, 2]) <= space_window)
    subset = data[mask]
    times = np.unique(subset[:, 0])
    sites = np.unique(subset[:, 1])
    dt = times[1] - times[0]
    if not np.allclose(np.diff(times), dt):
        raise ValueError("时间采样不均匀")
    correlation = np.empty((len(times), len(sites)), dtype=complex)
    correlation[:] = np.nan
    ti = np.searchsorted(times, subset[:, 0])
    si = np.searchsorted(sites, subset[:, 1])
    if len(subset) != len(times) * len(sites) or len(set(zip(ti, si))) != len(subset):
        raise ValueError("关联函数网格不完整或重复")
    correlation[ti, si] = subset[:, 3] + 1j * subset[:, 4]
    distances = np.array([subset[subset[:, 1] == site, 2][0] for site in sites])
    if not np.allclose(subset[:, 2], distances[si]):
        raise ValueError("空间坐标随时间变化")
    cq = correlation @ np.exp(-1j * np.outer(distances, q))
    # 复现旧积分约定，保留符号及缺失的零时刻记录。
    window = np.sin(np.pi * times / times[-1]) ** 2
    raw = (np.exp(1j * np.outer(omega, times)) @ (cq * window[:, None]) * dt).real.T
    return raw, times


def save(fig, out, name):
    for extension in ("png", "pdf", "svg"):
        fig.savefig(out / f"{name}.{extension}", dpi=320, bbox_inches="tight")
    plt.close(fig)


def grid(items, out, signed=False):
    key = "raw" if signed else "stored"
    limit = max(float(np.abs(item[key]).max()) for item in items)
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0, vmax=limit) if signed else Normalize(0, limit)
    fig, axes = plt.subplots(2, len(items), figsize=(12.4, 5.1), sharex=True,
                             sharey="row", layout="constrained")
    image = None
    for col, item in enumerate(items):
        for row, ymax in enumerate((3, LOW_MAX)):
            ax = axes[row, col]
            image = ax.pcolormesh(item["q"] / np.pi, item["omega"], item[key].T,
                                 shading="nearest", cmap="RdBu_r" if signed else "inferno",
                                 norm=norm, rasterized=True)
            ax.set(xlim=(0, 2), ylim=(0, ymax), xticks=[0, 1, 2])
            ax.text(0.03, 0.94, f"({chr(97 + row * len(items) + col)})",
                    transform=ax.transAxes, va="top", color="black" if signed else "white")
            if row == 0:
                ax.set_title(rf"$J_2/J_1={item['alpha']:g}$")
            else:
                ax.set_xlabel(r"$q/\pi$")
        axes[0, col].set_yticks([0, 1, 2, 3])
        axes[1, col].set_yticks([0, 0.2, 0.4, 0.6])
    for ax in axes[:, 0]:
        ax.set_ylabel(r"$\omega/J_1$")
    colorbar = fig.colorbar(image, ax=axes, shrink=0.90, pad=0.015)
    colorbar.set_label("signed Fourier estimate" if signed else r"stored $S^{zz}(q,\omega)$")
    fig.suptitle(r"$J_3/J_1=0.5$, $L=40$, $t_{\max}J_1=15$, $\Delta t J_1=0.05$"
                 + (" | unclipped diagnostic" if signed else " | legacy pilot spectrum"), fontsize=11)
    save(fig, out, "signed_spectrum_diagnostic" if signed else "stored_full_and_low_energy")


def window_slices(items, out):
    selected = [item for item in items if item["alpha"] in (-0.5, 0.23)]
    fig, axes = plt.subplots(2, 3, figsize=(10.4, 5.8), sharex=True, layout="constrained")
    rows = []
    colors = ("#0072B2", "#D55E00", "#009E73")
    for row, item in enumerate(selected):
        for cutoff, color in zip((7.5, 10, 15), colors):
            raw, times = transform(item["data"], item["q"], item["omega"], cutoff, item["space_window"])
            for col, target in enumerate((0.2, 0.6, 1.0)):
                iq = int(np.argmin(np.abs(item["q"] / np.pi - target)))
                values = raw[iq]
                axes[row, col].plot(item["omega"], values, color=color, lw=1,
                                    label=rf"$t_{{\max}}J_1={times[-1]:g}$")
                low = item["omega"] <= LOW_MAX
                peak = np.argmax(values[low])
                rows.append({"alpha": item["alpha"], "q_over_pi": item["q"][iq] / np.pi,
                             "tmax": times[-1], "peak_omega_in_0_0p6": item["omega"][low][peak],
                             "peak_signed_value": values[low][peak], "negative_fraction": np.mean(values[low] < 0)})
        for col, target in enumerate((0.2, 0.6, 1.0)):
            ax = axes[row, col]
            ax.axhline(0, color="0.5", lw=0.6)
            ax.set(xlim=(0, 1.2), title=rf"$J_2/J_1={item['alpha']:g}$, $q={target:g}\pi$")
            if row == 1:
                ax.set_xlabel(r"$\omega/J_1$")
            if col == 0:
                ax.set_ylabel("signed Fourier estimate")
    axes[0, 0].legend(fontsize=8)
    save(fig, out, "time_window_slices")
    write_csv(out / "time_window_metrics.csv", rows)
    return rows


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, default=ROOT / "results/dsf_resolution_20261001")
    args = parser.parse_args()
    out = args.inputs
    plt.rcParams.update({"font.family": "Arial", "font.size": 9, "pdf.fonttype": 42,
                         "svg.fonttype": "none", "axes.linewidth": 0.7,
                         "xtick.direction": "in", "ytick.direction": "in"})
    with (out / "metadata.csv").open(encoding="utf-8", newline="") as file:
        metadata = list(csv.DictReader(file))
    items, metrics = [], []
    for meta in metadata:
        alpha = float(meta["alpha"])
        stem = f"a{alpha}"
        load = lambda suffix: np.loadtxt(out / f"{stem}_{suffix}.csv", delimiter=",")
        item = {"alpha": alpha, "data": load("correlation"), "stored": load("stored"),
                "q": load("q"), "omega": load("omega"), "space_window": int(meta["space_window"])}
        raw, times = transform(item["data"], item["q"], item["omega"], float(meta["tmax"]), item["space_window"])
        item["raw"] = raw
        discrepancy = float(np.max(np.abs(np.maximum(raw, 0) - item["stored"])))
        if discrepancy > 1e-8 * max(1, float(item["stored"].max())):
            raise ValueError(f"旧谱复现失败：alpha={alpha}, error={discrepancy}")
        low = item["omega"] <= LOW_MAX
        metrics.append({**meta, "omega_grid_step": np.diff(item["omega"])[0],
                        "time_window_scale_2pi_over_T": 2 * np.pi / times[-1],
                        "t0_included": bool(times[0] == 0), "raw_min": raw.min(), "raw_max": raw.max(),
                        "negative_grid_fraction": np.mean(raw < 0), "low_negative_grid_fraction": np.mean(raw[:, low] < 0),
                        "negative_abs_weight_fraction": np.abs(raw[raw < 0]).sum() / np.abs(raw).sum(),
                        "inversion_relative_rms": np.linalg.norm(raw - raw[::-1]) / np.linalg.norm(raw),
                        "legacy_clip_reproduction_max_error": discrepancy})
        np.savetxt(out / f"{stem}_signed.csv", raw, delimiter=",")
        items.append(item)
    write_csv(out / "audit_metrics.csv", metrics)
    grid(items, out)
    grid(items, out, signed=True)
    window_slices(items, out)
    qa = {"smoothing": False, "interpolation": False, "mirror_average": False,
          "data_clipping_by_this_script": False, "stored_input_preclipped": True,
          "color_limits": "shared absolute maximum across all panels, no saturation",
          "full_omega_range": [0, 3], "low_omega_range": [0, LOW_MAX],
          "legacy_transform": "Re sum dt exp(i(omega*t-q*r)) C(r,t) sin(pi*t/T)^2",
          "normalization": "legacy one-sided transform; no added factor of 2 or pi",
          "all_legacy_spectra_reproduced": True, "production_validated": False,
          "missing_requested_alpha": [0.5], "t0_missing": True,
          "generated_source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in sorted(out.glob("*.csv"))}}
    (out / "qa.json").write_text(json.dumps(qa, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2, default=float))
    print(f"Outputs: {out}")


if __name__ == "__main__":
    main()
