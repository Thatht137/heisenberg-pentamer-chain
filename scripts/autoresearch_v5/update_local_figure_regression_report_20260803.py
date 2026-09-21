"""记录本地图表和分析器回归结果。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-03 23:27 本地图表与分析器回归"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "切换到项目已有 Anaconda 绘图环境后执行；未接触服务器计算。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "本地回归 43/43 通过",
                "why": "q=pi TEBD、CV/TEBD 交叉分析、图表管线和全部 autoresearch_v5 测试均通过；compileall 通过。",
            },
            {
                "kind": "table",
                "columns": ["项目", "结果", "解释"],
                "rows": [
                    ["Python 绘图环境", "D:/program/Anaconda3_2025.06/python.exe；matplotlib 3.10.0", "可生成 SVG/PDF/PNG/TIFF"],
                    ["单元测试", "43/43 OK", "包含 q=pi TEBD plot 和 CV/TEBD analyzer"],
                    ["编译检查", "scripts/autoresearch_v5 全目录通过", "未发现语法错误"],
                    ["论文图资产", "Fig. 1--8 所需 PNG 全部存在", "报告引用无缺失"],
                ],
                "widths": ["25%", "38%", "37%"],
            },
            {
                "kind": "note",
                "label": "边界",
                "style": "pending",
                "text": "本地回归只能证明脚本和已有结果一致，不能替代正在运行的 CV 终态；Fig. 6--8 仍按报告中的部分完成/等待交叉验收标记。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 · LOCAL FIGURE REGRESSION"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "tests": "43/43", "compileall": "pass"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
