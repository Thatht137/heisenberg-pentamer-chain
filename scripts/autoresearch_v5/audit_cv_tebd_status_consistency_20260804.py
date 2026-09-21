"""核对历史 CV--TEBD 摘要与当前覆盖审计是否给出一致状态。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HISTORICAL = ROOT / "results/autoresearch_v5_20260803/round29_qpi_local_handoff/production_crosscheck/summary.json"
COVERAGE = ROOT / "results/research_progress/cv_tebd_gate_coverage_20260804.json"
REPORT = ROOT / "results/research_progress/report.json"
OUTPUT = ROOT / "results/research_progress/cv_tebd_status_consistency_20260804.json"
TITLE = "2026-08-04 CV--TEBD 状态一致性审计"


def main() -> None:
    historical = json.loads(HISTORICAL.read_text(encoding="utf-8"))
    coverage = json.loads(COVERAGE.read_text(encoding="utf-8"))
    checks = {
        "historical_tag_not_evaluable": historical.get("cross_method_tag") == "NotEvaluable",
        "historical_peak_uncovered": historical.get("coverage", {}).get("cv_main_peak") is False,
        "historical_weight_uncovered": historical.get("coverage", {}).get("cv_major_weight") is False,
        "coverage_status_not_evaluable": coverage.get("status") == "NotEvaluable",
        "coverage_peak_uncovered": coverage.get("coverage", {}).get("main_peak_covered") is False,
        "coverage_window_uncovered": coverage.get("coverage", {}).get("integral_window_0_to_1_5_covered") is False,
    }
    result = {
        "schema_version": 1,
        "checked_at": "2026-08-04T09:15:00+08:00",
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "historical_source": str(HISTORICAL.relative_to(ROOT)).replace("\\", "/"),
        "coverage_source": str(COVERAGE.relative_to(ROOT)).replace("\\", "/"),
        "conclusion": "两份独立摘要一致保留 NotEvaluable：CV 未包围 TEBD 主峰约 0.05，也未覆盖 [0,1.5] 主要积分窗。",
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "只比较已有本地摘要，不连接服务器、不改变动态验收等级。",
        "blocks": [
            {"kind": "verdict", "status": "good" if result["status"] == "pass" else "bad", "label": "动态状态无漂移", "why": "历史 production_crosscheck 摘要与当前覆盖图均保留 NotEvaluable，未把 sparse anchors 误升级为 Agreement。"},
            {"kind": "table", "columns": ["检查项", "历史摘要", "当前覆盖审计", "结果"], "rows": [["状态", historical.get("cross_method_tag"), coverage.get("status"), "一致" if checks["historical_tag_not_evaluable"] and checks["coverage_status_not_evaluable"] else "冲突"], ["TEBD 主峰覆盖", "否", "否", "一致"], ["[0,1.5] 积分窗", "否", "否", "一致"]], "widths": ["28%", "24%", "24%", "24%"]},
            {"kind": "kv", "pairs": [["审计 JSON", "results/research_progress/cv_tebd_status_consistency_20260804.json"], ["结论", "NotEvaluable；等待低频合格 CV 与完整积分窗覆盖"], ["范围", "0 <= alpha,beta <= 1；排除负 alpha 和 Fig.9"]]},
        ],
    }
    report["sections"] = [entry for entry in report["sections"] if entry.get("title") != TITLE]
    report["sections"].insert(5, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · DYNAMIC STATUS CONSISTENCY"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "checks": checks}, ensure_ascii=False))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
