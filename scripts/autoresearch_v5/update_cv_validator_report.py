#!/usr/bin/env python3
"""记录独立 CV run 验收器的回归结果。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
TITLE = "CV run 独立验收器回归"


def build_section() -> dict[str, object]:
    return {
        "title": TITLE,
        "note": "2026-08-03 · 独立复核，不新增服务器计算",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "独立验收器再次通过 L=40 三频点 CV run",
                "why": "round20、round21 及 2026-08-03 对 round21 的现场重验均通过终态、checksum、方差、截断、CV residual、完整频点、非负性及正参数范围检查。",
            },
            {
                "kind": "table",
                "columns": ["run", "尺寸/频点", "最大 residual", "variance/L", "结果"],
                "rows": [
                    ["round20", "L=40、1 点", "6.021e-6", "2.612e-10", "PASS"],
                    ["round21", "L=40、3 点", "6.021e-6", "2.612e-10", "PASS"],
                    ["round20 live recheck", "L=40、1 点", "6.02125e-6", "2.61194e-10", "PASS"],
                    ["round21 live recheck", "L=40、3 点", "6.02125e-6", "2.61194e-10", "PASS"],
                ],
                "numeric": [False, False, True, True, False],
                "widths": ["17%", "25%", "20%", "20%", "18%"],
            },
            {
                "kind": "list",
                "title": "验收项目",
                "items": [
                    "终态 status/manifest 与 acceptance=pass",
                    "checksums.sha256 全量逐文件校验",
                    "variance_per_site<=1e-8、max_dmrg_truncation<=1e-8",
                    "max_cv_residual<=1e-5、频点数量完整",
                    "频谱有限、非负、alpha/beta 均位于 [0,1]",
                ],
            },
            {
                "kind": "code",
                "title": "回归入口",
                "text": "scripts/autoresearch_v5/validate_cv_run.py\nresults/autoresearch_v5_20260802/round20_cv_resume_warmstart/round20_validation.json\nresults/autoresearch_v5_20260802/round21_cv_triplet_warmstart/round21_validation.json\nresults/research_progress/cv_single_validator_recheck_20260803.json\nresults/research_progress/cv_triplet_validator_recheck_20260803.json",
            },
            {
                "kind": "note",
                "label": "使用边界",
                "style": "pending",
                "text": "现场重验只证明本地数据和验收器当前仍一致，不替代 L=80 anchor 的新数据验收；不涉及负 alpha 或 TEBD 生产结论。",
            },
        ],
    }


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    index = next(
        (i + 1 for i, section in enumerate(sections) if section["title"] == "TEBD pilot 审计与交叉检查准备"),
        len(sections),
    )
    sections.insert(index, build_section())
    report["sections"] = sections
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "section": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
