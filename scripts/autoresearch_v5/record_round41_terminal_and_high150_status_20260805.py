#!/usr/bin/env python3
"""记录 round41 终态验收与 high-150 条件 ETA。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results/research_progress"
CELL = ROOT / "results/autoresearch_v5_20260805/round41_qpi_cv_low005_fetch"
VALIDATOR = RUN / "round41_qpi_cv_low005_validator_20260805.json"
REPORT = RUN / "report.json"
SCHEDULE = RUN / "automation_schedule_20260804.json"
TITLE = "2026-08-05 round41 终态验收与 high-150 进展"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    validator = json.loads(VALIDATOR.read_text(encoding="utf-8"))
    manifest = json.loads((CELL / "manifest.json").read_text(encoding="utf-8"))
    files = sorted(path for path in CELL.iterdir() if path.is_file())
    receipt = {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "pass",
        "non_clobbering": True,
        "remote_checksum": "pass",
        "local_checksum": "pass",
        "local_dir": CELL.relative_to(ROOT).as_posix(),
        "files": [{"path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)} for path in files],
    }
    (RUN / "round41_qpi_cv_low005_fetch_receipt_20260805.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    assessment = {
        "schema_version": 1,
        "status": "rejected_residual",
        "accepted_only_action": "excluded",
        "cv_tebd_action": "remain_not_evaluable_six_points",
        "diagnostics": manifest["diagnostics"],
        "acceptance": manifest["acceptance"],
        "validator": validator,
        "stop_rule": "不降低 residual 门槛，不扩展 0--0.20，不自动重试 omega=0.05。",
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    (RUN / "round41_qpi_cv_low005_terminal_assessment_20260805.json").write_text(
        json.dumps(assessment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    high150 = {
        "schema_version": 1,
        "checked_at": "2026-08-05T07:42:29+08:00",
        "status": "running",
        "phase": "julia_linsolve",
        "elapsed_seconds": 59672.412,
        "cpu_percent": 1609.0,
        "rss_bytes": 3881492 * 1024,
        "completed_points": 0,
        "total_points": 1,
        "stderr_bytes": 0,
        "next_check": "2026-08-05T15:07:00+08:00",
        "eta": "无可靠终点预测；15:07 达到 24 h 人工复核边界。",
    }
    (RUN / "round31_high150_status_20260805_0742.json").write_text(
        json.dumps(high150, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if SCHEDULE.is_file():
        schedule = json.loads(SCHEDULE.read_text(encoding="utf-8"))
        existing_effective = schedule.get("latest_update", {}).get("automation_effective", False)
        schedule["latest_update"] = {
            "round41": "terminal_rejected_residual",
            "high150": "running",
            "high150_next_read": "2026-08-05T15:07:00+08:00",
            "automation_effective": existing_effective,
        }
        SCHEDULE.write_text(json.dumps(schedule, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "round41 已远端 checksum、非覆盖回传、本地 checksum 和 validator；high-150 为一次性只读状态。",
        "blocks": [
            {"kind": "verdict", "status": "bad", "label": "round41 程序成功，但数值验收失败", "why": "omega=0.05 residual=1.17068e-5，仍高于 1e-5；方差、截断、非负性和 checksum 全通过。"},
            {"kind": "table", "columns": ["验收项", "结果", "处理"], "rows": [
                ["远端/本地 checksum", "通过", "保留审计数据"],
                ["variance per site", "2.612e-10", "通过"],
                ["DMRG truncation", "9.996e-11", "通过"],
                ["CV residual", "1.17068e-5", "失败"],
                ["accepted-only", "排除", "不改变六点锚点表"],
                ["CV--TEBD", "NotEvaluable", "不升级"],
            ]},
            {"kind": "verdict", "status": "warn", "label": "high-150 仍在有效计算", "why": "07:42 时 elapsed=16.58 h、CPU≈16 核、RSS≈3.70 GiB、stderr 为空；0/1 点，阶段为 julia_linsolve。"},
            {"kind": "note", "label": "下一读取", "style": "pending", "text": "北京时间 8 月 5 日 15:07 达到 24 h 复核边界。此前不轮询、不启动新 Julia；届时若仍运行，只做资源诊断并由作者决定继续或停止。"},
            {"kind": "kv", "pairs": [
                ["round41 validator", "results/research_progress/round41_qpi_cv_low005_validator_20260805.json"],
                ["回传 receipt", "results/research_progress/round41_qpi_cv_low005_fetch_receipt_20260805.json"],
                ["终态评估", "results/research_progress/round41_qpi_cv_low005_terminal_assessment_20260805.json"],
                ["high-150 状态", "results/research_progress/round31_high150_status_20260805_0742.json"],
            ]},
        ],
    }
    report["sections"] = [section] + [item for item in report["sections"] if item.get("title") != TITLE]
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-05 · ROUND41 REJECTED · HIGH150 RUNNING"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"round41": "rejected_residual", "high150": "running", "next_check": high150["next_check"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
