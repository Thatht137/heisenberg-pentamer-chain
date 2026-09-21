"""把一次性后台检查的 armed 状态写入 HTML。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-04 round31 一次性只读检查已挂起"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "后台进程只等待到指定时间并执行一次检查；不循环、不写远端。",
        "blocks": [
            {"kind": "verdict", "status": "good", "label": "02:09 北京时间检查已挂起", "why": "后台 PowerShell 进程按 UTC 正确换算目标时间，当前仍在等待；不会启动或干预 Julia。"},
            {"kind": "kv", "pairs": [["目标时间", "2026-08-04 02:09:00 +08:00"], ["后台 PID", "42248"], ["检查类型", "round31 全局状态 + 四个 cell 的 progress/status/manifest/checkpoint，只读"]]},
            {"kind": "note", "label": "保护规则", "style": "pending", "text": "若连接失败，只保留失败日志；若连接成功，只保存状态快照。后续回传、checksum 和验收仍需人工/主流程按顺序执行。"},
        ],
    }
    report["sections"] = [item for item in report["sections"] if item["title"] != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · ROUND31 MONITOR ARMED"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": "armed"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
