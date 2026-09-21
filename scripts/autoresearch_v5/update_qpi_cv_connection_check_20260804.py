"""记录 round31 最新只读连接检查结果。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
REPORT_DIR = REPORT.parent
TITLE = "2026-08-04 round31 最新只读检查：SSH 仍不可达"


def main() -> None:
    snapshot = {
        "checked_at": "2026-08-04",
        "target": "wangjieren@39.96.207.180:6000",
        "result": "connection_refused",
        "remote_state": "unobservable",
        "last_authoritative_state": {
            "checked_at": "2026-08-03T23:23:46+08:00",
            "cell": "cell-l40-qpi-low-000-020",
            "completed_points": "1/5",
            "status": "running",
            "manifest_present": False,
            "julia_processes": 1,
        },
        "action": "只读检查；未写远端、未取消、未启动第二个 Julia、未下载",
        "scope": {
            "alpha_beta": "[0,1]",
            "negative_alpha_excluded": True,
            "fig9_excluded": True,
        },
    }
    out = REPORT_DIR / "qpi_cv_extension_remote_status_20260804.json"
    out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "本次只读 SSH 复核未能建立连接，因此不推断远端 Julia 的终态。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "round31 状态暂不可观测",
                "why": "39.96.207.180:6000 在连接层返回 Connection refused；不能把连接故障当作计算完成或失败。",
            },
            {
                "kind": "table",
                "columns": ["检查项", "结果", "处理"],
                "rows": [
                    ["目标", "wangjieren@39.96.207.180:6000", "保持原目录和顺序"],
                    ["最后可信快照", "low cell 1/5，running，manifest absent", "沿用 2026-08-03 23:23"],
                    ["本次动作", "只读连接检查失败", "不重启、不取消、不并行启动 Julia"],
                    ["当前交叉标签", "NotEvaluable", "缺少主峰与积分窗覆盖"],
                ],
                "widths": ["24%", "40%", "36%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["本地快照", "results/research_progress/qpi_cv_extension_remote_status_20260804.json"],
                    ["恢复后顺序", "读取 overall/status/progress/manifest -> 远端 checksum -> 独立回传 -> 本地 checksum -> validator -> anchor 组装"],
                    ["范围", "0 <= alpha,beta <= 1；排除负 alpha 与 Fig. 9"],
                ],
            },
            {
                "kind": "note",
                "label": "可继续的本地工作",
                "style": "info",
                "text": "继续维护 Fig. 1--8 的 provenance、HTML 审计和离线 validator；动态图保持 exploratory/constrained overlay，不升级为 production，直到 round31 终态和 CV--TEBD 交叉门通过。",
            },
        ],
    }
    sections = [s for s in report["sections"] if s.get("title") != TITLE]
    sections.insert(0, section)
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · ROUND31 CONNECTION CHECK"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "snapshot": str(out), "result": snapshot["result"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
