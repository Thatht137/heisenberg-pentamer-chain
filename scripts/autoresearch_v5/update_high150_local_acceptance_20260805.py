#!/usr/bin/env python3
"""记录 high-150 本地验收与七点交叉分析。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results/research_progress"
REPORT = RUN / "report.json"
VALIDATOR = RUN / "round31_high150_validator_20260805.json"
RECEIPT = RUN / "round31_high150_fetch_receipt_20260805.json"
CROSSCHECK = ROOT / "results/autoresearch_v5_20260805/round40_cv_tebd_accepted7_analysis/cross-method-check.json"
TITLE = "2026-08-05 high-150 本地验收与七点 CV--TEBD 分析"


def main() -> None:
    validator = json.loads(VALIDATOR.read_text(encoding="utf-8"))
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    crosscheck = json.loads(CROSSCHECK.read_text(encoding="utf-8"))
    if validator.get("status") != "pass" or not all(validator.get("checks", {}).values()):
        raise SystemExit("high-150 validator 未全部通过")
    if receipt.get("status") != "pass" or receipt.get("non_clobbering") is not True:
        raise SystemExit("high-150 回传 receipt 未通过")
    if crosscheck.get("tag") != "NotEvaluable":
        raise SystemExit("七点分析标签与预期不符")

    diagnostics = crosscheck["diagnostics"]
    point_max = max(diagnostics["shared_point_relative_differences"])
    high150_delta = diagnostics["shared_point_relative_differences"][-1]
    weight_delta = diagnostics["shared_window_weight_relative_delta"]
    section = {
        "title": TITLE,
        "note": "完整执行远端 checksum、非覆盖回传、本地 checksum、validator、accepted-only 组装和独立方法分析。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "high-150 完成本地独立验收",
                "why": "validator 全部通过；residual=5.540316e-6，方差、截断误差、谱非负性和完整性均通过。",
            },
            {
                "kind": "verdict",
                "status": "warn",
                "label": "七点 CV--TEBD 更接近，但严格标签仍为 NotEvaluable",
                "why": f"逐点最大差 {point_max:.2%}；omega=1.50 差 {high150_delta:.2%}；共享窗积分差降至 {weight_delta:.2%}。低频端点和主峰包围仍缺失。",
            },
            {
                "kind": "table",
                "columns": ["验收项", "结果", "解释"],
                "rows": [
                    ["非覆盖回传", "pass", "新目录；未覆盖六点基线"],
                    ["本地 checksum", "pass", "11 个回传文件完整"],
                    ["high-150 validator", "pass", "全部八项检查通过"],
                    ["accepted-only", "7 点：0.20--1.50", "只含已验收来源"],
                    ["主峰包围", "false", "仍缺 omega=0.00/0.05 低频结构"],
                    ["完整积分窗", "false", "左端尚未覆盖到 0.00"],
                ],
                "widths": ["27%", "25%", "48%"],
            },
            {
                "kind": "note",
                "label": "下一步",
                "style": "pending",
                "text": "等待正在运行的 omega=0.05 retry。若通过，再执行已登记的 omega=0.00 最小侧翼点；若失败，停止追加并保持 bounded。",
            },
        ],
    }
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(0, section)
    report["eyebrow"] = "RESEARCH LOG · HIGH150 LOCALLY VALIDATED · CV–TEBD 7-POINT NOT EVALUABLE"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "updated", "point_max": point_max, "weight_delta": weight_delta}, ensure_ascii=False))


if __name__ == "__main__":
    main()
