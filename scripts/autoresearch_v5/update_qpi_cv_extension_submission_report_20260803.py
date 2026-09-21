"""把 CV 主峰扩展任务的上传和启动证据写入报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
EVIDENCE = ROOT / "results/research_progress/qpi_cv_extension_submission_20260803.json"
TITLE = "2026-08-03 q=pi CV 主峰与积分窗扩展已启动"


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    launch = evidence["launch"]
    section = {
        "title": TITLE,
        "note": "单 Julia 顺序任务；上传前后均做目录冲突、进程、hash 和脚本语法检查。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "CV 扩展运行中，主峰覆盖尚未验收",
                "why": "已进入 L=40 低频 cell；当前只确认启动健康，必须等待每个 cell 的 manifest/status/checksum 后才能升级交叉方法结论。",
            },
            {
                "kind": "table",
                "columns": ["项目", "参数/状态", "目的"],
                "rows": [
                    ["低频 cell", "omega=0.00,0.05,0.10,0.15,0.20", "包围 TEBD 离散主峰 omega=0.05"],
                    ["高频锚点", "omega=0.55,1.00,1.50", "覆盖主要积分窗的上端并提供远离峰的独立校验"],
                    ["物理实例", "alpha=0.23，beta=0.5，L=40，q=pi，eta=0.1", "与已通过 TEBD/maxdim 对照完全一致"],
                    ["执行方式", "4 cells 顺序；Julia=1；threads=8", "避免服务器资源冲突，单 cell 具备 progress.json"],
                    ["启动状态", f"launcher={launch['launcher_pid']}；driver={launch['driver_pid']}；Julia={launch['julia_pid']}", "phase=starting，0/4 cells 已完成"],
                ],
                "widths": ["20%", "45%", "35%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["提交预览", "results/research_progress/qpi_cv_extension_submission_preview_20260803.json"],
                    ["启动证据", "results/research_progress/qpi_cv_extension_submission_20260803.json"],
                    ["远端目录", "results/autoresearch_v5_20260803/round31_qpi_cv_extension"],
                    ["估计耗时", "典型 8–12 h；保守上限 16 h；不做短间隔轮询"],
                ],
            },
            {
                "kind": "note",
                "label": "验收边界",
                "style": "pending",
                "text": "只有在低频主峰被 CV 点包围、[0,1.5] 积分窗被覆盖且所有点通过 residual/非负性/checksum 后，才允许把 TEBD–CV 标记为 Agreement；当前仍是 NotEvaluable。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item["title"] != TITLE]
    report["sections"].insert(0, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03 · CV EXTENSION RUNNING"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"section": TITLE, "status": launch["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
