"""把 crossing guard 稳健性摘要加入 HTML 报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SUMMARY = ROOT / "results/autoresearch_v5_20260804/round34_phase_guard_robustness/summary.json"
TITLE = "2026-08-04 正区 crossing guard 留一 beta 稳健性"


def main() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    pair_rows = summary["pair_summary"]
    loo = summary["leave_one_beta_out"]
    loo_min = {
        pair: min(row["minimum_abs_delta_over_2sigma"] for row in loo if row["size_pair"] == pair)
        for pair in ("40-60", "60-80")
    }
    section = {
        "title": TITLE,
        "note": "仅复用已验收的正区 phase-size-differences.csv；不修改 phase policy、不连接服务器。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "C11 有限尺寸 guard 的方向对 beta 切片稳健",
                "why": "56 个 alpha>0 内部点均为负且超过 2σ；逐个去掉任一 beta 切片后，两组最终尺寸对仍保持全负且显著。",
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "../../figures/positive_phase_guard_margin_20260804.png",
                        "caption": "正区 crossing guard 稳健性。颜色和数字表示 ΔR/(2σ)，两个面板分别为 L=40→60 与 L=60→80；所有内部点均低于零。该图支持当前有限尺寸数据未见可验收内部 crossing，不等价于热力学极限单相证明。",
                    }
                ],
            },
            {
                "kind": "table",
                "columns": ["尺寸对", "点数", "最小 |ΔR|/(2σ)", "最大 |ΔR|/(2σ)", "留一 beta 后最小裕量", "判定"],
                "rows": [
                    [row["size_pair"], str(row["count"]), f"{row['minimum_abs_delta_over_2sigma']:.2f}", f"{row['maximum_abs_delta_over_2sigma']:.2f}", f"{loo_min[row['size_pair']]:.2f}", "全负且显著"]
                    for row in pair_rows
                ],
                "widths": ["14%", "12%", "20%", "20%", "20%", "14%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["摘要", "results/autoresearch_v5_20260804/round34_phase_guard_robustness/summary.json"],
                    ["源数据", "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/phase-size-differences.csv"],
                    ["留一规则", "分别去掉 beta=0.05/0.1/0.25/0.5/0.75/1.0 后重算方向和 2σ 裕量"],
                ],
            },
            {
                "kind": "note",
                "label": "phase-diagram 边界",
                "style": "pending",
                "text": "该分析只增强 crossing guard 的有限尺寸稳健性；没有 opposite-sign bracket，因此不产生相界估计，也不把‘未见 crossing’写成热力学极限相名。alpha=0 边界点、负 alpha 和 Fig.9 均不在本分析内。",
            },
        ],
    }
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(3, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · PHASE GUARD ROBUSTNESS"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": summary["status"], "pairs": len(pair_rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
