"""把交付就绪审计登记到长期 HTML 报告。"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results" / "research_progress" / "report.json"
AUDIT = ROOT / "results" / "research_progress" / "delivery_readiness_audit_20260803.json"
TITLE = "8/10 交付就绪审计（2026-08-03）"


def build_section(audit: dict[str, object]) -> dict[str, object]:
    checks = audit["checks"]
    passed = sum(bool(value) for value in checks.values())
    total = len(checks)
    rows = [
        ["HTML、计划、证据矩阵和主图资产", "通过" if checks["required_files"] else "未通过"],
        ["正区相图 guard", "通过" if checks["positive_phase_audit"] else "未通过"],
        ["L=40 CV 三频点现场重验", "通过" if checks["cv_l40_recheck"] else "未通过"],
        ["正区 TEBD pilot 限制性审计", "通过" if checks["positive_tebd_pilot_audit"] else "未通过"],
        ["TEBD 生产配置（等待 anchor）", "通过" if checks["tebd_production_ready_after_anchor"] else "未通过"],
        ["L=80 anchor 运行时诊断", "通过" if checks["l80_runtime_diagnosis"] else "未通过"],
        ["L=80 anchor 终态", "通过" if checks.get("l80_anchor_terminal") else "待完成"],
        ["CV/TEBD 动力学交叉验收", "通过" if checks.get("tebd_crosscheck_terminal") else "待完成"],
        ["最终动态结论准入", "待完成"],
    ]
    return {
        "title": TITLE,
        "note": "只含 alpha>=0、beta>=0；这是就绪审计，不是论文完成声明",
        "blocks": [
            {
                "kind": "verdict",
                "status": "warn",
                "label": "静态与方法证据已就绪，动态生产门仍未闭合",
                "why": f"本轮通过 {passed}/{total} 项就绪检查；剩余动态门槛依赖 L=80 anchor 终态和 TEBD dt/dt2 交叉数据，不能提前写成生产结论。",
            },
            {"kind": "table", "columns": ["检查项", "状态"], "rows": rows, "widths": ["72%", "28%"]},
            {
                "kind": "list",
                "title": "已锁定的交付边界",
                "items": [
                    "范围只含 alpha>=0、beta>=0；不纳入负 alpha 和 Fig. 9。",
                    "105 条正区记录的 guard 结论是不支持当前数据中的可验收内部 crossing，不命名热力学相界。",
                    "正区 TEBD pilot 图只用于说明时间窗、raw inversion 和非负性风险，不作为生产 DSF。",
                    "只有 L=80 CV、TEBD dt/dt2 和 CV/TEBD 主峰及权重门槛全部通过，才提升动态结论级别。",
                ],
            },
            {
                "kind": "code",
                "title": "审计入口",
                "text": "scripts/autoresearch_v5/audit_delivery_readiness_20260803.py\nresults/research_progress/delivery_readiness_audit_20260803.json\nscripts/autoresearch_v5/update_delivery_readiness_report.py",
            },
            {
                "kind": "note",
                "label": "当前下一步",
                "style": "pending",
                "text": "保持 anchor 单任务运行；终态后回传到独立目录、运行 validate_cv_run.py，再由 supervisor 启动 TEBD。若 8/04 中午仍无终态，冻结 L=80 动力学扩展，按降级方案交付已通过的 L=40 CV、静态机制和 pilot 审计。",
            },
        ],
    }


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    sections = [section for section in report["sections"] if section["title"] != TITLE]
    index = next((i + 1 for i, section in enumerate(sections) if section["title"] == "TEBD pilot 审计与交叉检查准备"), len(sections))
    sections.insert(index, build_section(audit))
    report["sections"] = sections
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-03"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(REPORT), "section": TITLE, "status": audit["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
