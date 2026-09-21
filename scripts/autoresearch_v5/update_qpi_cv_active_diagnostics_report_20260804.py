"""把当前活动 cell 的只读运行诊断写入 HTML。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
DIAG = ROOT / "results/research_progress/qpi_cv_active_diagnostics_20260804.json"
TITLE = "2026-08-04 round31 high-100 活动 cell 运行诊断"


def main() -> None:
    data = json.loads(DIAG.read_text(encoding="utf-8"))
    process = next(item for item in data["processes"] if "julia" in item["pgrep"] and "/usr/bin/time" not in item["pgrep"])
    section = {
        "title": TITLE,
        "note": "只读读取 progress、文件时间、stdout 尾部和 ps 状态；没有修改远端。",
        "blocks": [
            {"kind": "verdict", "status": "good", "label": "不是进程卡死；Julia 正在高 CPU linsolve", "why": "Julia 进程状态 RNl、CPU 约 1761%，墙钟约 4.29 h；stderr 为空，progress.json 持续更新时间。"},
            {"kind": "table", "columns": ["诊断项", "结果", "解释"], "rows": [
                ["Julia 状态", "RNl；CPU 1761%", "约 17.6 个 CPU 核，正常计算活动"],
                ["墙钟", "04:17:31", "仍在 omega=1.00 单点 linsolve"],
                ["progress", "updated 00:26:50 UTC", "wrapper 仍活跃"],
                ["stderr/checkpoint", "空 / 无", "尚未到终态，不判失败"],
            ], "widths": ["25%", "28%", "47%"]},
            {"kind": "kv", "pairs": [["证据", "results/research_progress/qpi_cv_active_diagnostics_20260804.json"], ["stdout", "16 次 DMRG sweep 已完成；当前进入 CV linsolve"], ["决定", "不取消、不重启、不并行；等待 high-100 终态"]]},
            {"kind": "note", "label": "ETA 约束", "style": "pending", "text": "当前没有可可靠外推的剩余时间；只有 progress.json 出现 completed_points 或 manifest/status 终态后，才更新 ETA 并进入回传。"},
        ],
    }
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    report["sections"] = [s for s in report["sections"] if s.get("title") != TITLE]
    report["sections"].insert(2, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · ROUND31 ACTIVE LINSOLVE"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": "active_linsolve"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
