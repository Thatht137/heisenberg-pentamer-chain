"""记录 L=80 anchor 与 TEBD supervisor 的当前只读终态。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
VALIDATOR = ROOT / "results/research_progress/l80_anchor_validator_20260803_1620_recheck.json"
TITLE = "2026-08-03 22:18 L=80 anchor 与 supervisor 终态复核"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    validator = json.loads(VALIDATOR.read_text(encoding="utf-8"))
    section = {
        "title": TITLE,
        "note": "按计划只读检查；未启动第二个 Julia，结果仅追加到 HTML。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "anchor 已通过，TEBD supervisor 在 raw-spectrum 门失败后停止",
                "why": "L=80 CV anchor 的独立 checksum 与 validate_cv_run 通过；TEBD coarse 虽完成 1200/1200 和 81/81 Fourier 点，但 raw spectrum 非负性失败，refined 未启动。",
            },
            {
                "kind": "table",
                "columns": ["对象", "只读终态", "处理"],
                "rows": [
                    ["L=80 CV anchor", "success / accepted；validator 8/8 PASS", "可作为 omega=0.25 的 CV 锚点"],
                    ["TEBD coarse", "completed 1200/1200；accepted=false；raw min=-0.93697", "保留失败证据，不进入正式 DSF 图"],
                    ["TEBD refined", "未启动", "不绕过 supervisor，不重新运行"],
                    ["服务器进程", "Julia=0；supervisor=0", "无运行任务，ETA 不适用"],
                ],
                "widths": ["24%", "42%", "34%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["anchor validator", "results/research_progress/l80_anchor_validator_20260803_1620_recheck.json"],
                    ["范围", "0<=alpha,beta<=1；负 alpha 与 Fig. 9 排除"],
                    ["下一门", "先修正严格 O_q|GS> 定义并做 L=10/20 smoke，再预览新的 L=40 任务"],
                ],
            },
            {
                "kind": "note",
                "label": "图版边界",
                "style": "pending",
                "text": "本次失败 raw spectrum 不会被裁剪或镜像后冒充正式谱；新参考图 Fig. 4--8 只使用正区和已通过的证据。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item["title"] != TITLE]
    report["sections"].insert(0, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 · TERMINAL AUDIT"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"section": TITLE, "validator": validator["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
