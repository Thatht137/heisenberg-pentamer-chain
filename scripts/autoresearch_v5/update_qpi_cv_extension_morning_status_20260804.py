"""把服务器恢复后的 round31 状态写入 HTML。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SNAPSHOT = ROOT / "results/research_progress/qpi_cv_extension_remote_status_20260804_morning.json"
TITLE = "2026-08-04 round31 服务器恢复后的 CV 扩展状态"


def main() -> None:
    payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    overall = payload["overall_progress"]
    low = payload["cells"]["cell-l40-qpi-low-000-020"]["manifest"]
    high055 = payload["cells"]["cell-l40-qpi-high-055"]["manifest"]
    high100 = payload["cells"]["cell-l40-qpi-high-100"]["progress"]
    high150 = payload["cells"]["cell-l40-qpi-high-150"]["progress"]
    section = {
        "title": TITLE,
        "note": "服务器恢复后的一次只读快照；没有下载或修改远端文件。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": "round31 仍运行中，2/4 cell 已有终态", "why": "低频 cell 结束但 residual 超过 1e-5；0.55 通过；1.00 正在 linsolve；1.50 尚未开始。"},
            {"kind": "table", "columns": ["cell", "状态", "关键证据", "决定"], "rows": [
                ["low 0.00–0.20", "success / acceptance fail", "5/5；max residual 1.3238e-5", "保留原始失败证据，不降门槛"],
                ["high 0.55", "success / accepted", "residual 6.4877e-6", "终态后独立回传"],
                ["high 1.00", "running", "0/1；elapsed≈4.13 h", "不干预、不并行"],
                ["high 1.50", "pending", "无 progress/manifest", "等待顺序执行"],
            ], "widths": ["22%", "24%", "30%", "24%"]},
            {"kind": "kv", "pairs": [
                ["全局状态", f"{overall['completed_cells']}/{overall['total_cells']} cells；phase={overall['phase']}；status={overall['status']}"],
                ["参数", "alpha=0.23, beta=0.5, L=40, q=pi, eta=0.1；仅正区"],
                ["快照", "results/research_progress/qpi_cv_extension_remote_status_20260804_morning.json"],
                ["远端 Julia", f"{payload['julia_process_count']} 条进程记录（同一活动 cell 的 time/wrapper + Julia）"],
            ]},
            {"kind": "note", "label": "回传与重试规则", "style": "pending", "text": "active cell 结束前不抓取整棵 run 目录；终态后先远端 sha256sum，再非覆盖回传。low cell 的 residual 失败只允许在 round31 完成后按预案做 omega=0.05 单点 smoke，不启动第二个 Julia。"},
        ],
    }
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    report["sections"] = [s for s in report["sections"] if s.get("title") != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · ROUND31 RUNNING 2/4"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "completed_cells": overall["completed_cells"], "total_cells": overall["total_cells"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
