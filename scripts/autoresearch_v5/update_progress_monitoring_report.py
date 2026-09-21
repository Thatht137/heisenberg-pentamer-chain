#!/usr/bin/env python3
"""把计算进度显示标准登记到离线 HTML 报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
STANDARD = ROOT / "results" / "research_progress" / "computation_progress_standard_20260803.json"
TITLE = "计算进度显示标准（2026-08-03）"


def build_section(standard: dict[str, object]) -> dict[str, object]:
    return {
        "title": TITLE,
        "note": "所有新生产计算必须生成 progress.json；当前旧 anchor 不中途覆盖",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "进度 heartbeat 已接入本地生产入口",
                "why": "CV、静态 DMRG、双初态、TEBD/Fourier 以及旧版 DMRG 封装均每 30 秒原子更新 progress.json；9 个入口已上传远端并通过 AST/哈希复核，本地生产入口测试 21/21 通过。",
            },
            {
                "kind": "table",
                "columns": ["计算入口", "可见进度", "状态文件"],
                "rows": [
                    ["可恢复 CV", "阶段、已完成频点、stdout 更新时间", "progress.json"],
                    ["静态 DMRG", "最近 sweep、stdout 更新时间", "progress.json"],
                    ["双初态静态", "当前 child 与两个子任务状态", "父/子 progress.json"],
                    ["TEBD + Fourier", "TEBD step/百分比/ETA、Fourier q", "progress.json"],
                    ["远端部署", "9/9 哈希一致、AST 通过", "新旧入口均已更新"],
                ],
                "widths": ["25%", "47%", "28%"],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["heartbeat 间隔", "30 s"],
                    ["统一实现", "scripts/autoresearch_v5/progress.py"],
                    ["验证", "本地 py_compile、21/21 测试；远端 9/9 AST"],
                    ["远端目标", "39.96.207.180:6000 · scripts/autoresearch_v5"],
                    ["当前 anchor", "旧 runner 已在运行；不覆盖，终态后同步新入口"],
                ],
            },
            {
                "kind": "table",
                "columns": ["验证层", "结果", "解释"],
                "rows": [
                    ["Python 生产入口", "21/21 通过", "progress、恢复、静态规格、oracle 和 TEBD 交叉验收测试"],
                    ["远端 Julia", "54/54 通过", "Julia 1.12.3；服务器断网 smoke/测试为生产依据"],
                    ["本地 Julia", "环境受限", "1.11.5 的 Pkg/预编译受 Windows ACL 阻断，不判为模型失败"],
                ],
                "widths": ["25%", "20%", "55%"],
            },
            {
                "kind": "code",
                "title": "复核入口",
                "text": "scripts/autoresearch_v5/progress.py\nresults/research_progress/computation_progress_standard_20260803.json\nprogress.json（每个新 run 的输出目录内）",
            },
            {
                "kind": "note",
                "label": "范围边界",
                "style": "pending",
                "text": "heartbeat 只提供运行可观测性，不降低残差、方差、非负性或 checksum 验收门槛；不包含负 alpha。",
            },
        ],
    }


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    standard = json.loads(STANDARD.read_text(encoding="utf-8"))
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    index = next((i + 1 for i, section in enumerate(sections) if section["title"] == "本地数据完整性与离线验收（2026-08-03）"), len(sections))
    sections.insert(index, build_section(standard))
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "section": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
