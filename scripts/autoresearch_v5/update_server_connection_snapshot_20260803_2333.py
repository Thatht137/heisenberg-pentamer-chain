"""记录服务器连接异常，避免把断连误判为计算终态。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
REPORT_DIR = REPORT.parent
TITLE = "2026-08-03 23:33 服务器连接快照"


def main() -> None:
    snapshot = {
        "checked_at": "2026-08-03T23:33:22+08:00",
        "host": "39.96.207.180",
        "ssh_port": 6000,
        "ssh_result": "connection_refused",
        "icmp_result": "reachable",
        "last_authoritative_state": {
            "checked_at": "2026-08-03T23:23:46+08:00",
            "cell": "cell-l40-qpi-low-000-020",
            "status": "running",
            "completed_points": 1,
            "total_points": 5,
            "manifest_present": False,
        },
        "action": "no_download_no_restart_no_second_julia",
        "scope": {"negative_alpha_excluded": True, "fig9_excluded": True},
    }
    (REPORT_DIR / "server_connection_snapshot_20260803_2333.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "一次只读连接检查；主机可达但 SSH 端口暂时拒绝连接。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "远端状态暂不可读取，不能判定终态",
                "why": "39.96.207.180 可 ping，但 6000 端口返回 Connection refused；没有新的 status/manifest/checksum 证据。",
            },
            {
                "kind": "table",
                "columns": ["项目", "证据", "决定"],
                "rows": [
                    ["最后可信任务状态", "23:23：低频 cell 1/5，phase=julia_linsolve", "暂按运行中保护"],
                    ["终态文件", "当时 manifest.json 不存在", "不执行 fetch/validator"],
                    ["网络", "ICMP reachable；SSH :6000 refused", "不反复短轮询"],
                    ["计算动作", "无新的远端命令", "不重启、不取消、不并行"],
                ],
                "widths": ["25%", "45%", "30%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["快照文件", "results/research_progress/server_connection_snapshot_20260803_2333.json"],
                    ["最后远端目录", "round31_qpi_cv_extension/cell-l40-qpi-low-000-020"],
                    ["恢复顺序", "SSH 恢复后先读 status/progress/manifest，再决定 checksum 与回传"],
                ],
            },
            {
                "kind": "note",
                "label": "保护条件",
                "style": "pending",
                "text": "连接恢复后仍需看到 success/failed 终态和完整文件，才能进入回传；Connection refused 本身不代表任务结束或失败。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(0, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 · REMOTE CONNECTION SNAPSHOT"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "ssh": snapshot["ssh_result"], "icmp": snapshot["icmp_result"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
