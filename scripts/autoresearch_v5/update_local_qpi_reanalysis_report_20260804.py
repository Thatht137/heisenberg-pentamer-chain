"""把 q=pi 本地独立重分析登记到 HTML 报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SUMMARY = ROOT / "results/autoresearch_v5_20260804/round32_local_reanalysis_qpi/summary.json"
AUDIT = ROOT / "results/research_progress/local_qpi_reanalysis_20260804.json"
TITLE = "2026-08-04 q=pi L=40 已有数据独立重分析"


def main() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    diagnostics = summary["diagnostics"]
    maxdim = diagnostics["maxdim"]
    cv = diagnostics["cv"]
    result = {
        "schema_version": 1,
        "status": summary["status"],
        "qpi_production_status": summary["qpi_production_status"],
        "full_dynamic_status": summary["full_dynamic_status"],
        "tebd_qpi_tag": summary["tebd_qpi_tag"],
        "cross_method_tag": summary["cross_method_tag"],
        "params": summary["params"],
        "diagnostics": {
            "dt_weight_relative_delta": diagnostics["dt_weight_relative_delta"],
            "maxdim_weight_relative_delta": maxdim["weight_relative_delta"],
            "maxdim_spectrum_relative_l2": maxdim["spectrum_relative_l2"],
            "cv_point_relative_differences": cv["point_relative_differences"],
            "cv_main_peak_bracketed": cv["main_peak_bracketed"],
            "cv_full_weight_window_covered": cv["full_weight_window_covered"],
        },
        "scope": {"negative_alpha_excluded": True, "fig9_excluded": True},
        "figure": "figures/qpi_tebd_local_reanalysis_20260804.png",
    }
    AUDIT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "仅复用已回传的 L=40 TEBD、maxdim=96 和 CV 锚点；不连接服务器、不新增 Julia 计算。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "TEBD 内部生产门通过；CV 交叉仍不可评估",
                "why": "dt/dt2、tmax、maxdim、非负性和 Fourier 复算均通过；CV 频点仍未包围 omega=0.05 主峰或 [0,1.5] 积分窗。",
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "../../figures/qpi_tebd_local_reanalysis_20260804.png",
                        "caption": "本地独立重分析。a：L=40 严格 q=pi 的 TEBD dt、tmax=25/30、maxdim=96/320 曲线与 CV 稀疏锚点；b：相对差值；c：内部验收门占用率。TEBD 内部收敛清晰，但 CV 点位于 0.20–0.35，未覆盖约 0.05 主峰。",
                    }
                ],
            },
            {
                "kind": "table",
                "columns": ["诊断量", "结果", "解释"],
                "rows": [
                    ["TEBD dt 权重相对差", f"{diagnostics['dt_weight_relative_delta']:.3e}", "低于 5% 门槛"],
                    ["maxdim=96 vs 320 权重差", f"{maxdim['weight_relative_delta']:.3e}", "独立截断档位通过"],
                    ["maxdim 谱相对 L2", f"{maxdim['spectrum_relative_l2']:.3e}", "曲线几乎重合"],
                    ["CV 点相对差范围", f"{min(cv['point_relative_differences']):.2%}–{max(cv['point_relative_differences']):.2%}", "只作稀疏点诊断"],
                    ["动态交叉标签", summary["cross_method_tag"], "主峰和积分窗覆盖后才能升级"],
                ],
                "widths": ["29%", "25%", "46%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["独立分析目录", "results/autoresearch_v5_20260804/round32_local_reanalysis_qpi/"],
                    ["摘要审计", "results/research_progress/local_qpi_reanalysis_20260804.json"],
                    ["绘图脚本", "scripts/autoresearch_v5/plot_qpi_tebd_production.py"],
                ],
            },
            {
                "kind": "note",
                "label": "边界",
                "style": "pending",
                "text": "本地重分析强化了严格 q=pi TEBD 的内部数值证据，但不替代 round31 低频 CV 顺序任务，也不关闭 Fig.6–8 动态生产门。范围仍为 0<=alpha,beta<=1；排除负 alpha 和 Fig.9。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · LOCAL QPI REANALYSIS"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": result["status"], "cross_method": result["cross_method_tag"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
