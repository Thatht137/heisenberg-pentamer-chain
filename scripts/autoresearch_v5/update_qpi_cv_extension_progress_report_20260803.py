"""记录 CV 扩展任务的单次进度快照。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
TITLE = "2026-08-03 q=pi CV 扩展低频 cell 进度"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "一次只读进度快照；未启动第二个 Julia。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "低频 CV cell 正常运行，尚无频点终态",
                "why": "DMRG 16 sweeps 已完成；第一个 correction-vector 频点仍在求解，progress.json 和 stdout.log 持续更新。",
            },
            {
                "kind": "table",
                "columns": ["量", "当前值", "判断"],
                "rows": [
                    ["整体任务", "starting；0/4 cells", "顺序 launcher 正常"],
                    ["当前 cell", "cell-l40-qpi-low-000-020；0/5 points", "omega=0.00–0.20，包含主峰附近"],
                    ["DMRG", "16/16 sweeps；E=-11.147101023773127", "基态阶段完成，未见错误"],
                    ["运行时间", "12:37；progress 最近更新于 23:07:25 CST", "进度文件仍更新，不判为卡死"],
                    ["资源", "Julia CPU≈825%；RSS≈1.35 GiB；状态 RNl", "线性求解占用正常，stderr 为空"],
                    ["进程纪律", "Julia=1；threads=8", "不启动第二个 Julia"],
                ],
                "widths": ["20%", "47%", "33%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["远端 progress", "round31_qpi_cv_extension/cell-l40-qpi-low-000-020/progress.json"],
                    ["启动证据", "results/research_progress/qpi_cv_extension_submission_20260803.json"],
                    ["范围", "0<=alpha,beta<=1；负 alpha 与 Fig. 9 排除"],
                ],
            },
            {
                "kind": "note",
                "label": "下一状态事件",
                "style": "pending",
                "text": "等待第一个频点完成或整体 launcher 进入下一 cell；不做短间隔轮询。终态后按回传、checksum、validator、组装和交叉验收顺序继续。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item["title"] != TITLE]
    report["sections"].insert(0, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 · CV EXTENSION PROGRESS"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"section": TITLE, "status": "running"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
