"""登记 round31 已结束 cell 的回传与独立验收。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-04 round31 已结束 cell 回传与独立验收"


def main() -> None:
    receipt = json.loads((ROOT / "results/research_progress/qpi_cv_extension_completed_cells_fetch_receipt_20260804.json").read_text(encoding="utf-8"))
    low = json.loads((ROOT / "results/research_progress/round31_low_validator_20260804.json").read_text(encoding="utf-8"))
    high = json.loads((ROOT / "results/research_progress/round31_high055_validator_20260804.json").read_text(encoding="utf-8"))
    section = {
        "title": TITLE,
        "note": "只回传已结束的 low 与 0.55 cell；正在运行的 1.00 cell 和待启动的 1.50 cell 未下载。",
        "blocks": [
            {"kind": "verdict", "status": "warn", "label": "回传成功；一通过、一因 residual 失败", "why": "远端 checksum 和本地独立 checksum 均通过；0.55 validator 全部通过，low cell 保留为数值失败证据。"},
            {"kind": "table", "columns": ["cell", "回传/校验", "关键结果", "证据等级"], "rows": [
                ["low 0.00–0.20", "checksum pass；validator fail", "max residual=1.323762e-5 > 1e-5；5/5 完整", "失败原始证据，禁止用于生产谱"],
                ["0.55", "checksum pass；validator pass", "residual=6.487728e-6；方差、截断、非负性均通过", "可作为稀疏 CV 锚点"],
            ], "widths": ["22%", "28%", "30%", "20%"]},
            {"kind": "kv", "pairs": [
                ["本地目录", "results/autoresearch_v5_20260803/round31_qpi_cv_extension_completed_cells_20260804"],
                ["回传 receipt", "results/research_progress/qpi_cv_extension_completed_cells_fetch_receipt_20260804.json"],
                ["validator", "results/research_progress/round31_low_validator_20260804.json；round31_high055_validator_20260804.json"],
                ["回传方式", "非覆盖；22 个文件；33,685 bytes；remote_write=false"],
            ]},
            {"kind": "note", "label": "保护规则", "style": "pending", "text": "low residual 失败不降低门槛、不覆盖原目录；只有 round31 全局终态后才按预案单点重试 omega=0.05。0.55 点可进入受限叠加，但不能关闭 CV–TEBD 动力学交叉门。"},
        ],
    }
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    report["sections"] = [s for s in report["sections"] if s.get("title") != TITLE]
    report["sections"].insert(2, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · COMPLETED CELLS VALIDATED"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "high055": high["status"], "low": low["status"], "files": receipt["file_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
