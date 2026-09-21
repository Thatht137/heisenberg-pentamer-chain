"""记录一次性 round31 检查的实际执行结果。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-04 round31 一次性只读检查执行结果"
OLD_TITLE = "2026-08-04 round31 一次性只读检查已挂起"


def main() -> None:
    evidence = ROOT / "results/research_progress/qpi_cv_extension_scheduled_check_result_20260804.json"
    result = {
        "executed_at": "2026-08-04T02:09:02+08:00",
        "target": "wangjieren@39.96.207.180:6000",
        "result": "connection_refused",
        "remote_state": "unobservable",
        "snapshot_written": False,
        "last_local_remote_snapshot": "results/research_progress/qpi_cv_extension_remote_status_20260804.json",
        "last_authoritative_remote_state": "2026-08-03T23:23:46+08:00: low cell 1/5 running, manifest absent",
        "action": "只读；未写远端、未取消、未启动第二个 Julia",
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    evidence.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "定时器已按计划执行一次；SSH 连接失败，因此没有新的远端状态快照。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": "检查已执行，但 round31 仍不可观测", "why": "02:09:02 的 SSH 只读检查返回 Connection refused；不能把它解释为 Julia 完成或失败。"},
            {"kind": "table", "columns": ["项目", "结果", "决定"], "rows": [["定时器", "已执行一次", "不再重复启动检查"], ["SSH", "Connection refused", "保留最后可信快照"], ["远端终态", "未知", "不回传、不取消、不启动第二个 Julia"], ["当前交叉门", "NotEvaluable", "等待 CV/TEBD 主峰与积分窗证据"]], "widths": ["24%", "30%", "46%"]},
            {"kind": "kv", "pairs": [["执行证据", "results/research_progress/qpi_cv_extension_scheduled_check_result_20260804.json"], ["日志", "results/research_progress/qpi_cv_extension_remote_check_20260804.log"], ["最后可信状态", "low cell 1/5、running、manifest absent（2026-08-03 23:23:46）"]]},
            {"kind": "note", "label": "下一步", "style": "pending", "text": "服务器恢复后只做一次连接复核；若读到终态，依次执行远端 checksum、非覆盖回传、本地 checksum、validate_cv_run.py、anchor 组装和 CV–TEBD 分析。"},
        ],
    }
    report["sections"] = [s for s in report["sections"] if s.get("title") not in {TITLE, OLD_TITLE}]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · ROUND31 CHECK EXECUTED"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "result": result["result"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
