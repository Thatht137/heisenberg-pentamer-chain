"""把服务器连接恢复纪律登记到 HTML 报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-03 服务器中断恢复标准"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "针对当前 6000 端口中断情况补充；不改变任何计算结果。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "恢复流程已写入标准",
                "why": "明确区分 SSH 服务/认证故障与 Julia 计算终态，恢复后必须先读状态文件再进入回传验收。",
            },
            {
                "kind": "list",
                "title": "必须遵守",
                "items": [
                    "客户端使用 ~/.ssh/id_ed25519 私钥，不使用 .pub 公钥文件作为 -i 参数。",
                    "6000 返回 Connection refused 时不重启、不取消、不并行启动新 Julia。",
                    "连接恢复后依次读取 status.json、progress.json、manifest.json，再执行 checksum、回传和 validate_cv_run.py。",
                    "范围固定为 0<=alpha,beta<=1，负 alpha 和 Fig. 9 排除。",
                ],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["详细文档", "docs/server_run_guide.md 的“SSH 中断时的恢复纪律”"],
                    ["当前最后可信状态", "round31 q=pi CV 低频 cell：1/5；manifest 尚不存在"],
                ],
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 · SERVER RECOVERY STANDARD"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": "recorded"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
