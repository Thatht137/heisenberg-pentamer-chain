"""把正 alpha 路径的参考 Fig. 7 诊断图加入 HTML。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
FIGURE = "reference_aligned_fig7_positive_alpha_pilot_20260804.png"
TITLE = "2026-08-04 参考 Fig. 7 正 alpha 路径诊断图"


def main() -> None:
    source = ROOT / "figures" / FIGURE
    target = ROOT / "results/research_progress" / FIGURE
    shutil.copy2(source, target)
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "对应参考 Fig. 7 的正 alpha 路径角色；只使用 beta=0.5、L=40、tmax=15 pilot 数据。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "Fig. 7 正区路径诊断图已补齐，仍不作为生产动态结论",
                "why": "alpha=0.14/0.23/0.33 的 raw q-omega 图和 q=pi 切片均可追溯；pilot 未通过生产级时间窗、dt/dt2 和 CV/TEBD 交叉门。",
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": FIGURE,
                        "caption": "对应参考 Fig. 7 的正 alpha 路径。上排为 beta=0.5 下三个 alpha 的 raw S^{zz}(q,omega)，下排为 q=pi 切片；共同色标用于比较色散位置，线图颜色区分 alpha。该图展示已存在 pilot 的结构变化，不宣称主峰、积分权重或相结构已经通过生产验收。",
                    }
                ],
            },
            {
                "kind": "table",
                "columns": ["参数", "值", "证据边界"],
                "rows": [
                    ["alpha", "0.14 / 0.23 / 0.33", "仅正区"],
                    ["beta, L, tmax", "0.5, 40, 15", "pilot"],
                    ["数据处理", "raw；无平滑、无裁剪", "保留原始结构"],
                    ["状态", "pilot_exploratory_not_production", "不关闭 Fig. 7 动态门"],
                ],
                "widths": ["25%", "38%", "37%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["绘图脚本", "scripts/autoresearch_v5/plot_reference_aligned_fig7_positive_alpha_20260804.py"],
                    ["来源 sidecar", "figures/reference_aligned_fig7_positive_alpha_pilot_20260804.sources.json"],
                    ["范围", "0<=alpha,beta<=1；负 alpha 与 Fig. 9 排除"],
                ],
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · REFERENCE FIG. 7 POSITIVE ALPHA DIAGNOSTIC"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "figure": FIGURE, "status": "pilot"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
