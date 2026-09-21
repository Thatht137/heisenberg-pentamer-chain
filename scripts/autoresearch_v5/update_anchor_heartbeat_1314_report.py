"""把 13:14 的服务器状态追加到离线研究报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SNAPSHOT = ROOT / "results/research_progress/server_progress_snapshot_20260803_1314.json"
TITLE = "2026-08-03 13:14 资源占用与 anchor 进度复核"


def build_section(snapshot: dict[str, object]) -> dict[str, object]:
    anchor = snapshot["anchor"]
    server = snapshot["server"]
    supervisor = snapshot["supervisor"]
    return {
        "title": TITLE,
        "note": "一次性只读检查；未提交新的远端任务",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "anchor 仍在计算，TEBD 继续等待",
                "why": f"Julia PID {anchor['julia_pid']} 已运行 {anchor['elapsed']}，CPU={anchor['cpu_percent']}%（约 16.2 核），stderr 为空；尚未生成频点文件，因此不把运行中状态当作结果。",
            },
            {
                "kind": "table",
                "columns": ["对象", "本轮观测", "决定"],
                "rows": [
                    ["服务器", f"{server['cpu_cores']} 核；可用内存 {server['memory_available_gib']} / {server['memory_total_gib']} GiB；负载 {server['load_average']}", "内存不是瓶颈"],
                    ["L=80 CV anchor", f"driver {anchor['driver_pid']} / Julia {anchor['julia_pid']}；已完成频点 {anchor['points_completed']}；已有基态和动量源", "保持单任务"],
                    ["TEBD supervisor", "waiting_for_anchor；TEBD status.json 不存在", "不手动绕过"],
                    ["空闲核", "约 64 核未由 anchor 使用", "不启动额外 Julia，避免 supervisor 放弃自动接续"],
                    ["本机逻辑检查", "21/21 回归；compileall 无错误；完整性 0 失败", "继续离线分析和报告"],
                ],
                "widths": ["23%", "49%", "28%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["下一状态事件", "anchor status.json 变为 success/failed，或 anchor PID 消失并出现 TEBD status.json"],
                    ["终态动作", "独立回传 -> 远端和本地 checksum -> validate_cv_run.py -> TEBD dt/dt2 交叉验收"],
                    ["预计时间", "以先验 L=80 单点约 11.84 h 和当前持续 CPU 为依据：较可能还需 0–8 h，保守还需 0–12 h；不把线性外推当作承诺"],
                    ["范围", "0 <= alpha,beta <= 1；负 alpha 与 Fig. 9 排除"],
                ],
            },
            {
                "kind": "code",
                "title": "本轮证据",
                "text": "results/research_progress/server_progress_snapshot_20260803_1314.json\n远端：round22_cv_l80_anchor/cell-0003-L80-qpi-w025/{ground_state.jld2,source_state.jld2}\n远端：round23_tebd_crosscheck/sequential_supervisor.log",
            },
            {
                "kind": "note",
                "label": "轮询纪律",
                "style": "pending",
                "text": "本次检查后不做短间隔重复 SSH；等待终态文件或 supervisor 出现 TEBD 启动事件。",
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
