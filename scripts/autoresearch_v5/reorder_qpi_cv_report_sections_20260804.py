"""整理 round31 报告的时间顺序，避免旧连接失败快照遮挡新状态。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    old = "2026-08-04 round31 最新只读检查：SSH 仍不可达"
    renamed = "2026-08-04 01:53 连接失败快照（恢复前）"
    for section in report["sections"]:
        if section.get("title") == old:
            section["title"] = renamed
            section["note"] = "恢复前的连接失败快照；随后 08:18 已重新连通并取得 round31 状态。"
    priority = {
        "2026-08-04 round31 服务器恢复后的 CV 扩展状态": 0,
        "2026-08-04 round31 已结束 cell 回传与独立验收": 1,
        "2026-08-04 round31 一次性只读检查执行结果": 2,
        renamed: 3,
    }
    indexed = list(enumerate(report["sections"]))
    indexed.sort(key=lambda item: (priority.get(item[1].get("title"), 10), item[0]))
    report["sections"] = [section for _, section in indexed]
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · ROUND31 2/4 RUNNING"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"moved_to_top": [section["title"] for section in report["sections"][:4]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
