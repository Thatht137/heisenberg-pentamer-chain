#!/usr/bin/env python3
"""登记 round20 CV smoke 的运行状态或最终验收结果。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
TITLE_PREFIX = "round20 CV checkpoint smoke"


def build_section(status: str, detail: str, why: str) -> dict[str, object]:
    good = status == "good"
    label = f"{TITLE_PREFIX}：{'已通过' if good else '运行中'}"
    return {
        "title": f"{TITLE_PREFIX}（{'已通过' if good else '运行中'}）",
        "note": "2026-08-02 · alpha=0.23、beta=0.5、L=40、q=pi、omega=0.25",
        "blocks": [
            {"kind": "verdict", "status": status, "label": label, "why": why},
            {
                "kind": "table",
                "columns": ["参数", "值", "用途"],
                "rows": [
                    ["模型点", "alpha=0.23, beta=0.5", "复用已有 L=10 oracle 与 L=40 pilot"],
                    ["尺寸/扇区", "L=40, OBC, Sz=0", "明日 warm-start 成本探针"],
                    ["谱点", "q=pi, eta=0.1, omega=0.25", "只计算一个新频率点"],
                    ["精度/资源", "dmrg cutoff=1e-10, CV cutoff=1e-14, 8 threads, nice=10", "受控单任务"],
                    ["远端 PID", "Python 3691108；Julia 3691115", "断线可追踪"],
                ],
                "widths": ["20%", "36%", "44%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["远端 run", "results/autoresearch_v5_20260802/round20_cv_resume_warmstart/cell-0001-L40-qpi-w025"],
                    ["状态详情", detail],
                    ["下一步", "完成后回传并核对 manifest、checkpoint、残差、资源日志和 SHA-256；通过才追加 omega=0.30/0.35"],
                ],
            },
            {
                "kind": "note",
                "label": "运行边界",
                "style": "pending",
                "text": "这是独立 checkpoint smoke，不覆盖 round3，不扩展相图，不包含负 alpha，也不代表 L=80 生产谱已完成。",
            },
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", choices=["running", "good"], required=True)
    parser.add_argument("--detail", required=True)
    parser.add_argument("--why", required=True)
    args = parser.parse_args()
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    sections = [item for item in report["sections"] if not item["title"].startswith(TITLE_PREFIX)]
    index = next((i for i, item in enumerate(sections) if item["title"] == "2026-08-02 服务器与任务审计"), len(sections)) + 1
    sections.insert(index, build_section(args.status, args.detail, args.why))
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-02"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "status": args.status}, ensure_ascii=False))


if __name__ == "__main__":
    main()
