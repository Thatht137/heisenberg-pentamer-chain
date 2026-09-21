#!/usr/bin/env python3
"""绘制七点 accepted-only 的 bounded Fig.8。"""

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
CV = ROOT / "results/autoresearch_v5_20260805/round40_qpi_cv_anchor_assembly_accepted/spectrum.csv"
CV_MANIFEST = CV.with_name("manifest.json")
TEBD = ROOT / "results/autoresearch_v5_20260803/round26_qpi_tebd_production/cell-alpha023-qpi-dt00125-t30/spectrum.csv"
TEBD_MANIFEST = TEBD.with_name("manifest.json")
CROSS = ROOT / "results/autoresearch_v5_20260805/round40_cv_tebd_accepted7_analysis/cross-method-check.json"
FAILED = ROOT / "results/research_progress/round41_low005_retry_validator_20260805.json"
FREEZE = ROOT / "results/research_progress/dynamic_gate_freeze_20260805.json"
PROJECTION = ROOT / "results/autoresearch_v3_20260729/round1_doublet_projection/representative.csv"
BASE = ROOT / "figures/paper_fig8_bounded_cv_tebd_20260805"
REPORT_PNG = ROOT / "results/research_progress/paper_fig8_bounded_cv_tebd_20260805.png"
SOURCE_DATA = ROOT / "results/research_progress/fig8_bounded_source_data_20260805.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def interpolate(grid: np.ndarray, values: np.ndarray, points: np.ndarray) -> np.ndarray:
    return np.interp(points, grid, values)


def main() -> None:
    cross = json.loads(CROSS.read_text(encoding="utf-8"))
    freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
    failed = json.loads(FAILED.read_text(encoding="utf-8"))
    if cross.get("tag") != "NotEvaluable" or freeze.get("status") != "bounded_dynamic_delivery":
        raise SystemExit("动态冻结状态不匹配")
    if failed.get("status") != "fail" or failed.get("checks", {}).get("cv_residual") is not False:
        raise SystemExit("low-005 失败证据不匹配")

    cv_rows = rows(CV)
    cv_omega = np.array([float(row["omega"]) for row in cv_rows])
    cv_value = np.array([float(row["intensity"]) for row in cv_rows])
    cv_residual = np.array([float(row["relative_residual"]) for row in cv_rows])
    tebd_rows = rows(TEBD)
    tebd_omega = np.array([float(row["omega"]) for row in tebd_rows])
    # 历史 q=pi 单切片已采用 analyzer 的最终归一化。
    tebd_value = np.array([float(row["intensity"]) for row in tebd_rows])
    shared = interpolate(tebd_omega, tebd_value, cv_omega)
    relative = np.abs(shared - cv_value) / np.maximum(np.abs(cv_value), 1e-30)
    expected_relative = np.array(cross["diagnostics"]["shared_point_relative_differences"])
    if not np.allclose(relative, expected_relative, rtol=1e-10, atol=1e-12):
        raise SystemExit("图件 TEBD 归一化与 analyzer 不一致")

    projection = next(row for row in rows(PROJECTION) if math.isclose(float(row["alpha"]), 0.23))
    jeff = 0.5 * float(projection["jeff_over_beta"])
    continuum_upper = math.pi * jeff

    SOURCE_DATA.parent.mkdir(parents=True, exist_ok=True)
    with SOURCE_DATA.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["omega", "cv_intensity", "tebd_intensity", "relative_delta", "cv_residual", "accepted"])
        for values in zip(cv_omega, cv_value, shared, relative, cv_residual):
            writer.writerow([*values, True])
        writer.writerow([0.05, 1.8715182607020768, np.interp(0.05, tebd_omega, tebd_value), "", 1.1767005759300015e-5, False])

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
    })
    figure = plt.figure(figsize=(3.50, 3.55), constrained_layout=True)
    grid = figure.add_gridspec(2, 1, height_ratios=(2.45, 1.0), hspace=0.08)
    main_axis = figure.add_subplot(grid[0])
    delta_axis = figure.add_subplot(grid[1], sharex=main_axis)

    main_axis.axvspan(0.0, continuum_upper, color="#dce8df", alpha=0.72, label="effective window")
    main_axis.plot(tebd_omega, tebd_value, color="#276b8e", lw=1.35, label="TEBD")
    main_axis.scatter(cv_omega, cv_value, s=24, color="#c75b2a", edgecolor="white", linewidth=0.45, zorder=4, label="accepted CV")
    main_axis.scatter([0.05], [1.8715182607020768], s=34, facecolor="white", edgecolor="#9b2f2f", marker="X", linewidth=1.0, zorder=5, label="rejected CV")
    main_axis.set_ylabel(r"$S^{zz}(q=\pi,\omega)$")
    main_axis.set_xlim(0.0, 1.55)
    main_axis.set_ylim(bottom=0.0)
    main_axis.legend(loc="upper right", fontsize=5.2, handlelength=1.4, borderaxespad=0.35)
    main_axis.text(0.02, 0.96, "a", transform=main_axis.transAxes, va="top", fontweight="bold", fontsize=8)
    main_axis.text(0.04, 0.78, "bounded", transform=main_axis.transAxes, fontsize=6.2, color="#5d6f62")
    main_axis.tick_params(labelbottom=False)

    delta_axis.axhspan(0.0, 0.15, color="#edf3ef", zorder=0)
    delta_axis.axhline(0.15, color="#65756a", lw=0.85, ls="--", label="15% budget")
    delta_axis.scatter(cv_omega, relative, s=20, color="#604f8a", zorder=3)
    delta_axis.set_xlabel(r"$\omega/J_1$")
    delta_axis.set_ylabel("relative\ndifference")
    delta_axis.set_ylim(0.0, 0.17)
    delta_axis.set_yticks([0.0, 0.05, 0.10, 0.15])
    delta_axis.text(0.02, 0.92, "b", transform=delta_axis.transAxes, va="top", fontweight="bold", fontsize=8)
    delta_axis.text(0.98, 0.90, "max 6.40%", transform=delta_axis.transAxes, ha="right", va="top", fontsize=6.2)

    outputs: dict[str, str] = {}
    for suffix, kwargs in (
        (".svg", {}),
        (".pdf", {}),
        (".png", {"dpi": 450}),
        (".tiff", {"dpi": 600, "pil_kwargs": {"compression": "tiff_lzw"}}),
    ):
        path = BASE.with_suffix(suffix)
        figure.savefig(path, bbox_inches="tight", **kwargs)
        outputs[suffix] = sha256(path)
    plt.close(figure)
    shutil.copy2(BASE.with_suffix(".png"), REPORT_PNG)

    sources = [CV, CV_MANIFEST, TEBD, TEBD_MANIFEST, CROSS, FAILED, FREEZE, PROJECTION, SOURCE_DATA]
    sidecar = {
        "schema_version": 1,
        "figure_id": 8,
        "status": "bounded_seven_point_overlay",
        "backend": "Python/matplotlib",
        "archetype": "quantitative overlay",
        "core_conclusion": "七个 accepted CV 点与 TEBD 在共享频率上一致，但低频 residual 未通过，不能宣称完整动态交叉验收。",
        "acceptance": {
            "accepted_cv_points": len(cv_omega),
            "max_cv_residual": float(cv_residual.max()),
            "max_shared_point_relative_delta": float(relative.max()),
            "shared_window_weight_relative_delta": cross["diagnostics"]["shared_window_weight_relative_delta"],
            "low005_rejected_residual": failed["diagnostics"]["max_cv_residual"],
            "final_dynamic_claim_gate": False,
        },
        "source_files": [{"path": str(path.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(path)} for path in sources],
        "outputs": outputs,
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    BASE.with_suffix(".sources.json").write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "base": str(BASE), "max_delta": float(relative.max())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
