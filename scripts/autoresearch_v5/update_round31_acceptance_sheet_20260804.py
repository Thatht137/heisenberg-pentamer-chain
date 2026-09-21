"""把 round31 q=pi CV 顺序任务的恢复后验收表写入 HTML。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
REPORT_DIR = REPORT.parent
TITLE = "2026-08-04 round31 q=pi CV 顺序任务恢复后验收表"


def main() -> None:
    cells = [
        ("cell-l40-qpi-low-000-020", "0.00, 0.05, 0.10, 0.15, 0.20", "低频主峰覆盖", "1"),
        ("cell-l40-qpi-high-055", "0.55", "低频尾部与权重连接", "2"),
        ("cell-l40-qpi-high-100", "1.00", "主要积分窗中段", "3"),
        ("cell-l40-qpi-high-150", "1.50", "积分窗上边界", "4"),
    ]
    snapshot = {
        "schema_version": 1,
        "created_at": "2026-08-04T00:28:49+08:00",
        "run_root": "results/autoresearch_v5_20260803/round31_qpi_cv_extension",
        "status": "ready_for_recovery_check",
        "cells": [
            {"cell_id": cell, "omega": omega, "purpose": purpose, "order": int(order)}
            for cell, omega, purpose, order in cells
        ],
        "gates": {
            "positive_region": "0 <= alpha,beta <= 1",
            "cv_residual": "<= 1e-5",
            "variance_per_site": "<= 1e-8",
            "max_dmrg_truncation": "<= 1e-8",
            "nonnegative_spectrum": True,
            "checksums": True,
        },
        "handoff_order": [
            "read overall_progress/status/progress/manifest",
            "remote sha256sum -c checksums.sha256",
            "non-clobber fetch to a new local directory",
            "local checksum and validate_cv_run.py",
            "assemble_qpi_cv_anchors.py",
            "analyze_cv_tebd_crosscheck.py",
        ],
        "failure_policy": "residual or checksum failure stays isolated; do not lower thresholds or overwrite a prior run",
        "scope": {"negative_alpha_excluded": True, "fig9_excluded": True},
    }
    output = REPORT_DIR / "round31_acceptance_sheet_20260804.json"
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "服务器恢复后只读读取并按顺序执行；不改变已启动任务，不降低验收门槛。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "恢复后动作表已就绪",
                "why": "低频 cell 先覆盖 omega≈0.05 主峰，再由 0.55/1.00/1.50 补齐 [0,1.5] 主要积分窗。",
            },
            {
                "kind": "table",
                "columns": ["顺序", "cell", "频率/目的", "通过条件"],
                "rows": [[order, cell, f"{omega}；{purpose}", "终态 + checksum + residual <= 1e-5"] for cell, omega, purpose, order in cells],
                "widths": ["10%", "30%", "34%", "26%"],
            },
            {
                "kind": "list",
                "title": "固定交接顺序",
                "items": [
                    "读取 overall_progress、status、progress、manifest，确认 success/failed 终态",
                    "远端 sha256sum -c checksums.sha256",
                    "新目录非覆盖回传，再做本地 checksum",
                    "validate_cv_run.py -> assemble_qpi_cv_anchors.py -> CV/TEBD 分析",
                ],
            },
            {
                "kind": "note",
                "label": "失败分支",
                "style": "pending",
                "text": "任一 cell residual、方差、截断、非负性或 checksum 失败时，隔离该目录并保留证据；不降低门槛、不覆盖旧结果、不扩展负 alpha 或 Fig. 9。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · ROUND31 ACCEPTANCE SHEET"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": snapshot["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
