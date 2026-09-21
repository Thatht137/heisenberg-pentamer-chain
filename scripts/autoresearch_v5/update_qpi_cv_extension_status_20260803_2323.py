"""把一次 q=pi CV 进度检查写入报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
REPORT_DIR = REPORT.parent
TITLE = "2026-08-03 23:23 q=pi CV 扩展进度复核"


def main() -> None:
    snapshot = {
        "checked_at": "2026-08-03T23:23:46+08:00",
        "run": "round31_qpi_cv_extension/cell-l40-qpi-low-000-020",
        "status": "running",
        "phase": "julia_linsolve",
        "completed_points": 1,
        "total_points": 5,
        "progress_updated_at": "2026-08-03T15:23:25.566260+00:00",
        "julia_processes": 1,
        "threads": 8,
        "cores": 80,
        "available_memory_gib": 227,
        "manifest_present": False,
        "first_point": {"omega": 0.0, "residual": 1.324e-5, "solution_maxdim": 200},
        "acceptance": {"residual_gate": 1e-5, "first_point_pass": False, "cell_final": False},
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    (REPORT_DIR / "qpi_cv_extension_status_20260803_2323.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "一次只读检查；没有启动第二个 Julia，也没有修改远端任务。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "CV 仍在有效计算，暂不回传",
                "why": "低频 cell 已完成 1/5 个频点，当前处于 Julia correction-vector linsolve；没有 manifest 终态，不能做物理验收。",
            },
            {
                "kind": "table",
                "columns": ["检查项", "当前观测", "处理"],
                "rows": [
                    ["cell 进度", "1/5；omega=0.00--0.20，步长 0.05", "继续等待自然终止"],
                    ["首点 residual", "1.324e-5；门槛 1e-5", "保留为未通过证据，不放宽门槛"],
                    ["进程", "Julia=1；threads=8；phase=julia_linsolve", "不启动第二个 Julia"],
                    ["资源", "80 核；available memory≈227 GiB", "资源不是瓶颈"],
                    ["终态文件", "manifest.json 尚不存在", "不下载、不运行 validator"],
                ],
                "widths": ["22%", "43%", "35%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["远端 cell", "results/autoresearch_v5_20260803/round31_qpi_cv_extension/cell-l40-qpi-low-000-020"],
                    ["本地快照", "results/research_progress/qpi_cv_extension_status_20260803_2323.json"],
                    ["终态顺序", "远端 checksum -> 独立回传 -> 本地 checksum -> validate_cv_run.py -> assemble_qpi_cv_anchors.py"],
                ],
            },
            {
                "kind": "note",
                "label": "下一状态事件",
                "style": "pending",
                "text": "等待 manifest/status 终态或 launcher 进入下一 cell；不做短间隔轮询。若最终 residual 超门槛，保留失败目录并另建提高 cv_maxdim/精度的独立重算目录。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(0, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 · QPI CV EXTENSION MONITOR"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": snapshot["status"], "progress": "1/5"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
