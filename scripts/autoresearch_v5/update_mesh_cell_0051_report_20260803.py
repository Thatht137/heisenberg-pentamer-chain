"""把高误差相图格点的本地诊断追加到 HTML 报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
DIAGNOSTIC = ROOT / "results/research_progress/mesh_cell_0051_diagnostic_20260803.json"
TITLE = "mesh-cell-0051 高误差格点诊断"


def build_section(data: dict[str, object]) -> dict[str, object]:
    cell = data["cell"]
    pairs = data["size_pairs"]
    return {
        "title": TITLE,
        "note": "只读复核；不新增相图扫描",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "误差由双初态差异主导，但不改变 guard 符号",
                "why": "alpha=0.125、beta=1、L=80 的误差为 6.049e-3，主要来自两个独立初态结构因子半差；最大截断误差仅 1.0e-11。60-80 尺寸差仍为 -0.03923 +/- 0.00658（5.97 sigma）。",
            },
            {
                "kind": "table",
                "columns": ["项目", "结果", "解释"],
                "rows": [
                    ["双初态结构因子", "0.279542 / 0.267444", "半差 0.006049，主导误差"],
                    ["最大截断误差", "9.999e-12", "不是 bond-dimension 截断失败"],
                    ["40-60 尺寸差", "-0.00651 +/- 0.00258（2.52 sigma）", "保持负号"],
                    ["60-80 尺寸差", "-0.03923 +/- 0.00658（5.97 sigma）", "显著为负，纳入 guard"],
                ],
                "widths": ["25%", "40%", "35%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["当前处理", "保留 accepted 记录并标记高误差；不用于趋势拟合或命名相界"],
                    ["是否重算", "当前不重算；重算应使用统一 warm-start 或增加独立初态"],
                    ["总体影响", "不改变 56 个内部尺寸差全部通过 2sigma、sign=-1 的 guard 结论"],
                    ["范围", "alpha,beta >= 0；负 alpha 与 Fig. 9 排除"],
                ],
            },
            {
                "kind": "code",
                "title": "诊断入口",
                "text": "results/research_progress/mesh_cell_0051_diagnostic_20260803.json\nresults/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/cells/mesh-cell-0051/manifest.json\nresults/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/phase-size-differences.csv",
            },
            {
                "kind": "note",
                "label": "验收边界",
                "style": "pending",
                "text": "该格点仍是高误差优先复核对象；本诊断不把它升级为高精度证据，也不因单格点扩大正区参数网格。",
            },
        ],
    }


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    data = json.loads(DIAGNOSTIC.read_text(encoding="utf-8"))
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(1, build_section(data))
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "section": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
