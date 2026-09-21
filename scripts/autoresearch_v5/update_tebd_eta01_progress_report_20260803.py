"""把 TEBD eta=0.1 定时进度写入研究报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SNAPSHOT = ROOT / "results/research_progress/tebd_eta01_progress_20260803_1723.json"
TITLE = "2026-08-03 17:23 TEBD eta=0.1 进度检查"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    progress = snapshot["progress"]
    process = snapshot["julia_processes"][0]
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(
        0,
        {
            "title": TITLE,
            "note": "一次只读事件检查；coarse 仍运行，不启动第二个 Julia",
            "blocks": [
                {
                    "kind": "verdict",
                    "status": "warn",
                    "label": "L=80 anchor 已闭环，TEBD coarse 正常运行",
                    "why": "anchor 已独立回传并通过 checksum、manifest 与 validate_cv_run.py 的 8/8 检查；当前 supervisor=running、phase=coarse，尚无终态结果。",
                },
                {
                    "kind": "table",
                    "columns": ["检查项", "快照", "判断"],
                    "rows": [
                        ["TEBD 进度", f"{progress['completed_steps']}/{progress['total_steps']}（{progress['percent']:.1f}%）", "运行中，不作物理验收"],
                        ["进度 ETA", f"{progress['eta_seconds'] / 60:.1f} 分钟", "启动初期估计，低置信度"],
                        ["Julia 占用", f"PID {process['pid']}；CPU={process['cpu_percent']:.0f}%；RSS={process['rss_kib'] / 1024**2:.2f} GiB", "仅 1 个 Julia，8 threads"],
                        ["supervisor", "running / coarse", "等待 coarse 终态后自动决定 refined"],
                    ],
                    "widths": ["24%", "38%", "38%"],
                },
                {
                    "kind": "kv",
                    "pairs": [
                        ["参数", "alpha=0.23、beta=0.5、L=40、dt=0.025、tmax=30、eta=0.1"],
                        ["时间窗", "exponential；tau=1/eta=10=tmax/3"],
                        ["执行约束", "coarse 通过后才由 supervisor 启动 dt=0.0125 refined；当前不手动接续"],
                        ["范围", "0 <= alpha,beta <= 1；负 alpha 与 Fig. 9 排除"],
                    ],
                },
                {
                    "kind": "code",
                    "title": "检查证据",
                    "text": "results/research_progress/tebd_eta01_progress_20260803_1723.json\n远端：round24_tebd_eta01_crosscheck/overall_status.json\n远端：cell-alpha023-dt025-t30/progress.json\n远端：scripts/staging_20260803_eta/tebd_eta01_supervisor.log",
                },
                {
                    "kind": "note",
                    "label": "下一触发点",
                    "style": "pending",
                    "text": "等待 coarse terminal status。若失败，先校验并回传完整失败证据；若通过，只确认 refined 已由 supervisor 自动启动。两阶段都完成后才做远端 checksum、本地独立 checksum、dt/dt2 和 CV/TEBD 验收。",
                },
            ],
        },
    )
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 17:23 CST"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"section": TITLE, "status": snapshot["supervisor"]["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
