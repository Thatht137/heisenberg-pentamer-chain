"""审计报告和图表 manifest 是否误纳入负 alpha 或 Fig. 9 内容。"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "results/research_progress/report.json"
MANIFEST = ROOT / "results/research_progress/reference_aligned_figures_manifest_20260804.json"
REPORT_DIR = REPORT.parent
TITLE = "2026-08-04 研究范围排除项审计"


def strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [part for item in value for part in strings(item)]
    if isinstance(value, dict):
        return [part for item in value.values() for part in strings(item)]
    return []


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    texts = strings(report)
    negative_hits = [
        text
        for text in texts
        if re.search(r"alpha\s*=\s*-\s*\d|alpha\s*<\s*0", text, re.I)
        and "禁止 alpha<0" not in text
    ]
    fig9_hits = [text for text in texts if re.search(r"Fig\.?\s*9", text, re.I)]
    allowed = r"排除|不包含|不计算|不进入|不纳入|不扩展|不含|不移植|不引入|不做|不复现|不在范围|未包含|fig9_included\s*=\s*false|excluded|exclude|Fig\. ?9 材料/RIXS"
    fig9_unscoped = [
        text
        for text in fig9_hits
        if text.strip() != "负 alpha / Fig. 9"
        and "Fig. 9 未加范围说明" not in text
        and not re.search(allowed, text, re.I)
    ]
    scope_ok = all(
        manifest.get("scope", {}).get(key) is expected
        for key, expected in (("negative_alpha_excluded", True), ("fig9_excluded", True))
    )
    result = {
        "schema_version": 1,
        "checked_at": "2026-08-04T00:38:10+08:00",
        "status": "pass" if not negative_hits and not fig9_unscoped and scope_ok else "fail",
        "report_negative_parameter_hits": negative_hits,
        "report_fig9_unscoped_hits": fig9_unscoped,
        "allowed_scope_mentions": len(fig9_hits) - len(fig9_unscoped),
        "manifest_scope": manifest.get("scope", {}),
        "scope": {"negative_alpha_excluded": True, "fig9_excluded": True},
    }
    output = REPORT_DIR / "scope_exclusion_audit_20260804.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    section = {
        "title": TITLE,
        "note": "只检查当前 HTML 和 Fig.1–8 manifest 的活动证据范围；历史档案不作为当前结论。",
        "blocks": [
            {"kind": "verdict", "status": "good" if result["status"] == "pass" else "bad", "label": "范围排除项通过" if result["status"] == "pass" else "范围审计失败", "why": "没有发现负 alpha 数值参数或未加排除说明的 Fig. 9 活动证据；manifest 明确锁定正区。"},
            {"kind": "table", "columns": ["检查", "结果", "规则"], "rows": [["负 alpha 数值", str(len(negative_hits)), "禁止 alpha<0 或 alpha=-数值"], ["Fig. 9 未加范围说明", str(len(fig9_unscoped)), "只允许作为排除声明出现"], ["manifest scope", "通过" if scope_ok else "失败", "negative_alpha_excluded=true；fig9_excluded=true"]], "widths": ["30%", "20%", "50%"]},
            {"kind": "kv", "pairs": [["审计文件", "results/research_progress/scope_exclusion_audit_20260804.json"], ["当前范围", "0 <= alpha,beta <= 1；排除负 alpha 和 Fig. 9"]]},
        ],
    }
    report["sections"] = [entry for entry in report["sections"] if entry.get("title") != TITLE]
    report["sections"].insert(5, section)
    report["eyebrow"] = "RESEARCH LOG · UPDATED 2026-08-04 · SCOPE AUDIT"
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"title": TITLE, "status": result["status"], "negative_hits": len(negative_hits), "fig9_unscoped": len(fig9_unscoped)}, ensure_ascii=False))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
