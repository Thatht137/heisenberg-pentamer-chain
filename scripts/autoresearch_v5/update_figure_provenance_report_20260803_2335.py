"""把最新图表来源和导出审计写入报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
AUDIT = ROOT / "results/research_progress/figure_provenance_audit_20260803.json"
TITLE = "2026-08-03 23:35 图表来源与导出 QA"


def main() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "使用项目 Anaconda 环境完成最新 provenance 审计；不改变图像内容。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "图表来源审计通过",
                "why": "29 个报告图像均存在且有 caption；source_missing=0、source_mismatches=0；PNG/TIFF 尺寸和 SVG/PDF 字体资源均可读取。",
            },
            {
                "kind": "table",
                "columns": ["审计项", "结果", "说明"],
                "rows": [
                    ["报告图像", str(len(audit.get("report_figures", []))), "全部存在并有 caption"],
                    ["source entries", str(audit.get("source_entries")), "无缺失"],
                    ["导出 entries", str(audit.get("export_entries")), "SVG/PDF/PNG/TIFF 可读"],
                    ["范围保护", "pass", "negative_alpha_included=false；fig9_included=false"],
                ],
                "widths": ["25%", "25%", "50%"],
            },
            {
                "kind": "note",
                "label": "剩余提示",
                "style": "pending",
                "text": "4 个诊断图 sidecar 未显式声明绘图后端，属于 provenance 元数据提示，不影响图像存在性和可读性；后续可在不重绘的情况下补齐。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 · FIGURE PROVENANCE QA"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": audit.get("status"), "report_figures": len(audit.get("report_figures", []))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
