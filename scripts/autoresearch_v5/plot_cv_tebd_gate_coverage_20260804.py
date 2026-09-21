"""绘制 CV--TEBD 动力学验收门的频率覆盖审计图。"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
SPARSE = ROOT / "results/research_progress/cv_sparse_anchor_table_20260804.json"
DIAGNOSTIC = ROOT / "results/research_progress/cv_tebd_local_diagnostic_20260804_0021.json"
REPORT = ROOT / "results/research_progress/report.json"
OUT_STEM = ROOT / "figures/cv_tebd_gate_coverage_20260804"
OUTPUT = ROOT / "results/research_progress/cv_tebd_gate_coverage_20260804.json"
TITLE = "2026-08-04 CV--TEBD 动力学门覆盖审计"


def main() -> None:
    sparse = json.loads(SPARSE.read_text(encoding="utf-8"))
    diagnostic = json.loads(DIAGNOSTIC.read_text(encoding="utf-8"))
    accepted = [float(value) for value in sparse["accepted_omega"]]
    failed = [value for value in [0.0, 0.05, 0.10, 0.15, 0.20] if value not in accepted]
    pending = [value for value in [1.0, 1.5] if value not in accepted]
    tebd_peak = float(diagnostic["tebd"]["refined_peak_omega"])
    required = [float(value) for value in diagnostic["next_required_cv_grid"]]
    result = {
        "schema_version": 1,
        "checked_at": "2026-08-04T09:00:00+08:00",
        "status": "NotEvaluable",
        "instance": diagnostic["instance"],
        "tebd_peak_omega": tebd_peak,
        "accepted_cv_omega": accepted,
        "failed_cv_omega": failed,
        "pending_cv_omega": pending,
        "required_grid": required,
        "coverage": {
            "main_peak_covered": False,
            "integral_window_0_to_1_5_covered": False,
            "accepted_min": min(accepted),
            "accepted_max": max(accepted),
        },
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
        "interpretation": "当前已通过 CV 点位于 0.20--1.00；TEBD 主峰约 0.05 未被包围，且 [0,1.5] 积分窗未覆盖，因此不能进行 CV--TEBD Agreement 判定。",
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
        }
    )
    figure, axis = plt.subplots(figsize=(7.2, 2.45), constrained_layout=True)
    axis.axvspan(0.0, 1.5, color="#dbeafe", alpha=0.7, label="integral window [0, 1.5]")
    axis.axvline(tebd_peak, color="#b91c1c", linewidth=1.5, linestyle="--", label=fr"TEBD peak $\omega={tebd_peak:g}$")
    axis.scatter(accepted, [0.54] * len(accepted), s=70, color="#15803d", marker="o", zorder=4, label="accepted CV")
    axis.scatter(failed, [0.30] * len(failed), s=70, color="#dc2626", marker="x", linewidth=2.0, zorder=4, label="CV residual fail")
    axis.scatter(pending, [0.78] * len(pending), s=70, facecolors="white", edgecolors="#64748b", marker="s", linewidth=1.5, zorder=4, label="pending CV")
    axis.text(0.05, 0.60, "TEBD peak covered: NO", color="#b91c1c", fontsize=8, weight="bold")
    axis.text(0.76, 0.60, "accepted: 0.20–1.00", color="#166534", fontsize=8)
    axis.text(0.76, 0.20, "low cell residual > 1e-5", color="#991b1b", fontsize=7.5)
    axis.set_xlim(-0.03, 1.58)
    axis.set_ylim(0.05, 0.95)
    axis.set_yticks([])
    axis.set_xlabel(r"$\omega/J_1$")
    axis.set_title("CV–TEBD gate coverage: NotEvaluable", fontsize=11, weight="bold")
    axis.legend(loc="upper left", ncol=2, fontsize=7, frameon=False)
    figure.text(0.5, -0.035, "Cover the omega≈0.05 peak first, then complete [0,1.5]; residual thresholds unchanged.", ha="center", fontsize=7.2, color="#555555")
    for suffix, kwargs in [("png", {"dpi": 600}), ("tiff", {"dpi": 600})]:
        figure.savefig(OUT_STEM.with_suffix(f".{suffix}"), bbox_inches="tight", **kwargs)
    figure.savefig(OUT_STEM.with_suffix(".svg"), bbox_inches="tight")
    figure.savefig(OUT_STEM.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(figure)

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "只用已有 TEBD 诊断和 CV sparse anchor；不连接服务器、不改变失败 cell、不降低 residual 门槛。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": "CV--TEBD 仍为 NotEvaluable", "why": "已通过 CV 点为 0.20–1.00，未覆盖 TEBD 主峰约 0.05，也未覆盖完整 [0,1.5] 积分窗。"},
            {"kind": "figures", "items": [{"src": "../../figures/cv_tebd_gate_coverage_20260804.png", "caption": "频率覆盖审计。绿色圆点为已通过 CV，红叉为 residual 失败低频点，空方块为尚待计算点，红虚线为 TEBD 主峰；蓝色区域为主要积分窗。"}]},
            {"kind": "kv", "pairs": [["JSON", "results/research_progress/cv_tebd_gate_coverage_20260804.json"], ["下一必要覆盖", "omega=0.05 附近及 0--1.5 主要积分窗"], ["验收规则", "CV residual <= 1e-5；不以 pilot 或失败 cell 关闭动态门"]]},
        ],
    }
    report["sections"] = [entry for entry in report["sections"] if entry.get("title") != TITLE]
    report["sections"].insert(4, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · CV–TEBD COVERAGE AUDIT"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "accepted": accepted, "failed": failed, "pending": pending}, ensure_ascii=False))


if __name__ == "__main__":
    main()
