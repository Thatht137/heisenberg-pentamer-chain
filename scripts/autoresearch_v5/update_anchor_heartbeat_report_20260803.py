"""把新的 anchor 心跳写入离线研究报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SNAPSHOT = ROOT / "results/research_progress/server_progress_snapshot_20260803_1244.json"
TITLE = "2026-08-03 12:44 anchor 状态转折检查"


def build_section(snapshot: dict[str, object]) -> dict[str, object]:
    anchor = snapshot["anchor"]
    supervisor = snapshot["supervisor"]
    return {
        "title": TITLE,
        "note": "间隔检查；未提交新的远端任务",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "anchor 仍在有效计算，TEBD 尚未启动",
                "why": f"Python PID {anchor['driver_pid']} 与 Julia PID {anchor['julia_pid']} 仍存在，运行 {anchor['elapsed']}，CPU={anchor['cpu_percent']}%；stderr 为空。supervisor 最近日志为 {supervisor['last_log']}。",
            },
            {
                "kind": "table",
                "columns": ["对象", "观测", "决定"],
                "rows": [
                    ["L=80 CV anchor", f"Julia {anchor['julia_pid']}，{anchor['cpu_percent']}% CPU，运行 {anchor['elapsed']}", "继续等待终态"],
                    ["supervisor", "waiting_for_anchor；日志持续推进", "保留自动接续"],
                    ["TEBD", "not_started", "不绕过 supervisor 手动启动"],
                    ["本地并行", "CV 三频点图和 21/21 回归已完成", "继续只做离线分析"],
                ],
                "widths": ["23%", "47%", "30%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["下一状态事件", "anchor PID 消失且 supervisor 日志出现 TEBD 启动，或 anchor 终态文件出现"],
                    ["轮询纪律", "本次检查后不做短间隔重复轮询"],
                    ["范围", "0 <= alpha,beta <= 1；负 alpha 与 Fig. 9 排除"],
                ],
            },
            {
                "kind": "code",
                "title": "本轮快照",
                "text": "results/research_progress/server_progress_snapshot_20260803_1244.json\n远端：results/autoresearch_v5_20260802/round23_tebd_crosscheck/sequential_supervisor.log",
            },
            {
                "kind": "note",
                "label": "等待条件",
                "style": "pending",
                "text": "只有 anchor 终态后才回传并运行 validate_cv_run.py；通过后才进入 L=40 TEBD dt/dt2 交叉检查。",
            },
        ],
    }


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(0, build_section(snapshot))
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "section": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
