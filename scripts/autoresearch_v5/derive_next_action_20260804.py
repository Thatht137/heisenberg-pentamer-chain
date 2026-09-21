# -*- coding: utf-8 -*-
"""根据本地快照推导下一步，避免误启动或提前回传。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROGRESS = ROOT / "results/research_progress"
OUT = PROGRESS / "next_action_decision_20260804.json"
REPORT = PROGRESS / "report.json"
TITLE = "2026-08-04 下一动作安全决策"


def load(name: str) -> dict[str, object]:
    return json.loads((PROGRESS / name).read_text(encoding="utf-8"))


def main() -> None:
    snapshots = sorted(PROGRESS.glob("qpi_cv_extension_remote_snapshot_20260804_*.json"))
    if not snapshots:
        raise SystemExit("缺少远端状态快照")
    remote_path = snapshots[-1]
    remote = json.loads(remote_path.read_text(encoding="utf-8"))
    retry = load("qpi_cv_retry_smoke_plan_20260804.json")
    static = load("static_delivery_manifest_20260804.json")
    active = remote["cells"]["cell-l40-qpi-high-100"]
    running = active.get("status") == "running"
    manifest_ready = bool(active.get("manifest_present"))
    if running or not manifest_ready:
        decision = {
            "status": "WAIT_REMOTE_TERMINAL",
            "allowed_action": "继续本地分析；不启动 retry smoke、不启动第二个 Julia、不回传 high-100 未终态目录",
            "blocking_evidence": ["cell-l40-qpi-high-100 status=running", "high-100 manifest_present=false"],
        }
    else:
        decision = {
            "status": "RECOVERY_PREFLIGHT_REQUIRED",
            "allowed_action": "先远端 checksum，再非覆盖回传和本地 validator；retry smoke 仍需独立目录",
            "blocking_evidence": [],
        }
    result = {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
        "decision": decision,
        "remote_snapshot": str(remote_path.relative_to(ROOT)).replace("\\", "/"),
        "retry_plan": {"status": retry["status"], "proposed_parameters": retry["proposed_parameters"]},
        "static_delivery": {"status": static["status"], "files": len(static["files"])},
        "next_transition": "仅当 high-100 产生 terminal manifest 且 overall_progress 结束时，进入 checksum→fetch→validate→assemble 顺序。",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "只使用本地远端快照和方案文件；不连接服务器、不改变运行状态。",
        "blocks": [
            {"kind": "verdict", "status": "warn" if decision["status"] == "WAIT_REMOTE_TERMINAL" else "good", "label": decision["status"], "why": decision["allowed_action"]},
            {"kind": "table", "columns": ["条件", "当前证据", "动作"], "rows": [["high-100", "running；manifest=false", "等待，不并行"], ["retry smoke", retry["status"], "不启动"], ["静态交付包", f"{static['status']}；{len(static['files'])} 文件", "可继续本地审阅"]]},
            {"kind": "kv", "pairs": [["决策 JSON", "results/research_progress/next_action_decision_20260804.json"], ["固定顺序", "remote checksum → non-clobber fetch → local checksum → validator → accepted anchors → CV–TEBD"], ["范围", "0 <= alpha,beta <= 1；排除负 alpha 和 Fig.9"]]},
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(2, section)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": decision["status"], "allowed_action": decision["allowed_action"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
