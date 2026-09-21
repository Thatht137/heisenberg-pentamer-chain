"""把 CV 三频点成本与质量图追加到离线报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "L=40 CV 三频点：信号、残差与求解成本"


def build_section() -> dict[str, object]:
    return {
        "title": TITLE,
        "note": "已通过的 round21 warm-start；不是完整动力学谱",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "三频点全部通过，成本随频率上升",
                "why": "alpha=0.23、beta=0.5、L=40、q=pi 的 omega=0.25/0.30/0.35 均满足非负性与 residual<=1e-5；最大 residual=6.021e-6。",
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": "cv_triplet_cost_quality_20260803.png",
                        "caption": "已验收的 L=40 correction-vector 三频点。a：强度从 omega=0.25 到 0.35 平滑下降；b：三个相对 residual 均低于 1e-5 门槛；c：warm-start 线性求解时间随频率增加（约 60、77、101 分钟）。这张图只证明离散频点的数值质量和成本，不外推为连续谱，也不替代尚未完成的 TEBD dt/dt2 交叉验收。",
                    }
                ],
            },
            {
                "kind": "table",
                "columns": ["omega/J1", "S(q,omega)", "relative residual", "solve time"],
                "rows": [
                    ["0.25", "0.5681807", "6.021e-6", "59.9 min"],
                    ["0.30", "0.4268871", "5.578e-6", "77.4 min"],
                    ["0.35", "0.3680496", "5.292e-6", "100.8 min"],
                ],
                "numeric": [True, True, True, True],
                "widths": ["18%", "27%", "27%", "28%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["数据源", "results/autoresearch_v5_20260802/round21_cv_triplet_warmstart/cell-0002-L40-qpi-w025-w035/spectrum.csv"],
                    ["图源哈希", "figures/cv_triplet_cost_quality_20260803.sources.json"],
                    ["后续边界", "不新增 L=80 频点；TEBD 释放后优先做 L=40 dt=0.025 与 dt=0.05 对照"],
                ],
            },
            {
                "kind": "note",
                "label": "解释边界",
                "style": "pending",
                "text": "强度下降是三个离散频点的观测，不命名谱峰或连续谱边界；成本图用于排期，不作为物理结论。负 alpha 与 Fig. 9 均未包含。",
            },
        ],
    }


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    index = next((i + 1 for i, section in enumerate(sections) if section["title"] == "计算等待期：已有结果可先分析"), len(sections))
    sections.insert(index, build_section())
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "section": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
