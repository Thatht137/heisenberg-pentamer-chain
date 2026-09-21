"""登记本地 CV validator 复核。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
VALIDATION = ROOT / "results/research_progress/local_validator_recheck_20260803.json"
TITLE = "2026-08-03 本地 CV validator 复核"


def main() -> None:
    result = json.loads(VALIDATION.read_text(encoding="utf-8"))
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "使用已回传的 L=80 q=pi anchor 做本地独立复核；不依赖当前服务器连接。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good" if result.get("status") == "pass" else "bad",
                "label": "L=80 anchor 本地 8/8 检查通过" if result.get("status") == "pass" else "validator 复核未通过",
                "why": "checksum、正区、方差、截断、CV residual、频点完整性和非负性均通过；这只确认既有 anchor，不代表新扩展 cell 已终态。",
            },
            {
                "kind": "table",
                "columns": ["指标", "结果", "门槛"],
                "rows": [
                    ["variance/L", "2.968e-10", "<=1e-8"],
                    ["max truncation", "9.996e-11", "<=1e-8"],
                    ["CV residual", "6.715e-6", "<=1e-5"],
                    ["频点", "1/1", "完整"],
                    ["spectrum", "非负", "允许数值容差"],
                ],
                "widths": ["28%", "36%", "36%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["复核文件", "results/research_progress/local_validator_recheck_20260803.json"],
                    ["源目录", "results/autoresearch_v5_20260802/round22_cv_l80_anchor/cell-0003-L80-qpi-w025"],
                    ["动态交叉边界", "L=40 TEBD 与新 round31 CV 扩展仍未闭合"],
                ],
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(1, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 · LOCAL CV VALIDATOR RECHECK"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": result.get("status")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
