"""诊断低频 CV residual 失败，区分程序错误与数值收敛不足。"""

from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CELL = ROOT / "results/autoresearch_v5_20260803/round31_qpi_cv_extension_completed_cells_20260804/cell-l40-qpi-low-000-020"
PROPOSAL = ROOT / "results/research_progress/qpi_cv_residual_retry_proposal_20260804.json"
REPORT = ROOT / "results/research_progress/report.json"
OUTPUT = ROOT / "results/research_progress/qpi_cv_low_residual_diagnosis_20260804.json"
TITLE = "2026-08-04 低频 CV residual 失败原因诊断"


def metric_rows() -> dict[str, float]:
    with (CELL / "metrics.csv").open(encoding="utf-8", newline="") as handle:
        values: dict[str, float] = {}
        for row in csv.DictReader(handle):
            try:
                values[row["metric"]] = float(row["value"])
            except ValueError:
                continue
        return values


def main() -> None:
    manifest = json.loads((CELL / "manifest.json").read_text(encoding="utf-8"))
    proposal = json.loads(PROPOSAL.read_text(encoding="utf-8"))
    metrics = metric_rows()
    points = []
    with (CELL / "spectrum.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            points.append({"omega": float(row["omega"]), "residual": float(row["relative_residual"]), "intensity": float(row["intensity"]), "solution_maxdim": int(row["solution_maxdim"])})
    failures = [point for point in points if point["residual"] > 1e-5]
    checks = {
        "returncode_zero": manifest.get("returncode") == 0,
        "stderr_empty": (CELL / "stderr.log").read_text(encoding="utf-8", errors="replace").strip() == "",
        "dmrg_variance_pass": metrics["variance_per_site"] <= 1e-8,
        "dmrg_truncation_pass": metrics["max_dmrg_truncation"] <= 1e-8,
        "spectrum_nonnegative": manifest.get("acceptance", {}).get("checks", {}).get("nonnegative") is True,
        "low_frequency_failures": len(failures) == 3 and [point["omega"] for point in failures] == [0.0, 0.05, 0.1],
        "residual_decreases_with_omega": all(points[index]["residual"] > points[index + 1]["residual"] for index in range(len(points) - 1)),
    }
    result = {
        "schema_version": 1,
        "checked_at": "2026-08-04T09:25:00+08:00",
        "status": "numerical_convergence_limited" if all(checks.values()) else "needs_manual_review",
        "cell": str(CELL.relative_to(ROOT)).replace("\\", "/"),
        "points": points,
        "failures": failures,
        "checks": checks,
        "baseline": proposal["baseline"],
        "proposed_retry": proposal["proposed_changes"],
        "interpretation": "程序正常结束且 DMRG/非负性通过；失败集中在低频并随 omega 升高改善，支持‘CV 线性求解收敛预算不足’诊断，不支持‘程序崩溃’诊断。",
        "safety": proposal["safety"],
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "只分析已回传失败 cell；不修改 round31、不降低 residual 门槛、不启动 retry。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": "更像数值收敛不足，不是程序崩溃", "why": "returncode=0、stderr 为空、DMRG 与非负性通过；3 个低频点 residual 超门并随 omega 升高下降。"},
            {"kind": "table", "columns": ["omega", "residual", "解向量维度", "状态"], "rows": [[f"{point['omega']:.2f}", f"{point['residual']:.3e}", str(point['solution_maxdim']), "失败" if point in failures else "通过"] for point in points], "widths": ["20%", "30%", "25%", "25%"]},
            {"kind": "kv", "pairs": [["诊断 JSON", "results/research_progress/qpi_cv_low_residual_diagnosis_20260804.json"], ["建议 retry", "新目录；dmrg_maxdim=320、cv_maxdim=800、nsweeps=20；先 omega=0.05 smoke"], ["保护", "保留原失败目录；不降低 1e-5 residual 门槛；单 Julia 顺序执行"]]},
            {"kind": "note", "label": "当前动作", "style": "pending", "text": "retry 仍只作为 proposal；等待 round31 全局终态和服务器恢复后再决定是否执行。"},
        ],
    }
    report["sections"] = [entry for entry in report["sections"] if entry.get("title") != TITLE]
    report["sections"].insert(5, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · LOW-FREQUENCY RESIDUAL DIAGNOSIS"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "failed_omegas": [point["omega"] for point in failures], "checks": checks}, ensure_ascii=False))
    if result["status"] != "numerical_convergence_limited":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
