#!/usr/bin/env python3
"""登记六点 CV 与 TEBD 的交叉分析。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
RESULT = ROOT / "results/autoresearch_v5_20260804/round39_cv_tebd_accepted6_analysis/cross-method-check.json"
TITLE = "2026-08-04 六点 accepted-only CV--TEBD 交叉分析"


def main() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    diagnostics = result["diagnostics"]
    point_max = max(diagnostics["shared_point_relative_differences"])
    section = {
        "title": TITLE,
        "note": "仅使用通过单 run 验收和 checksum 的六个 CV 点；不使用 low residual 失败点。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": "共享点数值一致，但覆盖不足，正式标签仍为 NotEvaluable", "why": f"六点逐点最大相对差 {point_max:.2%}，共享窗积分差 {diagnostics['shared_window_weight_relative_delta']:.2%}；主峰与完整积分窗仍未覆盖。"},
            {"kind": "table", "columns": ["诊断", "结果", "预算/要求", "判定"], "rows": [
                ["共享点最大相对差", f"{point_max:.2%}", "诊断量", "一致"],
                ["共享窗积分相对差", f"{diagnostics['shared_window_weight_relative_delta']:.2%}", "<=15%", "通过诊断预算"],
                ["主峰覆盖", "否", "需包围 omega≈0.05", "未完成"],
                ["积分窗覆盖", "0.20–1.00", "0.00–1.50", "未完成"],
            ]},
            {"kind": "kv", "pairs": [["CV 频点", ", ".join(f"{value:.2f}" for value in diagnostics["cv_omegas"])], ["结果", "results/autoresearch_v5_20260804/round39_cv_tebd_accepted6_analysis/cross-method-check.json"], ["锚点集", "results/autoresearch_v5_20260803/round31_qpi_cv_anchor_assembly_accepted_20260804"], ["下一必要结果", "round31 high-150；低频主峰需保留 residual<=1e-5 的独立重算"]]},
            {"kind": "note", "label": "论文口径", "style": "pending", "text": "可以陈述现有共享频点与 TEBD 相符；不能陈述方法交叉已完成，也不能以共享子窗积分替代 0–1.5 主要积分窗。"},
        ],
    }
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    report["sections"] = [section] + [s for s in report["sections"] if s.get("title") != TITLE]
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · CV–TEBD NUMERICALLY CONSISTENT · COVERAGE OPEN"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["tag"], "point_max": point_max}, ensure_ascii=False))


if __name__ == "__main__":
    main()
