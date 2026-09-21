"""把 Fig.7 pilot 定量后处理加入 HTML 报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SUMMARY = ROOT / "results/autoresearch_v5_20260804/round33_fig7_pilot_quantitative/summary.json"
TITLE = "2026-08-04 Fig.7 正 alpha pilot 定量峰值诊断"


def main() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    rows = summary["records"]
    section = {
        "title": TITLE,
        "note": "复用 beta=0.5、L=40、tmax=15 的 raw TEBD 矩阵；只做离散 q=pi 后处理，不连接服务器。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "pilot 定量趋势已提取，端点峰位不作生产结论",
                "why": "alpha=0.14 的离散最大值约为 omega=0.556；alpha=0.23 和 0.33 的最大值落在低频端点，需等待生产时间窗和 CV 主峰覆盖。",
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "../../figures/reference_aligned_fig7_pilot_quantitative_20260804.png",
                        "caption": "Fig.7 正 alpha pilot 的定量后处理。a：三条 raw q=pi 切片，实心点为全窗口最大值，空心点为 omega>=0.1 的内部最大值；b：端点敏感性；c：全窗口峰高；d：omega∈[0,1.5] 窗口积分。alpha=0.23/0.33 的全窗口最大值位于低频端点，因此该图只用于诊断原始 pilot 的结构变化，不作为稳定峰位、相界或 CV/TEBD Agreement 证据。",
                    }
                ],
            },
            {
                "kind": "table",
                "columns": ["alpha", "全窗口峰 omega/J1", "omega>=0.1 峰 omega/J1", "全窗口峰高", "窗口积分", "解释"],
                "rows": [
                    [f"{row['alpha']:.2f}", f"{row['peak_omega']:.4f}", f"{row['interior_peak_omega']:.4f}", f"{row['peak_intensity']:.4f}", f"{row['window_weight']:.4f}", "端点敏感" if row['peak_omega'] < 0.1 else "内部峰" ]
                    for row in rows
                ],
                "widths": ["10%", "18%", "22%", "15%", "15%", "20%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["摘要", "results/autoresearch_v5_20260804/round33_fig7_pilot_quantitative/summary.json"],
                    ["峰值 CSV", "results/autoresearch_v5_20260804/round33_fig7_pilot_quantitative/qpi_peak_summary.csv"],
                    ["图件 provenance", "figures/reference_aligned_fig7_pilot_quantitative_20260804.sources.json"],
                    ["范围", "alpha=0.14/0.23/0.33，beta=0.5，L=40，tmax=15；内部峰窗口从 omega=0.1 开始；排除负 alpha 和 Fig.9"],
                ],
            },
            {
                "kind": "note",
                "label": "证据边界",
                "style": "pending",
                "text": "raw pilot 的低频端点可能受有限时间窗、展宽和离散网格影响；全窗口峰与 omega>=0.1 内部峰的差异只用于敏感性诊断。在生产 TEBD dt/tmax 验收及 CV 主峰覆盖之前，不对 alpha 依赖的峰位迁移或谱权变化作物理定论。",
            },
        ],
    }
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · FIG.7 PILOT QUANTIFICATION"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": "recorded", "rows": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
