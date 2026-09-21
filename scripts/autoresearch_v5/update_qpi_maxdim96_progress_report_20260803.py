"""把 maxdim=96 的远端进度快照追加到 HTML 报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SNAPSHOT = ROOT / "results/research_progress/qpi_tebd_maxdim96_progress_20260803_2141.json"
TITLE = "2026-08-03 21:41 maxdim=96 进度快照"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    proc = snapshot["processes"]
    section = {
        "title": TITLE,
        "note": "一次只读检查；不启动第二个 Julia。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "运行健康，完成度 10%",
                "why": "progress.json 持续更新，TEBD 已完成 240/2400 步；ETA 约 12.1 分钟，尚无终态谱验收。",
            },
            {
                "kind": "table",
                "columns": ["量", "值", "解释"],
                "rows": [
                    ["阶段", f"{snapshot['phase']} / {snapshot['status']}", "严格 q=pi，dt=0.0125，tmax=30"],
                    ["进度", f"{snapshot['completed_steps']}/{snapshot['total_steps']} ({snapshot['percent']:.1f}%)", "TEBD 时间步"],
                    ["耗时", f"{snapshot['elapsed_seconds']:.1f} s", "远端 progress.json"],
                    ["ETA", f"{snapshot['eta_seconds'] / 60:.1f} min", "运行时估计；不替代终态证据"],
                    ["进程", f"supervisor={proc['supervisor_pid']}；Julia={proc['julia_pid']}", f"Julia 数量={proc['julia_count']}，保持单任务"],
                ],
                "widths": ["18%", "32%", "50%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["快照证据", "results/research_progress/qpi_tebd_maxdim96_progress_20260803_2141.json"],
                    ["远端 cell", snapshot["cell_id"]],
                    ["范围", "0<=alpha,beta<=1；负 alpha 与 Fig. 9 排除"],
                ],
            },
            {
                "kind": "note",
                "label": "下一状态事件",
                "style": "pending",
                "text": "等待 manifest/status.json 进入 success 或 failed；成功后回传并比较 maxdim=96 与基准 maxdim=320，再更新 Fig. 6–8 对应动力学图。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item["title"] != TITLE]
    report["sections"].insert(0, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 21:41 CST"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"section": TITLE, "percent": snapshot["percent"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
