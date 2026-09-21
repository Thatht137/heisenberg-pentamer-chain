#!/usr/bin/env python3
"""把 13:51 服务器快照追加到离线研究报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SNAPSHOT = ROOT / "results/research_progress/server_progress_snapshot_20260803_1351.json"
DIAGNOSTIC = ROOT / "results/research_progress/l80_anchor_diagnostic_20260803_1351.json"
TITLE = "2026-08-03 13:51 anchor 长时运行复核"


def build_section(snapshot: dict[str, object], diagnostic: dict[str, object]) -> dict[str, object]:
    anchor = snapshot["anchor"]
    server = snapshot["server"]
    supervisor = snapshot["supervisor"]
    estimate = diagnostic["estimate"]
    return {
        "title": TITLE,
        "note": "一次性低频只读检查；未启动第二个 Julia",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "anchor 仍在有效求解，TEBD 继续等待",
                "why": f"Julia PID {anchor['julia_pid']} 已运行 {anchor['elapsed']}，CPU={anchor['cpu_percent']}%（约 16.2 核），状态 RNl、stderr 为空；points/和 checkpoint 仍为空。",
            },
            {
                "kind": "table",
                "columns": ["对象", "13:51 观测", "处理"],
                "rows": [
                    ["L=80 CV anchor", f"16 次 DMRG sweep；E={anchor['energy']:.12f}；仅 ground/source 已保存", "继续等待首个 linsolve 终态"],
                    ["进程", f"driver {anchor['driver_pid']} / Julia {anchor['julia_pid']}；{anchor['elapsed']}；{anchor['cpu_percent']}% CPU", "不取消、不覆盖"],
                    ["服务器资源", f"80 核；可用内存 {server['memory_available_gib']} / {server['memory_total_gib']} GiB；负载 {server['load_average']}", "资源不是瓶颈"],
                    ["supervisor", supervisor["last_log"], "保持自动接续"],
                    ["TEBD", "status.json 不存在", "不手动绕过"],
                ],
                "widths": ["22%", "49%", "29%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["ETA（低置信度）", f"较可能还需 {estimate['likely_remaining_hours'][0]}–{estimate['likely_remaining_hours'][1]} h；保守还需 {estimate['conservative_remaining_hours'][1]} h"],
                    ["较可能窗口", estimate["likely_terminal_window_local"]],
                    ["保守截止", estimate["conservative_terminal_deadline_local"]],
                    ["终态动作", "回传独立目录 -> validate_cv_run.py -> checksum -> TEBD 交叉验收"],
                    ["范围", "0 <= alpha,beta <= 1；负 alpha 和 Fig. 9 排除"],
                ],
            },
            {
                "kind": "code",
                "title": "本轮证据",
                "text": "results/research_progress/server_progress_snapshot_20260803_1351.json\nresults/research_progress/l80_anchor_diagnostic_20260803_1351.json\n远端：round23_tebd_crosscheck/sequential_supervisor.log",
            },
            {
                "kind": "note",
                "label": "轮询纪律",
                "style": "pending",
                "text": "本次检查后不做短间隔重复 SSH；等待 anchor 终态文件或 supervisor 出现 TEBD 启动事件。",
            },
        ],
    }


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    diagnostic = json.loads(DIAGNOSTIC.read_text(encoding="utf-8"))
    report["sections"] = [section for section in report["sections"] if section["title"] != TITLE]
    report["sections"].insert(0, build_section(snapshot, diagnostic))
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "section": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
