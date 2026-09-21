"""记录 2026-08-04 00:09 的服务器只读连接结果。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
REPORT_DIR = REPORT.parent
TITLE = "2026-08-04 00:09 服务器只读连接复核"


def main() -> None:
    snapshot = {
        "checked_at": "2026-08-04T00:09:54+08:00",
        "host": "39.96.207.180",
        "port": 6000,
        "result": "connection_refused",
        "remote_state": "unobservable",
        "last_authoritative_state": "2026-08-03T23:23:46+08:00: cell 1/5, running, manifest absent",
        "action": "no_restart_no_cancel_no_parallel_julia_no_download",
        "scope": {
            "alpha_beta": "[0,1]",
            "negative_alpha_excluded": True,
            "fig9_excluded": True,
        },
    }
    (REPORT_DIR / "server_connection_snapshot_20260804_0009.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "一次带超时的只读 SSH 核查；未修改服务器配置、计算进程或本地既有结果。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "远端任务状态仍不可观测",
                "why": "39.96.207.180:6000 在连接层返回 Connection refused，无法读取 overall_progress、status、progress 或 manifest。",
            },
            {
                "kind": "table",
                "columns": ["项目", "结果", "决定"],
                "rows": [
                    ["目标", "wangjieren@39.96.207.180:6000", "保持原顺序任务目录"],
                    ["可观测性", "Connection refused", "不把 SSH 故障当作 Julia 终态"],
                    ["最后可信状态", "low cell 1/5；manifest absent", "沿用 2026-08-03 23:23 快照"],
                    ["保护动作", "未启动、未取消、未下载", "等待端口/认证恢复"],
                ],
                "widths": ["22%", "42%", "36%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["本次快照", "results/research_progress/server_connection_snapshot_20260804_0009.json"],
                    ["恢复后顺序", "读取 status/progress/manifest -> 远端 checksum -> 独立回传 -> 本地 checksum -> validate_cv_run.py -> assemble_qpi_cv_anchors.py"],
                    ["验收范围", "0 <= alpha,beta <= 1；排除负 alpha 与 Fig. 9"],
                ],
            },
            {
                "kind": "note",
                "label": "下一步",
                "style": "pending",
                "text": "在服务器恢复前继续本地报告、图表 provenance 和 validator 复核；不重复短间隔轮询，也不声称动态谱已完成。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(0, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · SERVER CONNECTION CHECK"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "result": snapshot["result"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
