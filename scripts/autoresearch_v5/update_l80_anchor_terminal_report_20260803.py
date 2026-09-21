"""把 L=80 CV anchor 终态和独立验收写入报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
VALIDATOR = ROOT / "results/research_progress/l80_anchor_validator_20260803.json"
MANIFEST = ROOT / "results/autoresearch_v5_20260802/round22_cv_l80_anchor/cell-0003-L80-qpi-w025/manifest.json"
TITLE = "2026-08-03 16:20 L=80 CV anchor 终态验收"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    validator = json.loads(VALIDATOR.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    diagnostics = manifest["diagnostics"]
    sections = [
        section
        for section in report["sections"]
        if not section["title"].startswith("round22 L=80 CV anchor") and section["title"] != TITLE
    ]
    sections.insert(
        0,
        {
            "title": TITLE,
            "note": "远端终态已回传；本地独立 checksum、manifest 和 CV 验收通过",
            "blocks": [
                {
                    "kind": "verdict",
                    "status": "good",
                    "label": "L=80 CV anchor 已通过",
                    "why": "远端 status=success、manifest acceptance=pass；本地逐文件 checksum 和独立 validator 的 8 项检查全部通过。",
                },
                {
                    "kind": "table",
                    "columns": ["项目", "结果", "验收含义"],
                    "rows": [
                        ["物理点", "alpha=0.23、beta=0.5、L=80、q=pi、omega=0.25", "正区单频率 anchor"],
                        ["方差/截断", f"variance/L={diagnostics['variance_per_site']:.3e}；max truncation={diagnostics['max_dmrg_truncation']:.3e}", "均低于生产门"],
                        ["CV residual", f"{diagnostics['max_cv_relative_residual']:.3e}", "低于 1e-5 门槛"],
                        ["频点完成", f"{int(diagnostics['completed_points'])}/{int(diagnostics['total_points'])}", "单点完整"],
                        ["独立 validator", "8/8 PASS", "terminal、checksum、正区、方差、截断、残差、完整性、非负性"],
                    ],
                    "widths": ["24%", "38%", "38%"],
                },
                {
                    "kind": "kv",
                    "pairs": [
                        ["本地目录", "results/autoresearch_v5_20260802/round22_cv_l80_anchor/cell-0003-L80-qpi-w025"],
                        ["回传顺序", "远端 checksum -> scp 临时目录 -> 本地 checksum -> 原子移动"],
                        ["下一步", "分析 TEBD dt/dt2、raw spectrum 和非负性；不追加 L=80 频率点"],
                        ["范围", "0 <= alpha,beta <= 1；负 alpha 与 Fig. 9 排除"],
                    ],
                },
                {
                    "kind": "code",
                    "title": "终态证据",
                    "text": "results/research_progress/l80_anchor_validator_20260803.json\nresults/autoresearch_v5_20260802/round22_cv_l80_anchor/cell-0003-L80-qpi-w025/manifest.json\nscripts/autoresearch_v5/validate_cv_run.py",
                },
                {
                    "kind": "note",
                    "label": "动态门边界",
                    "style": "pending",
                    "text": "anchor 通过只闭合 L=80 单频率 CV 门；TEBD 首轮 manifest 的 raw_spectrum_min=-2.07、raw 非负性为 false，不能作为最终动态结论。",
                },
            ],
        },
    )
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"section": TITLE, "validator": validator["status"], "manifest": manifest["acceptance"]["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
