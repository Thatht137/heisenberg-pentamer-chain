"""把正区 alpha=1 beta 扫描诊断图加入 HTML。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
FIGURE = "reference_aligned_fig6_alpha1_beta_scan_exploratory_20260803.png"
TITLE = "2026-08-03 参考 Fig. 6 正区 beta 扫描诊断图"


def main() -> None:
    source = ROOT / "figures" / FIGURE
    target = ROOT / "results/research_progress" / FIGURE
    if not source.is_file():
        raise SystemExit(f"缺少图像: {source}")
    shutil.copy2(source, target)
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "只展示 alpha=1、beta>=0 的已有探索性 TEBD 网格；对应参考 Fig. 6 的多 beta 面板角色。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "参考 Fig. 6 的正区版式已补齐，但仍是探索性证据",
                "why": "五个 beta 面板使用既有 raw TEBD CSV，保留原始强度、不平滑、不裁剪；缺少生产 CV 和完整 TEBD 交叉门，因此不提升动态结论等级。",
            },
            {
                "kind": "figures",
                "items": [
                    {
                        "src": FIGURE,
                        "caption": "对应参考 Fig. 6 的五面板 beta 演化。alpha=1、beta=1.0/0.7/0.5/0.4/0.1，展示 raw S^{zz}(q,omega)；颜色为共同线性强度标度。该图只用于观察正区色散结构和选择生产锚点，不替代 CV residual、TEBD dt/dt2、tmax 或非负性验收。",
                    }
                ],
            },
            {
                "kind": "table",
                "columns": ["项目", "值", "边界"],
                "rows": [
                    ["alpha", "1.0", "正区"],
                    ["beta", "1.0, 0.7, 0.5, 0.4, 0.1", "均为非负 beta"],
                    ["数据", "200×400 raw CSV / 面板", "已有探索性 TEBD"],
                    ["显示处理", "共同色标；无平滑、无裁剪", "不改变数据"],
                    ["生产状态", "Exploratory_NotProduction", "不用于 Fig. 6 最终门"],
                ],
                "widths": ["24%", "43%", "33%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["绘图脚本", "scripts/autoresearch_v5/plot_reference_aligned_fig6_positive_beta_20260803.py"],
                    ["来源 sidecar", "figures/reference_aligned_fig6_alpha1_beta_scan_exploratory_20260803.sources.json"],
                    ["负 alpha / Fig. 9", "均排除"],
                ],
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 · REFERENCE FIG. 6 POSITIVE BETA DIAGNOSTIC"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "figure": FIGURE, "status": "exploratory"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
