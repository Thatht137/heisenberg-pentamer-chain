#!/usr/bin/env python3
"""绘制 L=10 严格 q=pi TEBD 的 ED 时域诊断图。"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results/autoresearch_v5_20260803/round25_qpi_tebd_smoke"
ANALYSIS = RUN / "time_domain_crosscheck"
EXACT = ROOT / "results/autoresearch_v5_20260730/round1_cv_oracle/cell-0001-exact"
COARSE = RUN / "L10-qpi-dt005-t30"
REFINED = RUN / "L10-qpi-dt0025-t30"
OUT = ROOT / "figures/qpi_tebd_ed_diagnostic_20260803"
REPORT_PREVIEW = ROOT / "results/research_progress/qpi_tebd_ed_diagnostic_20260803.png"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_time(path: Path) -> dict[str, np.ndarray]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {
        key: np.array([float(row[key]) for row in rows])
        for key in rows[0]
    }


def read_spectrum(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return (
        np.array([float(row["omega"]) for row in rows]),
        np.array([float(row["intensity"]) for row in rows]),
    )


def panel_label(axis, label: str) -> None:
    axis.text(
        -0.1,
        1.04,
        label,
        transform=axis.transAxes,
        fontsize=8,
        fontweight="bold",
        va="bottom",
    )


def main() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 7,
            "axes.labelsize": 7,
            "axes.titlesize": 7,
            "xtick.labelsize": 6.5,
            "ytick.labelsize": 6.5,
            "legend.fontsize": 6.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.7,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "lines.linewidth": 1.15,
        }
    )
    exact_color = "#222222"
    coarse_color = "#3F7CAC"
    refined_color = "#C4583E"
    coarse = read_time(ANALYSIS / "coarse_time_domain.csv")
    refined = read_time(ANALYSIS / "refined_time_domain.csv")
    exact_omega, exact_spectrum = read_spectrum(EXACT / "exact_spectrum.csv")
    coarse_omega, coarse_spectrum = read_spectrum(COARSE / "spectrum.csv")
    refined_omega, refined_spectrum = read_spectrum(REFINED / "spectrum.csv")

    width = 183 / 25.4
    height = 105 / 25.4
    fig = plt.figure(figsize=(width, height), constrained_layout=False)
    grid = fig.add_gridspec(
        2,
        2,
        height_ratios=[1.35, 1.0],
        width_ratios=[1.35, 1.0],
        left=0.085,
        right=0.985,
        bottom=0.13,
        top=0.95,
        hspace=0.42,
        wspace=0.32,
    )
    axis_a = fig.add_subplot(grid[0, 0])
    axis_b = fig.add_subplot(grid[0, 1])
    axis_c = fig.add_subplot(grid[1, 0])
    axis_d = fig.add_subplot(grid[1, 1])

    axis_a.plot(coarse["time"], coarse["exact_real"], color=exact_color, label="ED")
    axis_a.plot(
        coarse["time"],
        coarse["tebd_real"],
        color=coarse_color,
        linestyle="--",
        label=r"TEBD $\Delta t=0.05$",
    )
    axis_a.plot(
        refined["time"],
        refined["tebd_real"],
        color=refined_color,
        linestyle=":",
        label=r"TEBD $\Delta t=0.025$",
    )
    axis_a.set(xlabel=r"Time $tJ_1$", ylabel=r"$\mathrm{Re}\,C_{\pi}(t)$", xlim=(0, 30))
    axis_a.legend(loc="upper right", handlelength=2.5)
    panel_label(axis_a, "a")

    axis_b.plot(coarse["time"], coarse["exact_imag"], color=exact_color)
    axis_b.plot(coarse["time"], coarse["tebd_imag"], color=coarse_color, linestyle="--")
    axis_b.plot(refined["time"], refined["tebd_imag"], color=refined_color, linestyle=":")
    axis_b.set(xlim=(0, 30), xlabel=r"Time $tJ_1$", ylabel=r"$\mathrm{Im}\,C_{\pi}(t)$")
    panel_label(axis_b, "b")

    axis_c.semilogy(
        coarse["time"],
        np.maximum(coarse["absolute_error"], 1e-14),
        color=coarse_color,
        label=r"$\Delta t=0.05$",
    )
    axis_c.semilogy(
        refined["time"],
        np.maximum(refined["absolute_error"], 1e-14),
        color=refined_color,
        label=r"$\Delta t=0.025$",
    )
    axis_c.set(
        xlabel=r"Time $tJ_1$",
        ylabel=r"$|C_{\pi}^{\mathrm{TEBD}}-C_{\pi}^{\mathrm{ED}}|$",
        xlim=(0, 30),
    )
    axis_c.legend(loc="upper left")
    panel_label(axis_c, "c")

    axis_d.plot(exact_omega, exact_spectrum, color=exact_color, label="ED")
    axis_d.plot(coarse_omega, coarse_spectrum, color=coarse_color, linestyle="--", label=r"$\Delta t=0.05$")
    axis_d.plot(refined_omega, refined_spectrum, color=refined_color, linestyle=":", label=r"$\Delta t=0.025$")
    axis_d.set(
        xlabel=r"Frequency $\omega/J_1$",
        ylabel=r"$S^{zz}(\pi,\omega)$",
        xlim=(0, 1.0),
    )
    axis_d.legend(loc="upper right")
    panel_label(axis_d, "d")

    for suffix, options in (
        ("svg", {}),
        ("pdf", {}),
        ("tiff", {"dpi": 600}),
        ("png", {"dpi": 300}),
    ):
        fig.savefig(OUT.with_suffix(f".{suffix}"), bbox_inches="tight", **options)
    plt.close(fig)
    shutil.copy2(OUT.with_suffix(".png"), REPORT_PREVIEW)

    exports = [OUT.with_suffix(f".{suffix}") for suffix in ("svg", "pdf", "tiff", "png")]
    sources = {
        "schema_version": 1,
        "figure_contract": {
            "core_conclusion": "L=10 严格 q=pi TEBD 在时域跟随 ED，频域 Agreement 不是偶然峰位重合。",
            "archetype": "quantitative grid with dominant time-domain panel",
            "backend": "Python/matplotlib",
            "final_size_mm": [183, 105],
            "panel_map": {
                "a": "复相关函数实部主面板",
                "b": "复相关函数虚部",
                "c": "逐时刻复误差",
                "d": "eta=0.1 频谱叠加",
            },
            "reviewer_risk": "时域误差无预声明门槛，只作实现诊断。",
        },
        "source_sha256": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in (
                ANALYSIS / "coarse_time_domain.csv",
                ANALYSIS / "refined_time_domain.csv",
                ANALYSIS / "summary.json",
                EXACT / "exact_spectrum.csv",
                COARSE / "spectrum.csv",
                REFINED / "spectrum.csv",
                Path(__file__),
            )
        },
        "exports": [str(path.relative_to(ROOT)) for path in exports],
        "output_sha256": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in exports
        },
        "statistics": "确定性 ED/TEBD 数值比较；无采样误差或统计检验。",
        "image_integrity": "无裁剪数据、平滑、插值或局部图像调整；仅坐标范围限制频谱主峰视图。",
    }
    OUT.with_suffix(".sources.json").write_text(
        json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"figure": str(OUT), "backend": "Python"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
