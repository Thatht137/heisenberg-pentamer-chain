"""把 q=pi 本地二次复核写入研究报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SUMMARY = ROOT / "results/autoresearch_v5_20260804/round36_local_qpi_reanalysis_recheck/summary.json"
AUDIT = ROOT / "results/research_progress/local_qpi_reanalysis_recheck_20260804.json"
TITLE = "2026-08-04 q=pi L=40 本地独立验收器二次复核"


def main() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    diagnostics = summary["diagnostics"]
    maxdim = diagnostics["maxdim"]
    cv = diagnostics["cv"]
    audit = {
        "schema_version": 1,
        "status": summary["status"],
        "full_dynamic_status": summary["full_dynamic_status"],
        "tebd_qpi_tag": summary["tebd_qpi_tag"],
        "cross_method_tag": summary["cross_method_tag"],
        "instance": summary["instance"],
        "checks": {
            "dt_weight_relative_delta": diagnostics["dt_weight_relative_delta"],
            "maxdim_spectrum_relative_l2": maxdim["spectrum_relative_l2"],
            "maxdim_weight_relative_delta": maxdim["weight_relative_delta"],
            "refined_peak_omega": diagnostics["refined_peak_omega"],
            "cv_main_peak_bracketed": cv["main_peak_bracketed"],
            "cv_full_weight_window_covered": cv["full_weight_window_covered"],
        },
        "source": "results/autoresearch_v5_20260804/round36_local_qpi_reanalysis_recheck/",
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "完全复用本地已回传资产，由独立验收器重新生成；不连接服务器、不新增 Julia 计算。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "二次复核与原结论一致",
                "why": "TEBD 内部生产门仍为 pass；CV 主峰和主要积分窗覆盖仍为 false，因此动态交叉继续保持 NotEvaluable。",
            },
            {
                "kind": "table",
                "columns": ["复核量", "二次复核结果", "解释"],
                "rows": [
                    ["TEBD 状态", summary["qpi_production_status"], "dt/dt2、tmax、maxdim、非负性和 Fourier 复算通过"],
                    ["主峰", f"omega={diagnostics['refined_peak_omega']:.2f}", "CV 频点未包围主峰"],
                    ["dt 权重相对差", f"{diagnostics['dt_weight_relative_delta']:.3e}", "低于 5% 门槛"],
                    ["maxdim 谱相对 L2", f"{maxdim['spectrum_relative_l2']:.3e}", "96/320 独立档位一致"],
                    ["CV--TEBD", summary["cross_method_tag"], "未覆盖主峰和 [0,1.5] 积分窗，不升级标签"],
                ],
                "widths": ["27%", "24%", "49%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["复核目录", "results/autoresearch_v5_20260804/round36_local_qpi_reanalysis_recheck/"],
                    ["审计摘要", "results/research_progress/local_qpi_reanalysis_recheck_20260804.json"],
                    ["范围", "0 <= alpha,beta <= 1；排除负 alpha 和 Fig.9"],
                ],
            },
            {
                "kind": "note",
                "label": "证据边界",
                "style": "pending",
                "text": "这次复核只增强已有 L=40 q=pi TEBD 的可重复性，不替代服务器 round31 低频 CV 终态，也不关闭 Fig.6--8 的动态生产门。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · LOCAL QPI RECHECK"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": audit["status"], "cross_method": audit["cross_method_tag"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
