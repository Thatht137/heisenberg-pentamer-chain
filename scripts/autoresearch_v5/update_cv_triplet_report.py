#!/usr/bin/env python3
"""登记 round21 相邻频率 warm-start 的状态。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
PREFIX = "round21 CV 相邻频率 warm-start"


def section(status: str, detail: str, why: str) -> dict[str, object]:
    passed = status == "good"
    return {
        "title": f"{PREFIX}（{'已通过' if passed else '运行中'}）",
        "note": "2026-08-02 · alpha=0.23、beta=0.5、L=40、q=pi",
        "blocks": [
            {"kind": "verdict", "status": status, "label": f"{PREFIX}：{'已通过' if passed else '运行中'}", "why": why},
            {
                "kind": "table",
                "columns": ["项目", "设置", "状态"],
                "rows": [
                    ["seed 频点", "omega=0.25", "从 round20 checkpoint 复制，不重算"],
                    ["新增频点", "omega=0.30, 0.35", "按相邻频率 warm-start 顺序求解"],
                    ["资源", "8 threads, nice=10, CV cutoff=1e-14", "单独后台任务"],
                    ["远端进程", "Python 3698233；Julia 3698240", detail],
                ],
                "widths": ["20%", "36%", "44%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["远端 run", "results/autoresearch_v5_20260802/round21_cv_triplet_warmstart/cell-0002-L40-qpi-w025-w035"],
                    ["配置", "omega=0.25:0.05:0.35；max_new_points=2；seed provenance 已记录"],
                    ["下一步", "完成后回传，分别验收 omega=0.30/0.35 的残差、solve_seconds、D 和 checksum"],
                ],
            },
            {"kind": "note", "label": "范围边界", "style": "pending", "text": "只含 alpha>=0、beta>=0；不覆盖旧 run，不扩大相图，不代表 L=80 生产谱已完成。"},
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", choices=["running", "good"], required=True)
    parser.add_argument("--detail", required=True)
    parser.add_argument("--why", required=True)
    args = parser.parse_args()
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    sections = [item for item in report["sections"] if not item["title"].startswith(PREFIX)]
    index = next((i for i, item in enumerate(sections) if item["title"].startswith("round20 CV checkpoint smoke")), len(sections)) + 1
    sections.insert(index, section(args.status, args.detail, args.why))
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-02"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "status": args.status}, ensure_ascii=False))


if __name__ == "__main__":
    main()
