#!/usr/bin/env python3
"""把 high-150 健康检查追加到研究报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results/research_progress"
REPORT = RUN / "report.json"
HEALTH = RUN / "round31_high150_health_20260805_0751.json"
TITLE = "2026-08-05 high-150 运行健康检查 07:51"


def main() -> None:
    health = json.loads(HEALTH.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "计划外只读健康检查；不修改任务、不启动新 Julia。",
        "blocks": [
            {"kind": "verdict", "status": "good", "label": "high-150 正常运行，未发现宕机或程序错误", "why": "PID 324653 为 RNl，CPU≈1609%，progress 心跳新鲜，stderr=0；无 OOM、segfault 或 I/O error。"},
            {"kind": "table", "columns": ["项目", "数值", "判断"], "rows": [
                ["elapsed", f"{health['elapsed_seconds']/3600:.2f} h", "仍在 julia_linsolve"],
                ["CPU / RSS", "约 16.1 核 / 3.68 GiB", "持续有效计算"],
                ["可用内存", "238 GiB", "无内存压力"],
                ["swap", "5 MiB / 2 GiB", "无交换抖动"],
                ["/home 可用", "688 GiB", "无磁盘阻塞"],
                ["stderr / kernel", "0 B / 0 条", "无程序或内核错误"],
            ]},
            {"kind": "note", "label": "解释", "text": health["diagnosis"]},
            {"kind": "note", "label": "下一检查", "style": "pending", "text": "15:07 达到 24 h 复核边界；此前不轮询。若届时仍运行，由作者决定继续或停止。"},
            {"kind": "kv", "pairs": [["健康记录", "results/research_progress/round31_high150_health_20260805_0751.json"], ["automation", "round31-high-150 / 15:07 CST"]]},
        ],
    }
    report["sections"] = [section] + [item for item in report["sections"] if item.get("title") != TITLE]
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-05 · HIGH150 HEALTHY RUNNING"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": health["status"], "next_check": health["next_check"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
