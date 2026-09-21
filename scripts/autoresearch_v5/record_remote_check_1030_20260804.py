# -*- coding: utf-8 -*-
"""记录 10:30 远端只读检查结果。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROGRESS = ROOT / "results/research_progress"
REPORT = PROGRESS / "report.json"
STATUS = PROGRESS / "qpi_cv_extension_remote_status_20260804_1030.json"
SNAPSHOT = PROGRESS / "qpi_cv_extension_remote_snapshot_20260804_1030.json"
TITLE = "2026-08-04 10:30 round31 CV anchor 只读检查"


def main() -> None:
    cells = {
        "cell-l40-qpi-low-000-020": {"status": "finished", "accepted": False, "manifest_present": True, "completed_points": 5, "max_points": 5, "returncode": 0},
        "cell-l40-qpi-high-055": {"status": "finished", "accepted": True, "manifest_present": True, "completed_points": 1, "max_points": 1, "returncode": 0},
        "cell-l40-qpi-high-100": {"status": "running", "phase": "julia_linsolve", "manifest_present": False, "completed_points": 0, "max_points": 1, "elapsed_seconds": 22921.284, "updated_at": "2026-08-04T02:31:50.905043+00:00"},
        "cell-l40-qpi-high-150": {"status": "not_started", "manifest_present": False},
    }
    snapshot = {
        "schema_version": 1,
        "checked_at": "2026-08-04T10:30:04+08:00",
        "target": "wangjieren@39.96.207.180:6000",
        "run_root": "/home/wangjieren/code/1x5_Heisenberg_Pentamer/results/autoresearch_v5_20260803/round31_qpi_cv_extension",
        "overall": {"phase": "omega_055_done", "completed_cells": 2, "total_cells": 4, "status": "running", "updated_at": "2026-08-03T20:09:49.546643+00:00"},
        "cells": cells,
        "resources": {"julia_processes": 2, "compute_threads_requested": 8, "supervisor_files": [], "active_cell": "cell-l40-qpi-high-100", "resource_utilization": "未读取 CPU/内存百分比；仅记录进程与线程配置"},
        "eta": {"status": "not_estimable", "reason": "high-100 仍在线性求解且无 manifest 终态；不以 high-055 成本外推，避免给出虚假 ETA"},
        "action": "只读；未写远端、未取消、未启动第二个 Julia、未回传未终态目录",
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    STATUS.write_text(json.dumps({"schema_version": 1, "status": "running", "remote_state": "observable_active_cell", **{key: snapshot[key] for key in ("checked_at", "target", "overall", "resources", "eta", "action", "scope")}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SNAPSHOT.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "按预定窗口执行的单次只读 SSH；没有写远端、取消任务、启动第二个 Julia 或回传未终态目录。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": "round31 仍运行中，不可交接", "why": "2/4 cells 已结束；high-100 仍处于 Julia linsolve、无 manifest，high-150 尚未开始。"},
            {"kind": "table", "columns": ["cell", "状态", "manifest", "处理"], "rows": [["low-000–020", "finished / rejected", "有", "保留 residual 失败证据"], ["high-055", "finished / accepted", "有", "可作为 accepted sparse anchor"], ["high-100", "running / linsolve", "无", "不回传、不启动并行任务"], ["high-150", "not started", "无", "等待顺序 supervisor"]]},
            {"kind": "kv", "pairs": [["远端资源", "2 个 Julia 相关进程；任务请求 8 threads；未读取 CPU/内存百分比"], ["ETA", "暂不可估计：high-100 无 manifest 终态，禁止用 high-055 成本线性外推"], ["快照", "results/research_progress/qpi_cv_extension_remote_snapshot_20260804_1030.json"], ["状态文件", "results/research_progress/qpi_cv_extension_remote_status_20260804_1030.json"]]},
            {"kind": "note", "label": "下一步", "style": "pending", "text": "等待 high-100 终态；只有 overall_progress 完成且远端 checksums 通过后，才按非覆盖回传→本地 checksum→validate_cv_run.py→accepted anchor 组装→CV–TEBD 分析顺序继续。"},
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · ROUND31 READ-ONLY CHECK"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "running", "completed_cells": 2, "total_cells": 4, "active_cell": "cell-l40-qpi-high-100", "eta": "not_estimable"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
