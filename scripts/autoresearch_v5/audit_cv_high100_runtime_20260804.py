# -*- coding: utf-8 -*-
"""审计 high-100 长时运行的代码预算与心跳证据。"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROGRESS = ROOT / "results/research_progress"
CODE = ROOT / "scripts/autoresearch_v5/cv_dsf_cell.jl"
RUNNER = ROOT / "scripts/autoresearch_v5/run_cv_dsf_cell.py"
SNAPSHOT = PROGRESS / "qpi_cv_extension_remote_snapshot_20260804_1030.json"
OUT = PROGRESS / "cv_high100_runtime_diagnosis_20260804.json"
REPORT = PROGRESS / "report.json"
TITLE = "2026-08-04 high-100 长时运行代码级诊断"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    code = CODE.read_text(encoding="utf-8")
    runner = RUNNER.read_text(encoding="utf-8")
    remote = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    active = remote["cells"]["cell-l40-qpi-high-100"]
    checks = {
        "linsolve_maxiter_present": bool(re.search(r"maxiter\s*=\s*500", code)),
        "krylovdim_present": bool(re.search(r"krylovdim\s*=\s*100", code)),
        "per_point_stdout_flush": "flush(stdout)" in code,
        "spectrum_csv_flush": "flush(file)" in code,
        "progress_heartbeat_wrapper": "ProgressWriter" in runner and "progress_probe" in runner,
        "active_process_recorded": active.get("status") == "running" and active.get("manifest_present") is False,
    }
    result = {
        "schema_version": 1,
        "created_at": "2026-08-04T10:50:00+08:00",
        "status": "active_compute_not_stuck" if all(checks.values()) else "needs_review",
        "cell": "cell-l40-qpi-high-100",
        "remote_evidence": {"status": active.get("status"), "phase": active.get("phase"), "elapsed_seconds": active.get("elapsed_seconds"), "updated_at": active.get("updated_at"), "manifest_present": active.get("manifest_present")},
        "code_budget": {"linsolve_maxiter": 500, "krylovdim": 100, "hard_timeout_present": False, "progress_flush_per_point": True},
        "checks": checks,
        "interpretation": "当前证据支持‘困难线性求解仍在运行’，不支持程序已崩溃；代码没有硬超时，因此若后续 heartbeat 长时间不变，需人工按证据决定是否终止，不能自动启动第二个 Julia。",
        "source_sha256": {path.relative_to(ROOT).as_posix(): sha256(path) for path in (CODE, RUNNER, SNAPSHOT)},
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "只审计本地代码和上次只读快照；不连接服务器、不修改运行中的 Julia。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": "活动计算，尚无硬超时", "why": "代码含 linsolve maxiter=500、krylovdim=100、逐点 stdout flush 和 wrapper heartbeat；high-100 仍有运行进程但无 manifest。"},
            {"kind": "table", "columns": ["证据", "结果", "含义"], "rows": [["Julia linsolve", "maxiter=500；krylovdim=100", "有迭代预算"], ["逐点进度", "stdout/file flush", "可由 heartbeat 观察"], ["硬超时", "未设置", "可能长时间运行，不能给虚假 ETA"], ["远端状态", "running；manifest=false", "当前不回传、不并行"]]},
            {"kind": "kv", "pairs": [["诊断 JSON", "results/research_progress/cv_high100_runtime_diagnosis_20260804.json"], ["下一检查规则", "仅在后续 heartbeat 长时间不变时人工复核；不自动取消或启动第二个 Julia"], ["范围", "0 <= alpha,beta <= 1；排除负 alpha 和 Fig.9"]]},
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(3, section)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "all_checks": all(checks.values()), "hard_timeout": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
