"""根据已有低频日志估算 retry smoke 成本并登记执行门。"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPECTRUM = ROOT / "results/autoresearch_v5_20260803/round31_qpi_cv_extension_completed_cells_20260804/cell-l40-qpi-low-000-020/spectrum.csv"
PROPOSAL = ROOT / "results/research_progress/qpi_cv_residual_retry_proposal_20260804.json"
REPORT = ROOT / "results/research_progress/report.json"
OUTPUT = ROOT / "results/research_progress/qpi_cv_retry_smoke_plan_20260804.json"
TITLE = "2026-08-04 低频 CV retry smoke 成本与执行计划"


def main() -> None:
    proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    rows = []
    with SPECTRUM.open(encoding="utf-8", newline="") as handle:
        rows = [{"omega": float(row["omega"]), "solve_seconds": float(row["solve_seconds"]), "residual": float(row["relative_residual"]), "solution_maxdim": int(row["solution_maxdim"])} for row in csv.DictReader(handle)]
    smoke = next(row for row in rows if abs(row["omega"] - 0.05) < 1e-12)
    result = {
        "schema_version": 1,
        "checked_at": "2026-08-04T09:30:00+08:00",
        "status": "plan_only_not_started",
        "baseline_smoke": smoke,
        "baseline_five_point_wall_minutes": sum(row["solve_seconds"] for row in rows) / 60.0,
        "proposed_parameters": proposal["proposed_changes"],
        "estimated_smoke_wall_time": {"lower_minutes": 20, "upper_minutes": 60, "basis": "baseline omega=0.05 solve=15.24 min; proposed maxdim/sweep increase makes exact time hardware- and convergence-dependent"},
        "required_preflight": ["round31 全局终态已确认", "远端 checksum 预检通过", "目标新目录不存在", "单 Julia/8 threads 资源可用", "不覆盖 round31 失败目录"],
        "acceptance": ["max_cv_residual <= 1e-5", "variance_per_site <= 1e-8", "max_dmrg_truncation <= 1e-8", "谱非负", "manifest/checksum/validator 全通过"],
        "stop_rules": ["smoke 仍 residual 失败则不扩展到 0.00--0.20", "不降低任何门槛", "不在服务器不可观测时启动"],
        "scope": {"alpha": 0.23, "beta": 0.5, "L": 40, "q_over_pi": 1.0, "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "只根据已有低频日志制定 smoke 计划；当前不启动服务器任务。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": "retry smoke 已准备，尚未启动", "why": f"omega=0.05 基线 solve 约 {smoke['solve_seconds'] / 60:.1f} 分钟；提议参数提高 CV maxdim 和 sweeps，预计约 20–60 分钟，实际以服务器日志为准。"},
            {"kind": "table", "columns": ["项目", "基线", "retry smoke", "门槛"], "rows": [["CV maxdim", "600", str(proposal["proposed_changes"]["cv_maxdim"]), "不变 residual <=1e-5"], ["DMRG maxdim", "256", str(proposal["proposed_changes"]["dmrg_maxdim"]), "variance/truncation 不变"], ["sweeps", "16", str(proposal["proposed_changes"]["nsweeps"]), "单点 omega=0.05"], ["预计墙钟", f"{smoke['solve_seconds'] / 60:.1f} min", "20–60 min（估计）", "先 smoke 后决定"]], "widths": ["25%", "20%", "25%", "30%"]},
            {"kind": "list", "title": "启动前必须满足", "items": result["required_preflight"]},
            {"kind": "kv", "pairs": [["计划 JSON", "results/research_progress/qpi_cv_retry_smoke_plan_20260804.json"], ["当前状态", "plan_only_not_started"], ["失败策略", "smoke 失败则保持 low cell 隔离，不扩展、不降门槛"]]},
        ],
    }
    report["sections"] = [entry for entry in report["sections"] if entry.get("title") != TITLE]
    report["sections"].insert(3, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · CV RETRY SMOKE PLAN"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "baseline_minutes": smoke["solve_seconds"] / 60.0, "estimated": result["estimated_smoke_wall_time"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
