#!/usr/bin/env python3
"""绘制精简全动量任务的论文级多面板图。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.colors as colors
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
SW = ROOT / "results/autoresearch_v5_20260731/round14_schrieffer_wolff/schrieffer_wolff_scan.csv"
POINTS = ("uniform", "weak", "agreement")
TITLES = {
    "uniform": r"Uniform chain  $\alpha=1,\ \beta=1$",
    "weak": r"Weak coupling  $\alpha=1,\ \beta=0.1$",
    "agreement": r"Agreement point  $\alpha=0.23,\ \beta=0.5$",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_checksums(root: Path) -> None:
    checksum_file = root / "checksums.sha256"
    if not checksum_file.is_file():
        raise SystemExit("交接目录缺少 checksums.sha256")
    for line in checksum_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        target = (root / relative.strip()).resolve()
        target.relative_to(root)
        if not target.is_file() or sha256(target) != expected:
            raise SystemExit(f"交接哈希失败: {relative}")


def read_coefficients(alpha: float) -> dict[str, float]:
    with SW.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    row = min(rows, key=lambda item: abs(float(item["alpha"]) - alpha))
    if abs(float(row["alpha"]) - alpha) > 1e-9:
        raise SystemExit(f"缺少 alpha={alpha} 的有效理论系数")
    return {key: float(value) for key, value in row.items()}


def folded_continuum(q: np.ndarray, jeff: float) -> tuple[np.ndarray, np.ndarray]:
    k = np.mod(5.0 * q, 2.0 * np.pi)
    return 0.5 * np.pi * jeff * np.abs(np.sin(k)), np.pi * jeff * np.abs(np.sin(k / 2.0))


def uniform_continuum(q: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return 0.5 * np.pi * np.abs(np.sin(q)), np.pi * np.abs(np.sin(q / 2.0))


def negative_fraction(matrix: np.ndarray) -> float:
    negative = float(np.abs(matrix[matrix < 0.0]).sum())
    positive = float(matrix[matrix > 0.0].sum())
    return negative / max(negative + positive, 1e-30)


def configure() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 7,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "axes.unicode_minus": True,
    })


def panel_label(axis: plt.Axes, label: str, *, light: bool = False) -> None:
    axis.text(
        0.02, 0.97, label, transform=axis.transAxes, ha="left", va="top",
        fontsize=8, fontweight="bold", color="white" if light else "black",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff-dir", required=True)
    parser.add_argument("--output-base", required=True)
    args = parser.parse_args()
    handoff = Path(args.handoff_dir).resolve()
    output = Path(args.output_base).resolve()
    if any(output.with_suffix(suffix).exists() for suffix in (".svg", ".pdf", ".png", ".tiff", ".sources.json", ".qa.json", ".source.csv")):
        raise SystemExit(f"拒绝覆盖已有全动量图: {output}")
    verify_checksums(handoff)
    summary = json.loads((handoff / "handoff_summary.json").read_text(encoding="utf-8"))
    if summary.get("status") != "production_ready" or not all(summary.get("acceptance", {}).values()):
        raise SystemExit("全动量 handoff 未通过 production 门")
    campaign = Path(str(summary["campaign_dir"])).resolve()
    configure()
    figure, axes = plt.subplots(2, 3, figsize=(7.2, 5.0), sharex="row", constrained_layout=False)
    source_items: list[dict[str, object]] = []
    source_rows: list[dict[str, object]] = []
    images = []

    for column, point in enumerate(POINTS):
        pair = summary["pairs"][point]
        coarse_dir = campaign / pair["coarse"]
        refined_dir = campaign / pair["refined"]
        coarse_manifest = json.loads((coarse_dir / "manifest.json").read_text(encoding="utf-8"))
        refined_manifest = json.loads((refined_dir / "manifest.json").read_text(encoding="utf-8"))
        coarse_path = coarse_dir / "spectrum_raw.csv"
        refined_path = refined_dir / "spectrum_raw.csv"
        coarse = np.loadtxt(coarse_path, delimiter=",")
        refined = np.loadtxt(refined_path, delimiter=",")
        if coarse.shape != refined.shape or coarse.ndim != 2:
            raise SystemExit(f"{point} 的 dt/dt2 矩阵形状不一致")
        settings = refined_manifest["settings"]
        params = refined_manifest["params"]
        q = np.linspace(0.0, 2.0 * np.pi, refined.shape[0])
        omega = np.linspace(0.0, float(settings["omega_max"]), refined.shape[1])
        positive_max = max(float(refined.max()), 1e-30)
        normalized = refined / positive_max
        vmin = min(float(np.quantile(normalized, 0.005)), -0.02)
        norm = colors.TwoSlopeNorm(vmin=max(vmin, -0.15), vcenter=0.0, vmax=1.0)
        top = axes[0, column]
        image = top.pcolormesh(q / np.pi, omega, normalized.T, shading="auto", cmap="RdBu_r", norm=norm, rasterized=True)
        images.append(image)
        alpha = float(params["alpha"])
        beta = float(params["beta"])
        overlay = "none"
        control_ratio = None
        if point == "uniform":
            lower, upper = uniform_continuum(q)
            overlay = "uniform_exact"
            top.plot(q / np.pi, lower, color="#111111", lw=0.8, ls="--")
            top.plot(q / np.pi, upper, color="#111111", lw=0.8, ls=":")
        else:
            coeff = read_coefficients(alpha)
            control_ratio = beta / coeff["local_gap"]
            if control_ratio <= 0.65:
                lower, upper = folded_continuum(q, beta * coeff["projection_J1_over_beta"])
                overlay = "five_site_folded"
                top.plot(q / np.pi, lower, color="#111111", lw=0.8, ls="--")
                top.plot(q / np.pi, upper, color="#111111", lw=0.8, ls=":")
        neg = negative_fraction(refined)
        top.text(0.98, 0.96, f"neg. weight {100 * neg:.2f}%", transform=top.transAxes, ha="right", va="top", fontsize=6, color="white", bbox={"facecolor": "black", "alpha": 0.45, "edgecolor": "none", "pad": 1.2})
        top.set_title(TITLES[point], fontsize=7.5)
        top.set_ylim(0.0, float(settings["omega_max"]))
        panel_label(top, chr(ord("a") + column), light=True)

        qpi = int(np.argmin(np.abs(q - np.pi)))
        coarse_scale = max(float(coarse[qpi].max()), 1e-30)
        refined_scale = max(float(refined[qpi].max()), 1e-30)
        bottom = axes[1, column]
        bottom.plot(omega, coarse[qpi] / coarse_scale, color="#6b7280", lw=1.0, label=r"$\Delta t=0.025$")
        bottom.plot(omega, refined[qpi] / refined_scale, color="#b2182b", lw=1.15, label=r"$\Delta t=0.0125$")
        diagnostics = pair["diagnostics"]
        bottom.text(0.98, 0.96, f"peak drift {float(diagnostics['qpi_peak_delta']):.3f}\nweight drift {100 * float(diagnostics['low_weight_relative_delta']):.1f}%", transform=bottom.transAxes, ha="right", va="top", fontsize=6)
        bottom.axhline(0.0, color="#9ca3af", lw=0.5)
        bottom.set_xlim(0.0, float(settings["omega_max"]))
        bottom.set_ylim(min(-0.08, float((refined[qpi] / refined_scale).min()) * 1.1), 1.08)
        bottom.set_xlabel(r"$\omega/J_1$")
        panel_label(bottom, chr(ord("d") + column))
        if column == 0:
            top.set_ylabel(r"$\omega/J_1$")
            bottom.set_ylabel(r"$S^{zz}(\pi,\omega)/S_{\max}$")
            bottom.legend(loc="upper left", bbox_to_anchor=(0.0, 0.87), fontsize=6)
        source_rows.append({
            "point": point,
            "alpha": alpha,
            "beta": beta,
            "refined_positive_max": positive_max,
            "raw_negative_weight_fraction": neg,
            "overlay": overlay,
            "beta_over_local_gap": control_ratio,
            "qpi_peak_delta": diagnostics["qpi_peak_delta"],
            "low_weight_relative_delta": diagnostics["low_weight_relative_delta"],
        })
        for role, path in (("coarse_raw", coarse_path), ("refined_raw", refined_path), ("coarse_manifest", coarse_dir / "manifest.json"), ("refined_manifest", refined_dir / "manifest.json")):
            source_items.append({"point": point, "role": role, "path": str(path), "sha256": sha256(path)})

    for axis in axes[0]:
        axis.set_xlabel(r"$q/\pi$")
    colorbar = figure.colorbar(images[0], ax=list(axes[0]), fraction=0.024, pad=0.02)
    colorbar.set_label(r"raw $S^{zz}(q,\omega)/S_{\max}$")
    figure.subplots_adjust(left=0.08, right=0.91, bottom=0.10, top=0.93, wspace=0.25, hspace=0.30)
    output.parent.mkdir(parents=True, exist_ok=True)
    for suffix, kwargs in ((".svg", {}), (".pdf", {}), (".png", {"dpi": 450}), (".tiff", {"dpi": 600})):
        figure.savefig(output.with_suffix(suffix), bbox_inches="tight", **kwargs)
    plt.close(figure)

    source_csv = output.with_suffix(".source.csv")
    with source_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(source_rows[0]))
        writer.writeheader()
        writer.writerows(source_rows)
    outputs = {suffix: sha256(output.with_suffix(suffix)) for suffix in (".svg", ".pdf", ".png", ".tiff")}
    sidecar = {
        "schema_version": 1,
        "status": "production_fullq_dt_crosschecked",
        "figure_contract": {
            "core_conclusion": "三个代表点的全动量谱仅在单 run 与 dt/dt2 门均通过后进入论文证据。",
            "archetype": "quantitative_grid",
            "backend": "Python/matplotlib",
            "final_width_mm": 183,
            "raw_negative_values_visible": True,
        },
        "handoff_sha256": sha256(handoff / "handoff_summary.json"),
        "sources": source_items,
        "summary_csv": {"path": str(source_csv), "sha256": sha256(source_csv)},
        "outputs": outputs,
        "scope": summary["scope"],
    }
    output.with_suffix(".sources.json").write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from PIL import Image

    with Image.open(output.with_suffix(".png")) as preview:
        width_px, height_px = preview.size
    qa = {
        "status": "pass" if width_px >= 2500 and height_px >= 1500 and all(output.with_suffix(suffix).is_file() for suffix in (".svg", ".pdf", ".png", ".tiff")) else "fail",
        "pixel_size": [width_px, height_px],
        "editable_svg_text": "fonttype=none",
        "pdf_fonttype": 42,
        "raw_negative_values_visible": True,
        "shared_axes": True,
        "outputs": outputs,
    }
    output.with_suffix(".qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": qa["status"], "output": str(output), "pixel_size": qa["pixel_size"]}, ensure_ascii=False))
    if qa["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
