"""审计 CV cell 是否因程序结构而停滞。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "results/research_progress"
REPORT = REPORT_DIR / "report.json"
SNAPSHOT = REPORT_DIR / "qpi_cv_extension_status_20260803_2323.json"
JULIA = ROOT / "scripts/autoresearch_v5/cv_dsf_cell.jl"
WRAPPER = ROOT / "scripts/autoresearch_v5/run_cv_dsf_cell.py"
OUT = REPORT_DIR / "cv_program_static_audit_20260804.json"
TITLE = "2026-08-04 round31 CV 程序结构审计"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    julia_text = JULIA.read_text(encoding="utf-8")
    wrapper_text = WRAPPER.read_text(encoding="utf-8")
    evidence = {
        "single_julia_guard": "julia_processes" in snapshot and snapshot["julia_processes"] == 1,
        "progress_probe_present": "progress_probe" in wrapper_text and "progress.start()" in wrapper_text,
        "per_point_flush": "flush(file)" in julia_text and "flush(stdout)" in julia_text,
        "linsolve_iteration_cap": "maxiter=500" in julia_text,
        "residual_measured_after_solve": julia_text.index("relative_residual(solution") > julia_text.index("linsolve("),
        "acceptance_post_run": "acceptance_checks" in wrapper_text and "max_cv_residual" in wrapper_text,
    }
    result = {
        "schema_version": 1,
        "created_at": "2026-08-04",
        "status": "ACTIVE_COMPUTE_NOT_STUCK_BUT_RESIDUAL_GATE_NOT_ADAPTIVE" if all(evidence.values()) else "REVIEW_REQUIRED",
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
        "remote_evidence": {
            "checked_at": snapshot["checked_at"],
            "phase": snapshot["phase"],
            "completed_points": snapshot["completed_points"],
            "total_points": snapshot["total_points"],
            "julia_processes": snapshot["julia_processes"],
            "first_point_residual": snapshot["first_point"]["residual"],
            "residual_gate": snapshot["acceptance"]["residual_gate"],
        },
        "evidence": evidence,
        "interpretation": "现有证据支持任务仍在 Julia linsolve 阶段，并非 wrapper 失去进程；但 residual 只在每点求解后记录、在 cell 结束时验收，没有自适应增加 maxdim 或重试机制，因此首点 residual 超门槛会使最终 cell 失败而不是立即修正。",
        "decision": "不修改正在运行的远端任务；终态回传后若 cell 失败，单独设计带残差重试的下一批，不降低 1e-5 门槛。",
        "source_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in [SNAPSHOT, JULIA, WRAPPER]},
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "基于最后可信远端快照和已上传源码的静态审计；不连接服务器，不修改运行任务。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": "不是进程卡死；残差门缺少自适应重试", "why": "快照仍显示 1 个 Julia、低频 cell 1/5；源码有逐点 progress/flush 和 linsolve maxiter=500，但 residual 只在求解后记录并在 cell 结束时验收。"},
            {"kind": "table", "columns": ["检查项", "结果", "含义"], "rows": [["进程状态", "Julia=1；phase=julia_linsolve", "不启动第二个 Julia"], ["进度记录", "progress_probe + 每点 flush", "程序仍能报告进度"], ["首点 residual", f"{snapshot['first_point']['residual']:.3e} > 1e-5", "可能导致最终 cell fail，不等于卡死"], ["重试机制", "未发现自适应 maxdim/重试", "终态后再决定是否修复"]], "widths": ["24%", "30%", "46%"]},
            {"kind": "kv", "pairs": [["审计文件", "results/research_progress/cv_program_static_audit_20260804.json"], ["决策", result["decision"]], ["范围", "0 <= alpha,beta <= 1；排除负 alpha 与 Fig. 9"]]},
            {"kind": "note", "label": "保护规则", "style": "pending", "text": "在 round31 终态可读之前不修改远端代码、不取消任务、不降低 residual 门槛；若失败，先保留原始目录再提交独立重试。"},
        ],
    }
    report["sections"] = [item for item in report["sections"] if item["title"] != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · CV PROGRAM AUDIT"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "evidence": evidence}, ensure_ascii=False))


if __name__ == "__main__":
    main()
