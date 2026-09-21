"""登记 round31 失败后的安全 CV 重试方案，不执行远端任务。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "results/research_progress"
REPORT = REPORT_DIR / "report.json"
OUT = REPORT_DIR / "qpi_cv_residual_retry_proposal_20260804.json"
TITLE = "2026-08-04 round31 CV 残差失败后的安全重试方案"


def main() -> None:
    result = {
        "schema_version": 1,
        "created_at": "2026-08-04",
        "status": "PROPOSAL_ONLY_NOT_STARTED",
        "trigger": "仅当 round31 单 cell 终态 manifest 明确 acceptance.status=fail 且 residual 超过 1e-5 时触发",
        "scope": {"alpha": 0.23, "beta": 0.5, "L": 40, "q_over_pi": 1.0, "negative_alpha_excluded": True, "fig9_excluded": True},
        "baseline": {"dmrg_maxdim": 256, "cv_maxdim": 600, "nsweeps": 16, "cutoff": 1e-10, "cv_cutoff": 1e-14, "max_cv_residual": 1e-5, "threads": 8},
        "proposed_changes": {"dmrg_maxdim": 320, "cv_maxdim": 800, "nsweeps": 20, "cutoff": 1e-10, "cv_cutoff": 1e-14, "max_cv_residual": 1e-5, "threads": 8},
        "safety": ["新 run 目录，禁止覆盖 round31", "先做单点 omega=0.05 smoke，再决定是否扩展", "仍保持四个 cell 顺序和单 Julia", "保留原始失败目录和 checksum", "不降低 residual、方差、截断或非负性门槛"],
        "reasoning": "提高 CV 解向量表达能力和 sweep 次数；不改变模型、q=pi、eta、OBC、Sz=0 或验收门槛。",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "只登记预案；当前 round31 仍未取得终态，不启动任何重试。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": "重试方案已准备但未触发", "why": "只有在 round31 cell manifest 明确失败后才允许单点 smoke；当前不能把 residual 超门槛的运行中快照当作终态。"},
            {"kind": "table", "columns": ["参数", "round31 基线", "候选重试", "目的"], "rows": [["DMRG maxdim", "256", "320", "增强基态表达"], ["CV maxdim", "600", "800", "增强修正向量表达"], ["nsweeps", "16", "20", "增加收敛机会"], ["验收门槛", "residual <= 1e-5", "不变", "保持可比性"]], "widths": ["24%", "23%", "23%", "30%"]},
            {"kind": "kv", "pairs": [["预案文件", "results/research_progress/qpi_cv_residual_retry_proposal_20260804.json"], ["触发条件", result["trigger"]], ["范围", "0 <= alpha,beta <= 1；排除负 alpha 与 Fig. 9"]]},
            {"kind": "note", "label": "保护规则", "style": "pending", "text": "先读取 round31 overall/status/progress/manifest 并完成 checksum；未确认终态前不改代码、不覆盖目录、不启动第二个 Julia。"},
        ],
    }
    report["sections"] = [item for item in report["sections"] if item["title"] != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · CV RETRY PLAN"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
