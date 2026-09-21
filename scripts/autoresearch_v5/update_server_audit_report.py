#!/usr/bin/env python3
"""把服务器只读审计结果写入 HTML 报告源。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
TITLE = "2026-08-02 服务器与任务审计"


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build_section() -> dict[str, object]:
    return {
        "title": TITLE,
        "note": "只读预检 · 服务器优先、离线环境、未提交计算",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "环境通过明日探针前置检查",
                "why": "Julia/ITensor 可用、依赖清单哈希一致、磁盘和内存充足，且没有活动 Julia 任务。",
            },
            {
                "kind": "table",
                "columns": ["项目", "审计结果", "判断"],
                "rows": [
                    ["SSH/账户", "39.96.207.180:6000 · wangjieren · c104-ysu", "通过"],
                    ["Julia", "1.12.3 · ITENSOR_SMOKE_OK", "通过"],
                    ["Manifest", "37a53ffd73db57b9db9c4ce11f6265a9a41ac2035dc421b01f9a633d893ba12c", "与本地一致"],
                    ["Project", "39e917d3ca9615132999b4ae6a9731e8b592454267e38b5779423e76a8d2dd7e", "与本地一致"],
                    ["资源", "/home 可用 707 GiB；内存可用 245 GiB；load 0.21/0.11/0.09", "通过"],
                    ["CV 资产", "5 manifests；45/45 checksum 条目通过；4 success，1 个 L=20 cutoff=1e-12 收敛失败", "文件完整，按门槛区分"],
                    ["活动任务", "pgrep -x julia 无输出", "无长任务"],
                ],
                "widths": ["18%", "58%", "24%"],
            },
            {
                "kind": "text",
                "text": "服务器按直连同步方案部署，没有 .git 元数据；后续每个 run 必须保存源码 SHA-256、Project/Manifest 哈希和完整清单。现有 CV 服务器资产只有 round1 精确 oracle、round2 成本探针和 round3 L=40 单频率探针，未发现 round4 可恢复 oracle 或 checkpoint_latest.jld2。L=20 cutoff=1e-12 的失败结果仅作为收敛负对照，不进入生产结论。",
            },
            {
                "kind": "kv",
                "pairs": [
                    ["今日完成", "只读连接、Julia/ITensor smoke、Manifest/Project 哈希、磁盘、内存、负载、活动任务和 CV 目录核对"],
                    ["明日新 run", "results/autoresearch_v5_20260802/round20_cv_resume_warmstart"],
                    ["明日第一步", "新目录单频率 checkpoint smoke；通过后才做 L=40 三个相邻频率 warm-start"],
                    ["明确排除", "负 alpha、相图扩展、L=80 长作业、覆盖旧 round3 结果"],
                ],
            },
            {
                "kind": "note",
                "label": "审计结论",
                "style": "info",
                "text": "环境没有阻塞；真正的前置缺口是可恢复 CV run 尚未落地。明日从独立 run 开始，不假定服务器存在旧 checkpoint。",
            },
            {
                "kind": "code",
                "title": "审计记录",
                "text": "docs/server_audit_20260802.md\ndocs/delivery_plan_to_20260810.md",
            },
        ],
    }


def main() -> None:
    report = load(REPORT)
    sections = [item for item in report["sections"] if item["title"] != TITLE]
    index = next((i for i, item in enumerate(sections) if item["title"] == "8 月 10 日交付计划"), 0)
    sections.insert(index, build_section())
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-02"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "section": TITLE}, ensure_ascii=False))


if __name__ == "__main__":
    main()
