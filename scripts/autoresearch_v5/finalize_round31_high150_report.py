#!/usr/bin/env python3
"""用终态证据更新 round31 与 CV--TEBD 报告。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


OLD_TITLES = {
    "2026-08-04 round31 high-150 运行状态与 ETA",
    "2026-08-04 六点 accepted-only CV--TEBD 交叉分析",
}


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--validator", required=True)
    parser.add_argument("--anchor-dir", required=True)
    parser.add_argument("--crosscheck", required=True)
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()

    report_path = Path(args.report).resolve()
    validator_path = Path(args.validator).resolve()
    anchor_dir = Path(args.anchor_dir).resolve()
    crosscheck_path = Path(args.crosscheck).resolve()
    receipt_path = Path(args.receipt).resolve()
    required = [report_path, validator_path, anchor_dir / "manifest.json", anchor_dir / "spectrum.csv", crosscheck_path, receipt_path]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("缺少终态证据: " + "; ".join(missing))

    validator = load(validator_path)
    anchor = load(anchor_dir / "manifest.json")
    crosscheck = load(crosscheck_path)
    receipt = load(receipt_path)
    if validator.get("status") != "pass" or not all(validator.get("checks", {}).values()):
        raise SystemExit("high-150 validator 未通过")
    if anchor.get("status") != "success" or anchor.get("acceptance", {}).get("status") != "pass":
        raise SystemExit("accepted-only anchor 未通过")
    if receipt.get("status") != "pass" or receipt.get("non_clobbering") is not True:
        raise SystemExit("回传 receipt 未通过非覆盖验收")
    if crosscheck.get("tag") not in {"Agreement", "NotEvaluable", "Disagreement"}:
        raise SystemExit("CV--TEBD 结果标签无效")

    omegas = [float(value) for value in crosscheck["diagnostics"]["cv_omegas"]]
    coverage = crosscheck["coverage"]
    tag = str(crosscheck["tag"])
    verdict_status = "good" if tag == "Agreement" else "warn" if tag == "NotEvaluable" else "bad"
    point_max = max(float(value) for value in crosscheck["diagnostics"]["shared_point_relative_differences"])
    weight_delta = float(crosscheck["diagnostics"]["shared_window_weight_relative_delta"])
    section = {
        "title": "round31 high-150 终态回传与 accepted-only 动态验收",
        "note": "由 validator、非覆盖回传 receipt、accepted-only anchor 和 CV--TEBD analyzer 直接生成。",
        "blocks": [
            {"kind": "verdict", "status": verdict_status, "label": f"high-150 已通过；CV--TEBD={tag}", "why": f"accepted CV 共 {len(omegas)} 点，范围 {min(omegas):.2f}--{max(omegas):.2f}；逐点最大差 {point_max:.2%}，共享窗积分差 {weight_delta:.2%}。"},
            {"kind": "table", "columns": ["验收项", "结果", "判定"], "rows": [
                ["high-150 validator", validator["status"], "通过"],
                ["非覆盖回传", "pass", "通过"],
                ["主峰被 CV 网格包围", str(bool(coverage["main_peak_bracketed_by_cv_grid"])), "通过" if coverage["main_peak_bracketed_by_cv_grid"] else "未完成"],
                ["0--1.5 积分窗覆盖", str(bool(coverage["major_weight_window_covered_by_cv_grid"])), "通过" if coverage["major_weight_window_covered_by_cv_grid"] else "未完成"],
            ]},
            {"kind": "kv", "pairs": [["CV 频点", ", ".join(f"{value:.2f}" for value in omegas)], ["anchor", str(anchor_dir)], ["crosscheck", str(crosscheck_path)], ["receipt", str(receipt_path)]]},
            {"kind": "note", "label": "下一步", "style": "pending" if tag != "Agreement" else "info", "text": "若仍为 NotEvaluable，只按既定方案补低频 omega=0.05 独立 smoke；不降低 residual 门槛，不使用失败 low cell。" if tag != "Agreement" else "动态主张门可进入最终 delivery audit，但仍需重跑完整报告审计。"},
        ],
    }
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    report["sections"] = [section] + [item for item in report["sections"] if item.get("title") not in OLD_TITLES and item.get("title") != section["title"]]
    report["eyebrow"] = f"RESEARCH LOG · ROUND31 TERMINAL · CV–TEBD {tag.upper()}"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "updated", "tag": tag, "accepted_points": len(omegas)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
