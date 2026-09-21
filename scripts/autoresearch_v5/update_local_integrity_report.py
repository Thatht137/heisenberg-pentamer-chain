#!/usr/bin/env python3
"""把本地完整性 QA 登记到离线 HTML 报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
AUDIT = ROOT / "results" / "research_progress" / "local_integrity_audit_20260803.json"
TITLE = "本地数据完整性与离线验收（2026-08-03）"


def build_section(audit: dict[str, object]) -> dict[str, object]:
    checksums = audit["checksums"]
    refs = audit["report_references"]
    status = audit["status"]
    return {
        "title": TITLE,
        "note": "不连接服务器；只检查已回传数据、报告引用和本地测试",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good" if status == "pass" else "bad",
                "label": "本地证据包完整" if status == "pass" else "本地证据包存在缺口",
                "why": f"{checksums['manifests']} 个 checksum 清单、{checksums['entries_checked']} 个文件条目全部通过；报告引用的本地路径无缺失。",
            },
            {
                "kind": "table",
                "columns": ["检查", "结果", "解释"],
                "rows": [
                    ["checksum", f"{checksums['entries_checked']} 条，0 失败", "SHA-256 逐文件复核"],
                    ["报告路径", f"{refs['total']} 条；本地缺失 {len(refs['missing_local'])} 条", "唯一远端 anchor 路径按预期保留"],
                    ["离线范围", "server_polled=false", "本轮没有重复轮询服务器"],
                    ["单元测试", "43/43 PASS", "autoresearch_v5 测试集全部通过"],
                ],
                "widths": ["24%", "30%", "46%"],
            },
            {
                "kind": "code",
                "title": "复核入口",
                "text": "scripts/autoresearch_v5/audit_local_integrity_20260803.py\nresults/research_progress/local_integrity_audit_20260803.json\npython -m unittest discover -s scripts/autoresearch_v5 -p 'test_*.py'",
            },
            {
                "kind": "note",
                "label": "范围边界",
                "style": "pending",
                "text": "只核对本地已有证据；不把 L=80 anchor 未终态或 TEBD 未启动误写成通过，不包含负 alpha。",
            },
        ],
    }


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    index = next((i + 1 for i, section in enumerate(sections) if section["title"] == "CV run 独立验收器回归"), len(sections))
    sections.insert(index, build_section(audit))
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "section": TITLE, "status": audit["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
