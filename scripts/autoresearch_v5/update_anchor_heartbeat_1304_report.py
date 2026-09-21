"""把 13:04 anchor 心跳追加到离线研究报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SNAPSHOT = ROOT / "results/research_progress/server_progress_snapshot_20260803_1304.json"
TITLE = "2026-08-03 13:04 anchor 状态复核"


def build_section(snapshot: dict[str, object]) -> dict[str, object]:
    anchor = snapshot["anchor"]
    supervisor = snapshot["supervisor"]
    return {
        "title": TITLE,
        "note": "间隔状态检查；未启动新计算",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "anchor 仍运行，TEBD 继续等待",
                "why": f"Julia PID {anchor['julia_pid']} 运行 {anchor['elapsed']}、CPU={anchor['cpu_percent']}%；anchor status.json 仍为 running，stderr 为空。supervisor 最新日志为 {supervisor['last_log']}。",
            },
            {
                "kind": "table",
                "columns": ["对象", "本轮观测", "处理"],
                "rows": [
                    ["L=80 CV anchor", "driver 3745209 / Julia 3745217；16:10:01；1620% CPU", "继续等待终态"],
                    ["supervisor", "PID 3862840；每分钟写入 anchor still running", "保留自动接续"],
                    ["TEBD", "status.json 尚不存在", "不手动绕过 supervisor"],
                    ["本地任务", "21/21 回归、CV recheck 和高误差诊断均完成", "不新增远端 Julia"],
                ],
                "widths": ["23%", "47%", "30%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["下一状态事件", "anchor status.json 变为 success/failed，或 anchor PID 消失并出现 TEBD status.json"],
                    ["终态动作", "回传独立目录 -> validate_cv_run.py -> checksum -> TEBD 交叉验收"],
                    ["范围", "0 <= alpha,beta <= 1；负 alpha 与 Fig. 9 排除"],
                ],
            },
            {
                "kind": "code",
                "title": "本轮快照",
                "text": "results/research_progress/server_progress_snapshot_20260803_1304.json\n远端：results/autoresearch_v5_20260802/round22_cv_l80_anchor/cell-0003-L80-qpi-w025/status.json\n远端：results/autoresearch_v5_20260802/round23_tebd_crosscheck/sequential_supervisor.log",
            },
            {
                "kind": "note",
                "label": "轮询纪律",
                "style": "pending",
                "text": "本次记录后不做短间隔重复 SSH；等待终态文件或 supervisor 日志出现 TEBD 启动事件。",
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
