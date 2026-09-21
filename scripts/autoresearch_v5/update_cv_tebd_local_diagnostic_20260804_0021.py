"""登记已有 L=40 CV/TEBD 交叉门的本地定量诊断。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
REPORT_DIR = REPORT.parent
SOURCE = ROOT / "results/autoresearch_v5_20260803/round29_qpi_local_handoff/production_crosscheck/summary.json"
TITLE = "2026-08-04 00:21 L=40 CV/TEBD 交叉门本地定量诊断"


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    diagnostics = source["diagnostics"]
    cv = diagnostics["cv"]
    snapshot = {
        "checked_at": "2026-08-04T00:21:30+08:00",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "status": source["cross_method_tag"],
        "instance": source["instance"],
        "tebd": {
            "coarse_peak_omega": diagnostics["coarse_peak_omega"],
            "refined_peak_omega": diagnostics["refined_peak_omega"],
            "dt_peak_delta": diagnostics["dt_peak_delta"],
            "dt_weight_relative_delta": diagnostics["dt_weight_relative_delta"],
            "time_window_peak_delta": diagnostics["time_window_peak_delta"],
        },
        "cv": {
            "omegas": cv["omegas"],
            "main_peak_bracketed": cv["main_peak_bracketed"],
            "full_weight_window_covered": cv["full_weight_window_covered"],
            "point_relative_differences": cv["point_relative_differences"],
        },
        "next_required_cv_grid": [0.0, 0.05, 0.10, 0.15, 0.20, 0.55, 1.0, 1.5],
        "scope": {"negative_alpha_excluded": True, "fig9_excluded": True},
    }
    output = REPORT_DIR / "cv_tebd_local_diagnostic_20260804_0021.json"
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "复用已回传的 L=40 q=pi 生产谱和 CV anchor；不连接服务器、不新增重计算。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "TEBD 内部收敛通过；CV 交叉仍 NotEvaluable",
                "why": "dt/dt2 峰位差为 0、积分权重相对差 1.2348e-4，但 CV 频点没有包围 TEBD 主峰，也未覆盖主要积分窗。",
            },
            {
                "kind": "table",
                "columns": ["门槛", "本地证据", "判断"],
                "rows": [
                    ["dt/dt2 主峰", "TEBD coarse/refined 均为 omega=0.05；差值 0", "通过"],
                    ["dt/dt2 权重", "相对差 1.2348e-4；预算 5%", "通过"],
                    ["时间窗", "tmax=25/30 峰位差 0", "通过"],
                    ["CV 主峰覆盖", "CV 仅 omega=0.20,0.25,0.30,0.35", "未覆盖 omega≈0.05"],
                    ["CV 主要积分窗", "目标 [0,1.5]；当前网格从 0.20 到 0.35", "未覆盖"],
                ],
                "widths": ["24%", "48%", "28%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["诊断文件", "results/research_progress/cv_tebd_local_diagnostic_20260804_0021.json"],
                    ["当前标签", "NotEvaluable（不是 Disagreement，也不是 Agreement）"],
                    ["下一批最小频点", "omega=0.00,0.05,0.10,0.15,0.20,0.55,1.00,1.50；按低频→高频顺序执行"],
                ],
            },
            {
                "kind": "note",
                "label": "解释边界",
                "style": "pending",
                "text": "TEBD 的内部 dt/tmax 证据已经足够稳定，但不能用插值或稀疏 CV 点替代主峰和积分窗覆盖；round31 服务器顺序任务正是为关闭这两个缺口而设计。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · LOCAL CV/TEBD GATE"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": snapshot["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
