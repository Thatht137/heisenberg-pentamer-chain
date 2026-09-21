#!/usr/bin/env python3
"""记录低频动态任务的交接工具状态。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-05 low-005 终态交接与 round42 条件启动工具"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "只完成本地工具与测试；未上传或启动 round42，不影响服务器当前 low-005。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "终态后的严格交接已可直接执行",
                "why": "交接器验证非覆盖 receipt、validator、accepted-only 组装和 CV--TEBD 返回码；失败即停。",
            },
            {
                "kind": "table",
                "columns": ["工具", "用途", "保护规则"],
                "rows": [
                    ["handoff_round41_low005.py", "low-005 回传后的八点组装与交叉分析", "路径限制、拒绝覆盖、validator 全通过才继续"],
                    ["launch_round42_qpi_cv_low000_20260805.sh", "条件补 omega=0.00", "low-005 通过、无 Julia、哈希和资源检查"],
                ],
                "widths": ["35%", "30%", "35%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["保护测试", "8/8 通过"],
                    ["round42 当前", "未上传、未启动"],
                    ["预估", "失败 residual 代理给出峰位差 0、完整窗积分差约 1.84%；仅用于排程"],
                    ["下一读取", "2026-08-05 22:10 CST"],
                ],
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(1, section)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "updated", "title": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
