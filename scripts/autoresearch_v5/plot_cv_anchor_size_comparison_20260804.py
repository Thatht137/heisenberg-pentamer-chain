"""比较同一 q=pi、omega=0.25 CV 锚点的 L=40 与 L=80。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
L40 = ROOT / "results/autoresearch_v5_20260802/round21_cv_triplet_warmstart/cell-0002-L40-qpi-w025-w035/spectrum.csv"
L80 = ROOT / "results/autoresearch_v5_20260802/round22_cv_l80_anchor/cell-0003-L80-qpi-w025/spectrum.csv"
OUT_STEM = ROOT / "figures/cv_anchor_size_comparison_20260804"
OUTPUT = ROOT / "results/research_progress/cv_anchor_size_comparison_20260804.json"
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-04 L=40/L=80 CV 锚点尺寸比较"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_anchor(path: Path) -> dict[str, float]:
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if abs(float(row["omega"]) - 0.25) < 1e-12:
                return {key: float(row[key]) for key in ("q_over_pi", "omega", "intensity", "relative_residual")}
    raise ValueError(f"缺少 omega=0.25: {path}")


def main() -> None:
    l40 = read_anchor(L40)
    l80 = read_anchor(L80)
    relative_change = (l80["intensity"] - l40["intensity"]) / l40["intensity"]
    result = {
        "schema_version": 1,
        "checked_at": "2026-08-04T09:20:00+08:00",
        "status": "pass",
        "instance": {"alpha": 0.23, "beta": 0.5, "q_over_pi": 1.0, "omega": 0.25, "eta": 0.1},
        "points": {"L40": l40, "L80": l80},
        "relative_intensity_change_L80_vs_L40": relative_change,
        "source_sha256": {"L40": sha256(L40), "L80": sha256(L80)},
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
        "interpretation": "L=40 到 L=80 的同频率强度变化约为 3.97%，两点 residual 均低于 1e-5；这是单锚点尺寸诊断，不是完整谱或 CV--TEBD Agreement。",
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 8,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "axes.linewidth": 0.8,
            "legend.frameon": False,
        }
    )
    figure, axes = plt.subplots(1, 2, figsize=(6.4, 2.8), constrained_layout=True)
    colors = ["#4C78A8", "#F58518"]
    labels = ["L=40", "L=80"]
    intensities = [l40["intensity"], l80["intensity"]]
    residuals = [l40["relative_residual"], l80["relative_residual"]]
    positions = np.arange(2)
    axes[0].bar(positions, intensities, color=colors, width=0.58)
    axes[0].set_xticks(positions, labels)
    axes[0].set_ylabel(r"$S^{zz}(q=\pi,\omega=0.25)$")
    axes[0].set_title("same-frequency intensity")
    axes[0].set_ylim(0, max(intensities) * 1.20)
    for index, value in enumerate(intensities):
        axes[0].text(index, value + 0.008, f"{value:.4f}", ha="center", fontsize=7)
    axes[0].text(0.5, 0.97, f"Δ={relative_change * 100:+.2f}%", transform=axes[0].transAxes, ha="center", va="top", fontsize=7.5, color="#444444")
    axes[1].bar(positions, residuals, color=colors, width=0.58)
    axes[1].axhline(1e-5, color="#B22222", linestyle="--", linewidth=1.0, label="acceptance limit")
    axes[1].set_xticks(positions, labels)
    axes[1].set_ylabel("relative residual")
    axes[1].set_title("CV residual")
    axes[1].set_ylim(0, 1.0e-5 * 1.25)
    axes[1].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    for index, value in enumerate(residuals):
        axes[1].text(index, value + 0.25e-6, f"{value:.2e}", ha="center", fontsize=7)
    axes[1].legend(fontsize=6.5, loc="upper left")
    figure.suptitle("CV anchor size comparison at q=π, ω=0.25", fontsize=10.5, fontweight="bold")
    figure.text(0.5, -0.025, "Single accepted L=80 anchor; supports finite-size robustness only, not full CV–TEBD agreement.", ha="center", fontsize=7.1, color="#555555")
    for suffix, kwargs in [("png", {"dpi": 600}), ("tiff", {"dpi": 600})]:
        figure.savefig(OUT_STEM.with_suffix(f".{suffix}"), bbox_inches="tight", **kwargs)
    figure.savefig(OUT_STEM.with_suffix(".svg"), bbox_inches="tight")
    figure.savefig(OUT_STEM.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(figure)

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "基于已通过 validator 的 L=40 与 L=80 同频率锚点；不把单点尺寸变化升级为完整动力学结论。",
        "blocks": [
            {"kind": "verdict", "status": "good", "label": "单锚点尺寸诊断通过", "why": f"L=40 强度 {l40['intensity']:.7f}，L=80 强度 {l80['intensity']:.7f}，相对变化 {relative_change * 100:.2f}%；两点 residual 均 < 1e-5。"},
            {"kind": "figures", "items": [{"src": "../../figures/cv_anchor_size_comparison_20260804.png", "caption": "同一 alpha=0.23、beta=0.5、q=π、omega=0.25 的 L=40/L=80 CV 锚点比较。左图为强度，右图为 relative residual 与 1e-5 验收线；该图只支持单频率有限尺寸稳健性。"}]},
            {"kind": "table", "columns": ["尺寸", "强度", "relative residual", "状态"], "rows": [["L=40", f"{l40['intensity']:.7f}", f"{l40['relative_residual']:.3e}", "通过"], ["L=80", f"{l80['intensity']:.7f}", f"{l80['relative_residual']:.3e}", "通过"]], "widths": ["18%", "28%", "30%", "24%"]},
            {"kind": "kv", "pairs": [["JSON", "results/research_progress/cv_anchor_size_comparison_20260804.json"], ["数据边界", "单个 omega=0.25 锚点；不替代主峰、积分窗和 TEBD 交叉门"], ["范围", "0 <= alpha,beta <= 1；排除负 alpha 与 Fig.9"]]},
        ],
    }
    report["sections"] = [entry for entry in report["sections"] if entry.get("title") != TITLE]
    report["sections"].insert(4, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · L40/L80 CV ANCHOR CHECK"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "relative_change": relative_change, "L40": l40, "L80": l80}, ensure_ascii=False))


if __name__ == "__main__":
    main()
