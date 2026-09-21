#!/usr/bin/env python3
"""记录 CV 自适应重试修复与 high-150 终态交接。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-05 adaptive retry 修复记录与 high-150 终态"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "只更新本地审计报告；不降低验收门槛、不覆盖原始 run、不启动新的 Julia。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "adaptive retry 修复已完成",
                "why": "CV 求解在单点 residual > 1e-5 时对当前点追加更高 linsolve 预算，原始失败目录仍保持不可变。",
            },
            {
                "kind": "table",
                "columns": ["项目", "修复/证据", "验收处理"],
                "rows": [
                    ["触发条件", "单点 residual > 1e-5", "门槛保持不变"],
                    ["追加预算", "nsweeps=max(nsweeps+4, 2*nsweeps)，maxiter=1000，krylovdim=200", "仅重解当前频点"],
                    ["round41 low-005", "1.17068e-5，原 run 已隔离", "不进入 accepted-only"],
                    ["high-150 omega=1.50", "终态 pass，max residual=5.540316e-6", "可进入 checksum/validator 交接"],
                ],
            },
            {
                "kind": "note",
                "label": "交接状态",
                "style": "pending",
                "text": "原计划为“等待 high-150 终态后再部署”；当前 high-150 已自然终态且远端 checksum 通过。下一步仍需非覆盖回传、本地 checksum、validator 和 CV--TEBD 分析；本记录未执行这些写入操作。",
            },
            {
                "kind": "kv",
                "pairs": [
                    ["修复代码", "scripts/autoresearch_v5/cv_dsf_cell.jl；scripts/autoresearch_v5/cv_dsf_resumable.jl"],
                    ["high-150 远端目录", "results/autoresearch_v5_20260803/round31_qpi_cv_extension/cell-l40-qpi-high-150"],
                    ["范围", "0 <= alpha,beta <= 1；排除负 alpha 与 Fig. 9"],
                ],
            },
        ],
    }
    report["sections"] = [section] + [item for item in report["sections"] if item.get("title") != TITLE]
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-05 · ADAPTIVE RETRY READY · HIGH150 TERMINAL"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "updated", "report": str(REPORT), "title": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
