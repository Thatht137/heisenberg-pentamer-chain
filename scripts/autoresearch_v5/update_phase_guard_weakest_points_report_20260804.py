"""把 crossing guard 最弱裕量清单加入 HTML。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
SUMMARY = ROOT / "results/autoresearch_v5_20260804/round35_phase_guard_weakest_points/summary.json"
TITLE = "2026-08-04 正区 crossing guard 最弱裕量优先级"


def main() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    rows = summary["weakest_points"]
    section = {
        "title": TITLE,
        "note": "基于已验收的 56 个 alpha>0 内部尺寸差；只生成复核优先级，不提交新的服务器 action。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "所有内部点仍通过 2σ；已识别最弱裕量点",
                "why": "首要复核点为 beta=1.0、alpha=0.125 的 L=40→60 尺寸差，|ΔR|/(2σ)=1.26；没有点被判为 crossing。",
            },
            {
                "kind": "table",
                "columns": ["排名", "beta", "alpha", "尺寸对", "ΔR", "误差", "|ΔR|/(2σ)", "状态"],
                "rows": [
                    [str(index), f"{row['beta']:g}", f"{row['alpha']:g}", row["size_pair"], f"{row['delta_R']:.5f}", f"{row['error']:.5f}", f"{row['abs_delta_over_2sigma']:.2f}", "通过"]
                    for index, row in enumerate(rows, 1)
                ],
                "widths": ["8%", "10%", "10%", "13%", "15%", "15%", "17%", "12%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["清单摘要", "results/autoresearch_v5_20260804/round35_phase_guard_weakest_points/summary.json"],
                    ["排序规则", "按 |ΔR|-2σ 升序，再按 |ΔR|/(2σ) 升序"],
                    ["推荐用途", "服务器 round31 终态后，优先补做前 4 个点的独立初态/统计复核"],
                ],
            },
            {
                "kind": "note",
                "label": "执行边界",
                "style": "pending",
                "text": "本清单不改变 phase policy、尺寸序列或 sigma 阈值，不自动提交服务器任务。它只用于 round31 终态后决定是否需要有针对性的 C11 复核；负 alpha、Fig.9 和 alpha=0 边界仍排除。",
            },
        ],
    }
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(4, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · PHASE GUARD PRIORITY LIST"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": summary["status"], "rows": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
