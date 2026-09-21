"""登记参考图一一对应版图像的本地视觉 QA。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
REPORT_DIR = REPORT.parent
TITLE = "2026-08-04 00:26 参考图一一对应版视觉 QA"


def main() -> None:
    figures = [
        {
            "figure": "Fig. 6",
            "file": "figures/reference_aligned_fig6_alpha1_beta_scan_exploratory_20260803.png",
            "panels": "5 个 beta 面板；共同色标；q-omega 热图",
            "qa": "通过",
            "boundary": "正 beta；footer 明确 exploratory，不作生产谱",
        },
        {
            "figure": "Fig. 7",
            "file": "figures/reference_aligned_fig7_positive_alpha_pilot_20260804.png",
            "panels": "上排 3 个热图 + 下排 3 个 q=pi 切片",
            "qa": "通过",
            "boundary": "alpha=0.14/0.23/0.33、beta=0.5；footer 明确 pilot",
        },
        {
            "figure": "Fig. 6/7 dynamic anchor",
            "file": "figures/qpi_tebd_maxdim96_production_20260803.png",
            "panels": "TEBD 收敛谱、差值、门槛占用率",
            "qa": "通过",
            "boundary": "CV 点以 sparse anchors 标示；未误标为 Agreement",
        },
    ]
    result = {
        "schema_version": 1,
        "checked_at": "2026-08-04T00:26:00+08:00",
        "status": "pass",
        "figures": figures,
        "checks": {
            "panel_roles_match_reference": True,
            "positive_region_only": True,
            "scope_labels_visible": True,
            "no_obvious_clipping_or_overlap": True,
            "dynamic_claims_not_overpromoted": True,
        },
        "scope": {"negative_alpha_excluded": True, "fig9_excluded": True},
    }
    output = REPORT_DIR / "reference_figure_visual_qa_20260804_0026.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "检查当前参考 Fig. 6/7 和 q=pi 动态图的面板角色、标注和证据边界；不修改 paper/。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "面板结构与证据边界通过视觉 QA",
                "why": "Fig. 6 保留 beta 横向面板，Fig. 7 保留热图+q=pi 切片角色；pilot/exploratory 和 sparse anchor 限制均可见。",
            },
            {
                "kind": "table",
                "columns": ["对应图", "面板结构", "QA 与边界"],
                "rows": [[item["figure"], item["panels"], f"{item['qa']}；{item['boundary']}\n{item['file']}" ] for item in figures],
                "widths": ["22%", "38%", "40%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["QA 文件", "results/research_progress/reference_figure_visual_qa_20260804_0026.json"],
                    ["范围", "0 <= alpha,beta <= 1；不含负 alpha 和 Fig. 9"],
                    ["结论", "图像可供 HTML/内部审阅使用；动态生产准入仍由数值门决定"],
                ],
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(2, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · FIGURE VISUAL QA"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": result["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
