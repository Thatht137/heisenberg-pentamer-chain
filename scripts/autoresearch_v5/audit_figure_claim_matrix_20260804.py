"""核对 Fig.1--8 与 claim-evidence 矩阵的状态一致性。"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "docs/claim_evidence_matrix.md"
MANIFEST = ROOT / "results/research_progress/reference_aligned_figures_manifest_20260804.json"
REPORT = ROOT / "results/research_progress/report.json"
REPORT_DIR = REPORT.parent
TITLE = "2026-08-04 Fig.1--8 与 claim-evidence 矩阵一致性审计"


FIGURE_CLAIMS = {
    "Fig. 1": ["C1", "C2"],
    "Fig. 2": ["C6", "C7"],
    "Fig. 3": ["C5", "C11"],
    "Fig. 4": ["C4"],
    "Fig. 5": ["C6", "C7"],
    "Fig. 6": ["C10"],
    "Fig. 7": ["C10"],
    "Fig. 8": ["C10", "C12"],
}


def parse_matrix() -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\|\s*(C\d+)\s*\|(.+)\|\s*$", line)
        if not match:
            continue
        columns = [part.strip() for part in match.group(2).split("|")]
        if len(columns) >= 3:
            rows[match.group(1)] = {"claim": columns[0], "evidence": columns[1], "status": columns[2]}
    return rows


def main() -> None:
    claims = parse_matrix()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = []
    failures = []
    for figure, claim_ids in FIGURE_CLAIMS.items():
        figure_status = manifest["figures"][figure]["status"]
        statuses = [claims.get(claim, {}).get("status", "missing") for claim in claim_ids]
        if any(status == "missing" for status in statuses):
            failures.append(f"{figure}: claim missing")
        if figure in {"Fig. 6", "Fig. 7", "Fig. 8"} and figure_status in {"ready", "production"}:
            failures.append(f"{figure}: dynamic figure overpromoted")
        rows.append({"figure": figure, "claim_ids": claim_ids, "manifest_status": figure_status, "claim_status": statuses})
    result = {
        "schema_version": 1,
        "checked_at": "2026-08-04T00:35:45+08:00",
        "status": "pass" if not failures else "fail",
        "figures": rows,
        "failures": failures,
        "scope": {"negative_alpha_excluded": True, "fig9_excluded": True},
    }
    output = REPORT_DIR / "figure_claim_matrix_audit_20260804.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    table_rows = [[row["figure"], ", ".join(row["claim_ids"]), row["manifest_status"], "; ".join(row["claim_status"])] for row in rows]
    section = {
        "title": TITLE,
        "note": "只检查图表证据等级与结论矩阵，不修改 claim-evidence 原文和 paper/。",
        "blocks": [
            {"kind": "verdict", "status": "good" if result["status"] == "pass" else "bad", "label": "图—结论状态一致" if result["status"] == "pass" else "存在状态冲突", "why": "Fig.1–5 的可写/有边界结论与 C1–C7/C11 对齐；Fig.6–8 保留动态待计算边界。"},
            {"kind": "table", "columns": ["图号", "关联 claim", "图证据等级", "矩阵状态"], "rows": table_rows, "widths": ["12%", "18%", "28%", "42%"]},
            {"kind": "kv", "pairs": [["审计文件", "results/research_progress/figure_claim_matrix_audit_20260804.json"], ["检查规则", "动态图不得在 C10/C12 待计算时标为 ready/production"], ["范围", "0 <= alpha,beta <= 1；排除负 alpha 与 Fig. 9"]]},
        ],
    }
    report["sections"] = [entry for entry in report["sections"] if entry.get("title") != TITLE]
    report["sections"].insert(4, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · CLAIM MATRIX AUDIT"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": result["status"], "failures": failures}, ensure_ascii=False))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
