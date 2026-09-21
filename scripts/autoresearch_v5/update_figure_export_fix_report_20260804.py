"""记录参考图导出文件的完整性修复。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
FIGURE = ROOT / "figures/cv_continuum_overlay_20260803.tiff"
TITLE = "2026-08-04 Fig. 8 TIFF 导出完整性修复"


def main() -> None:
    digest = hashlib.sha256(FIGURE.read_bytes()).hexdigest()
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "只修复导出文件，不改变数据、图形内容或动态证据等级。",
        "blocks": [
            {"kind": "verdict", "status": "good", "label": "Fig. 8 TIFF 可用", "why": f"已从现有 PNG 生成 LZW 压缩 TIFF；文件大小 {FIGURE.stat().st_size:,} bytes，SHA-256 已登记。"},
            {"kind": "kv", "pairs": [["文件", "figures/cv_continuum_overlay_20260803.tiff"], ["SHA-256", digest], ["状态", "SVG/PDF/PNG/TIFF 四种导出均非空"]]},
            {"kind": "note", "label": "解释边界", "style": "pending", "text": "该修复只保证图表交付完整性；Fig. 8 仍是 constrained_overlay，不能替代 CV 主峰覆盖或 CV/TEBD 交叉验收。"},
        ],
    }
    report["sections"] = [item for item in report["sections"] if item["title"] != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · REFERENCE-ALIGNED FIGURES"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "bytes": FIGURE.stat().st_size, "sha256": digest}, ensure_ascii=False))


if __name__ == "__main__":
    main()
