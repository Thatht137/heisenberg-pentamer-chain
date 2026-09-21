"""把等待期的本地验收结果登记到研究报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
DELIVERY = ROOT / "results" / "research_progress" / "delivery_readiness_audit_20260803.json"
INTEGRITY = ROOT / "results" / "research_progress" / "local_integrity_audit_20260803.json"
TITLE = "2026-08-03 15:08 等待期本地验收"


def build_section(delivery: dict[str, object], integrity: dict[str, object]) -> dict[str, object]:
    checks = delivery["checks"]
    passed = sum(bool(value) for value in checks.values())
    total = len(checks)
    return {
        "title": TITLE,
        "note": "服务器 anchor 仍按计划运行；本节只登记离线审计，不启动新的 Julia",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good",
                "label": "等待期本地验收通过",
                "why": "Python 21/21 回归、compileall、TEBD 交接/启动前哈希、图表来源和本地 checksum 审计均通过。",
            },
            {
                "kind": "table",
                "columns": ["验收项", "结果", "范围说明"],
                "rows": [
                    ["Python 回归", "21/21 PASS", "progress、恢复、静态规格、oracle 和 TEBD 分析器"],
                    ["Python 编译", "PASS", "scripts 全目录 compileall 无错误"],
                    ["TEBD 交接与 preflight", "PASS", "仅验证配置/哈希/保护条件，未启动 TEBD"],
                    ["本地完整性", f"{integrity['checksums']['manifests']} manifests / {integrity['checksums']['entries_checked']} entries", "0 checksum failure；报告引用无缺失"],
                    ["交付门", f"{passed}/{total}（{delivery['status']}）", "剩余 3 项依赖服务器动态数据"],
                ],
                "widths": ["25%", "25%", "50%"],
            },
            {
                "kind": "list",
                "title": "当前仍未宣称完成的动态门",
                "items": [
                    "L=80 omega=0.25 anchor 终态、manifest、checksum 和 CV residual。",
                    "L=40 TEBD 的 dt/dt2、时间窗、raw spectrum 与非负性检查。",
                    "CV/TEBD 主峰位置和低频权重的独立交叉验收。",
                ],
            },
            {
                "kind": "kv",
                "pairs": [
                    ["服务器动作", "不提前轮询、不启动第二个 Julia；等待 16:20 自动检查"],
                    ["预计窗口", "依据 13:51 诊断：最可能 13:51–21:51，保守截止 2026-08-04 01:51"],
                    ["范围", "0 <= alpha,beta <= 1；负 alpha 和 Fig. 9 排除"],
                ],
            },
            {
                "kind": "code",
                "title": "本轮复核入口",
                "text": "python -m unittest discover -s scripts/autoresearch_v5 -p 'test_*.py'\npython -m compileall -q scripts\nresults/research_progress/delivery_readiness_audit_20260803.json\nresults/research_progress/local_integrity_audit_20260803.json",
            },
        ],
    }


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    delivery = json.loads(DELIVERY.read_text(encoding="utf-8"))
    integrity = json.loads(INTEGRITY.read_text(encoding="utf-8"))
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    sections.insert(0, build_section(delivery, integrity))
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"section": TITLE, "delivery": delivery["status"], "integrity": integrity["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
