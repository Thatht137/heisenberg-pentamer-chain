"""记录 6000 端口和默认端口的连接诊断。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
REPORT_DIR = REPORT.parent
TITLE = "2026-08-03 23:41 服务器 SSH 恢复诊断"


def main() -> None:
    snapshot = {
        "checked_at": "2026-08-03T23:41:14+08:00",
        "host": "39.96.207.180",
        "port_6000": "connection_refused",
        "port_22": "reachable_but_publickey_denied",
        "last_authoritative_state": "2026-08-03T23:23:46+08:00: cell 1/5, running, manifest absent",
        "action": "no_restart_no_download_no_parallel_julia",
        "scope": {"negative_alpha_excluded": True, "fig9_excluded": True},
    }
    (REPORT_DIR / "server_connection_snapshot_20260803_2341.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "一次只读恢复诊断；未修改服务器配置和计算进程。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "远端仍无可验收终态",
                "why": "专用端口 6000 返回 Connection refused；默认端口 22 可达但当前公钥认证失败。",
            },
            {
                "kind": "table",
                "columns": ["端口", "结果", "含义"],
                "rows": [
                    ["6000", "Connection refused", "专用 SSH 服务或端口转发暂不可用"],
                    ["22", "Permission denied (publickey,password)", "服务可达，但当前密钥未被接受"],
                    ["计算终态", "无新证据", "最后可信快照仍为 1/5、manifest absent"],
                    ["处理", "保持保护", "不重启、不取消、不并行、不下载"],
                ],
                "widths": ["18%", "42%", "40%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["诊断文件", "results/research_progress/server_connection_snapshot_20260803_2341.json"],
                    ["恢复后动作", "先读取 status/progress/manifest；只有 success/failed 终态才进行 checksum 和回传"],
                ],
            },
            {
                "kind": "note",
                "label": "保护边界",
                "style": "pending",
                "text": "连接问题不能被解释为 Julia 失败。若需要恢复服务器访问，应由用户或管理员修复 6000 端口/认证；本地报告和既有结果仍可继续使用。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(0, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 · SSH RECOVERY DIAGNOSTIC"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "port6000": snapshot["port_6000"], "port22": snapshot["port_22"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
