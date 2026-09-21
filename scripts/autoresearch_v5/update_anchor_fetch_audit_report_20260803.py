"""把 anchor 终态回传器的本地审计写入 HTML 报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
TITLE = "2026-08-03 14:36 anchor 终态回传器本地审计"


def build_section() -> dict[str, object]:
    return {
        "title": TITLE,
        "note": "只做本地 PowerShell 语法和流程审计；未执行 SSH、scp 或远端修改",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "终态回传器已准备",
                "why": "脚本只接受 success 状态，并要求远端 checksum、下载后 checksum 和 manifest.acceptance=pass；临时目录校验通过后才原子移动。",
            },
            {
                "kind": "table",
                "columns": ["保护条件", "实现", "状态"],
                "rows": [
                    ["运行中保护", "status != success 时退出，不下载", "通过"],
                    ["远端完整性", "先执行 sha256sum -c checksums.sha256", "通过"],
                    ["本地完整性", "临时目录逐文件 SHA-256 后再移动", "通过"],
                    ["覆盖保护", "已有有效目录只报告，不覆盖；已有坏目录直接拒绝", "通过"],
                    ["范围保护", "固定 cell-0003-L80-qpi-w025；不含负 alpha", "通过"],
                ],
                "widths": ["24%", "52%", "24%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["本地语法", "PowerShell Parser PASS；Python compileall PASS"],
                    ["执行状态", "未执行 fetch；等待 anchor 终态"],
                    ["终态后顺序", "fetch_cv_anchor_20260803.ps1 -> validate_cv_run.py -> local checksum -> 检查 supervisor/TEBD"],
                    ["范围", "0 <= alpha,beta <= 1；负 alpha 与 Fig. 9 排除"],
                ],
            },
            {
                "kind": "code",
                "title": "回传器",
                "text": "scripts/autoresearch_v5/fetch_cv_anchor_20260803.ps1\nscripts/autoresearch_v5/validate_cv_run.py",
            },
            {
                "kind": "note",
                "label": "下一动作",
                "style": "pending",
                "text": "北京时间 16:20 只读检查服务器；只有 anchor status.json 变为 success 才执行回传器。",
            },
        ],
    }


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    report["sections"] = [section for section in report["sections"] if section["title"] != TITLE]
    report["sections"].insert(0, build_section())
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "section": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
