#!/usr/bin/env python3
"""把已验收 CV 离散点与有效链边界做受限叠加。"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "results" / "research_progress"
REPORT = REPORT_DIR / "report.json"
RESULT_DIR = REPORT_DIR / "cv_continuum_overlay_20260803"
FIGURE_BASE = ROOT / "figures" / "cv_continuum_overlay_20260803"
REPORT_PNG = REPORT_DIR / "cv_continuum_overlay_20260803.png"
TITLE = "L=40 CV 三频点与有效链连续谱边界（受限叠加）"
SPECTRUM = ROOT / "results/autoresearch_v5_20260802/round21_cv_triplet_warmstart/cell-0002-L40-qpi-w025-w035/spectrum.csv"
MANIFEST = ROOT / "results/autoresearch_v5_20260802/round21_cv_triplet_warmstart/cell-0002-L40-qpi-w025-w035/manifest.json"
PROJECTION = ROOT / "results/autoresearch_v3_20260729/round1_doublet_projection/representative.csv"
MULTIPLETS = ROOT / "results/autoresearch_v4_20260730/round2_local_spectral_channels_v4/representative_summary.csv"
ALPHA = 0.23
BETA = 0.5


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_coefficients() -> tuple[float, float]:
    projection = next(row for row in read_rows(PROJECTION) if math.isclose(float(row["alpha"]), ALPHA))
    multiplet = next(row for row in read_rows(MULTIPLETS) if math.isclose(float(row["alpha"]), ALPHA))
    return float(projection["jeff_over_beta"]), float(multiplet["lowest_quartet"])


def build_rows() -> tuple[list[dict[str, float]], float, float, float]:
    jeff_over_beta, quartet_gap = load_coefficients()
    jeff = BETA * jeff_over_beta
    upper = math.pi * jeff
    rows = []
    for row in read_rows(SPECTRUM):
        rows.append(
            {
                "omega": float(row["omega"]),
                "intensity": float(row["intensity"]),
                "relative_residual": float(row["relative_residual"]),
                "solve_seconds": float(row["solve_seconds"]),
            }
        )
    return rows, jeff_over_beta, quartet_gap, upper


def write_csv(rows: list[dict[str, float]], jeff_over_beta: float, quartet_gap: float, upper: float) -> Path:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULT_DIR / "cv_points_with_continuum_reference.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["alpha", "beta", "omega", "intensity", "relative_residual", "solve_seconds", "jeff_over_beta", "quartet_gap", "continuum_upper_qpi"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "alpha": ALPHA,
                "beta": BETA,
                **row,
                "jeff_over_beta": jeff_over_beta,
                "quartet_gap": quartet_gap,
                "continuum_upper_qpi": upper,
            })
    return path


def plot(rows: list[dict[str, float]], quartet_gap: float, upper: float) -> list[Path]:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "font.size": 7,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "axes.linewidth": 0.8,
        "legend.frameon": False,
    })
    omega = np.array([row["omega"] for row in rows])
    intensity = np.array([row["intensity"] for row in rows])
    residual = np.array([row["relative_residual"] for row in rows])
    xmax = max(0.78, upper * 1.12, float(omega.max()) * 1.12)
    fig = plt.figure(figsize=(7.2, 3.5), constrained_layout=True)
    grid = fig.add_gridspec(1, 2, width_ratios=(1.05, 1.35), wspace=0.32)

    ax_window = fig.add_subplot(grid[0, 0])
    ax_window.axvspan(0.0, upper, color="#DDEFE5", alpha=0.95, label="effective-chain window")
    ax_window.axvline(quartet_gap, color="#C4762B", lw=1.5, ls="--", label=r"local $S=3/2$ gap")
    ax_window.hlines(0.0, 0.0, xmax, color="#313131", lw=1.0)
    ax_window.scatter(omega, np.zeros_like(omega), s=36, color="#125A9C", zorder=3, label="accepted CV points")
    for index, item in enumerate(rows):
        offset_y = 9 if index % 2 == 0 else 20
        ax_window.annotate(f"{item['omega']:.2f}", (item["omega"], 0.0), xytext=(0, offset_y), textcoords="offset points", ha="center", fontsize=6.2, color="#125A9C")
    ax_window.set_xlim(0.0, xmax)
    ax_window.set_ylim(-0.18, 0.22)
    ax_window.set_yticks([])
    ax_window.set_xlabel(r"frequency $\omega/J_1$")
    ax_window.set_title(r"$q=\pi$ energy-window check", pad=5)
    ax_window.text(-0.13, 1.04, "a", transform=ax_window.transAxes, fontsize=9, fontweight="bold")
    ax_window.legend(loc="lower right", fontsize=6.0, handlelength=1.7)

    ax_signal = fig.add_subplot(grid[0, 1])
    ax_signal.plot(omega, intensity, marker="o", ms=4.8, lw=1.6, color="#125A9C", label=r"$S(q,\omega)$")
    ax_signal.set_xlim(0.22, 0.38)
    ax_signal.set_xlabel(r"frequency $\omega/J_1$")
    ax_signal.set_ylabel(r"CV intensity $S(\pi,\omega)$", color="#125A9C")
    ax_signal.tick_params(axis="y", labelcolor="#125A9C")
    ax_signal.set_ylim(0.0, 0.66)
    ax_signal.axvspan(max(0.22, 0.0), min(0.38, upper), color="#DDEFE5", alpha=0.45, zorder=0)
    ax_residual = ax_signal.twinx()
    ax_residual.plot(omega, residual, marker="s", ms=3.7, lw=1.2, color="#B34A4A", label="relative residual")
    ax_residual.axhline(1e-5, color="#B34A4A", lw=1.0, ls="--", alpha=0.8)
    ax_residual.set_yscale("log")
    ax_residual.set_ylim(3e-6, 2e-5)
    ax_residual.set_ylabel("relative residual", color="#B34A4A")
    ax_residual.tick_params(axis="y", labelcolor="#B34A4A")
    handles = [ax_signal.lines[0], ax_residual.lines[0]]
    ax_signal.legend(handles, ["CV intensity", "relative residual"], loc="upper right", fontsize=6.0)
    ax_signal.text(-0.13, 1.04, "b", transform=ax_signal.transAxes, fontsize=9, fontweight="bold")
    fig.suptitle("Accepted L=40 CV points against a leading-order reference window", fontsize=8.2)

    outputs: list[Path] = []
    for suffix in (".svg", ".pdf", ".png", ".tiff"):
        path = FIGURE_BASE.with_suffix(suffix)
        kwargs: dict[str, object] = {"bbox_inches": "tight"}
        if suffix in {".png", ".tiff"}:
            kwargs["dpi"] = 600
        if suffix == ".tiff":
            kwargs["pil_kwargs"] = {"compression": "tiff_lzw"}
        fig.savefig(path, **kwargs)
        outputs.append(path)
    plt.close(fig)
    shutil.copy2(FIGURE_BASE.with_suffix(".png"), REPORT_PNG)
    return outputs


def update_report(rows: list[dict[str, float]], jeff_over_beta: float, quartet_gap: float, upper: float, csv_path: Path) -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "已通过的 L=40 三个离散 CV 点；只作理论窗口一致性诊断",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "离散 CV 点落在参考低能窗内，但不构成连续谱结论",
                "why": f"alpha={ALPHA}, beta={BETA}, q=pi 的三个 CV 点均位于 0 <= omega <= pi J_eff={upper:.4f} 的 leading-order 参考窗内；local quartet gap={quartet_gap:.6f}。L=80 和 TEBD 仍未通过。",
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "cv_continuum_overlay_20260803.png",
                        "caption": "受限叠加诊断。a：在 alpha=0.23、beta=0.5、q=pi 下，绿色区域是 leading-order 有效链参考频率窗，橙色虚线是孤立五聚体最低四重态隙，蓝点是已通过的 L=40 CV 离散频点；b：对应强度和 relative residual。该图只显示三个离散点与理论尺度相容，不把点集解释为连续谱、峰支或 TEBD 交叉结果。",
                    }
                ],
            },
            {
                "kind": "table",
                "columns": ["omega/J1", "S(pi,omega)", "relative residual", "参考位置"],
                "rows": [[f"{row['omega']:.2f}", f"{row['intensity']:.7f}", f"{row['relative_residual']:.3e}", "有效链窗内"] for row in rows],
                "numeric": [True, True, True, False],
                "widths": ["18%", "28%", "28%", "26%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["模型点", "alpha=0.23, beta=0.5, L=40, q=pi, eta=0.1"],
                    ["理论参考", f"J_eff/beta={jeff_over_beta:.6f}；pi J_eff={upper:.6f}；local quartet gap={quartet_gap:.6f}"],
                    ["数据源", str(csv_path.relative_to(ROOT)).replace("\\", "/")],
                    ["边界", "不替代 L=80 CV、TEBD dt/dt2、时间窗或 CV/TEBD 峰位验收"],
                ],
            },
            {
                "kind": "note",
                "label": "解释边界",
                "style": "pending",
                "text": "有效链边界是热力学 leading-order 参考，不是有限五聚体链的严格上界；beta=0.5 对 alpha=0.23 已超出 g<=0.65 的受控投影区，因此这里只登记一致性，不命名谱线或相。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item["title"] != TITLE]
    index = next((i + 1 for i, item in enumerate(report["sections"]) if item["title"] == "L=40 CV 三频点：信号、残差与求解成本"), len(report["sections"]))
    report["sections"].insert(index, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    rows, jeff_over_beta, quartet_gap, upper = build_rows()
    csv_path = write_csv(rows, jeff_over_beta, quartet_gap, upper)
    outputs = plot(rows, quartet_gap, upper)
    sidecar = {
        "schema_version": 1,
        "figure": "cv_continuum_overlay_20260803",
        "backend": "Python/matplotlib",
        "archetype": "asymmetric mixed-modality figure",
        "claim": "三个已验收 L=40 CV 离散点与 alpha=0.23,beta=0.5 的 leading-order 有效链参考频率窗相容，但不构成连续谱或方法交叉结论。",
        "scope": {"alpha": ALPHA, "beta": BETA, "L": 40, "q": "pi", "eta": 0.1, "negative_alpha_excluded": True},
        "acceptance": {
            "points": len(rows),
            "max_relative_residual": max(row["relative_residual"] for row in rows),
            "all_nonnegative": all(row["intensity"] >= 0 for row in rows),
            "all_points_inside_reference_window": all(0.0 <= row["omega"] <= upper for row in rows),
            "jeff_over_beta": jeff_over_beta,
            "reference_window_upper_qpi": upper,
            "local_quartet_gap": quartet_gap,
        },
        "source_files": [],
        "exports": [str(path.relative_to(ROOT)).replace("\\", "/") for path in outputs],
        "interpretation_boundary": "参考边界为有效链热力学 leading-order 公式；图中三点不是完整频率网格，不作谱支命名，不替代 L=80 CV 或 TEBD。",
    }
    source_paths = [SPECTRUM, MANIFEST, PROJECTION, MULTIPLETS, csv_path]
    sidecar["source_files"] = [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)} for path in source_paths]
    sidecar_path = FIGURE_BASE.with_suffix(".sources.json")
    sidecar_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_report(rows, jeff_over_beta, quartet_gap, upper, csv_path)
    print(json.dumps({"figure": str(FIGURE_BASE), "sidecar": str(sidecar_path), "points": len(rows), "upper_qpi": upper}, ensure_ascii=False))


if __name__ == "__main__":
    main()
