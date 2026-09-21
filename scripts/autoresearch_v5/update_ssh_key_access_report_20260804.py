"""记录本机 SSH 私钥可访问性复核。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
KEY = Path(r"C:\Users\hh250\.ssh\id_ed25519")
TITLE = "2026-08-04 SSH 私钥可访问性复核"


def main() -> None:
    digest = hashlib.sha256(KEY.read_bytes()).hexdigest()
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "只读检查本机密钥文件；未连接服务器。",
        "blocks": [
            {"kind": "verdict", "status": "good", "label": "私钥已确认存在", "why": "C:/Users/hh250/.ssh/id_ed25519 可读取；后续 SSH 必须使用该私钥，不能使用 .pub 文件。"},
            {"kind": "kv", "pairs": [["私钥", "~/.ssh/id_ed25519"], ["文件大小", f"{KEY.stat().st_size} bytes"], ["SHA-256", digest], ["服务器连接", "尚未执行；等待 02:09 只读窗口"]]},
            {"kind": "note", "label": "安全边界", "style": "pending", "text": "私钥内容不写入报告；只记录路径、大小和哈希。服务器任务仍不启动、不取消、不并行。"},
        ],
    }
    report["sections"] = [item for item in report["sections"] if item["title"] != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · SSH READY"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "bytes": KEY.stat().st_size, "sha256": digest}, ensure_ascii=False))


if __name__ == "__main__":
    main()
