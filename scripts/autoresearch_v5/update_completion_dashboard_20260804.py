# -*- coding: utf-8 -*-
"""从现有审计文件重建研究完成度仪表盘。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROGRESS = ROOT / "results/research_progress"
OUT = PROGRESS / "research_completion_dashboard_20260804.json"
REPORT = PROGRESS / "report.json"
CLAIMS_MD = ROOT / "docs/claim_evidence_matrix.md"
TITLE = "2026-08-04 实时交付仪表盘（本地审计汇总）"


def load(name: str) -> dict[str, object]:
    return json.loads((PROGRESS / name).read_text(encoding="utf-8"))


def main() -> None:
    matrix = load("figure_claim_matrix_audit_20260804.json")
    manifest = load("reference_aligned_figures_manifest_20260804.json")
    delivery = load("delivery_readiness_audit_20260803.json")
    asset = load("figure_asset_pixel_qa_20260804.json")
    claim_states: dict[str, str] = {}
    for line in CLAIMS_MD.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("| C"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) >= 5 and re.fullmatch(r"C\d+", parts[1]):
            claim_states[parts[1]] = parts[4]
    pending_ids = sorted(claim_id for claim_id, status in claim_states.items() if "待计算" in status)
    pending = len(pending_ids)
    total = len(claim_states)
    static_ready = sum(manifest["figures"][name]["status"] in {"ready", "ready_with_boundary"} for name in ("Fig. 1", "Fig. 2", "Fig. 3", "Fig. 4", "Fig. 5"))
    dynamic_not_production = sum(manifest["figures"][name]["status"] not in {"ready", "ready_with_boundary"} for name in ("Fig. 6", "Fig. 7", "Fig. 8"))
    dashboard = {
        "schema_version": 1,
        "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
        "claim_evidence": {"total": total, "supported_or_bounded": total - pending, "pending": pending, "coverage_fraction": (total - pending) / total if total else 0.0, "pending_ids": pending_ids},
        "figures": {"reference_aligned_total": 8, "static_ready_or_bounded": static_ready, "dynamic_not_production": dynamic_not_production, "static_ready_or_bounded_ids": [name for name in ("Fig. 1", "Fig. 2", "Fig. 3", "Fig. 4", "Fig. 5") if manifest["figures"][name]["status"] in {"ready", "ready_with_boundary"}], "dynamic_not_production_ids": [name for name in ("Fig. 6", "Fig. 7", "Fig. 8") if manifest["figures"][name]["status"] not in {"ready", "ready_with_boundary"}]},
        "delivery_gates": {"passed": sum(bool(value) for value in delivery["checks"].values()), "total": len(delivery["checks"]), "pending_ids": [name for name, value in delivery["checks"].items() if not value], "status": delivery["status"]},
        "asset_qa": {"status": asset["status"], "asset_count": asset["asset_count"], "failures": len(asset["failures"])},
        "interpretation": f"{total - pending}/{total} claim 条目已有支持或明确边界；Fig.1--5 静态图通过，Fig.6--8 动态级别仍受 CV/TEBD 门约束；这不是论文完成率。",
    }
    OUT.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {"title": TITLE, "note": "由本地 claim matrix、图件 manifest、delivery audit 和资产 QA 自动汇总；不连接服务器。", "blocks": [{"kind": "verdict", "status": "warn" if dashboard["delivery_gates"]["status"] != "READY" else "good", "label": dashboard["delivery_gates"]["status"], "why": dashboard["interpretation"]}, {"kind": "table", "columns": ["层级", "当前值", "解释"], "rows": [["主张证据", f"{total-pending}/{total}", "已支持或有明确边界"], ["参考图件", f"{static_ready}/5 静态；{dynamic_not_production}/3 动态待生产", "Fig.6--8 不提前升级"], ["交付门", f"{dashboard['delivery_gates']['passed']}/{dashboard['delivery_gates']['total']}", "剩余门槛依赖动态交叉验收"], ["导出资产", f"{asset['asset_count']} 个，失败 {len(asset['failures'])}", "哈希与分辨率审计"]]}, {"kind": "note", "label": "边界", "style": "pending", "text": "范围固定为 0<=alpha,beta<=1；不纳入负 alpha 和 Fig.9。仪表盘只汇总证据状态，不替代物理结论或服务器终态。"}]}
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(1, section)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": dashboard["delivery_gates"]["status"], "claims": f"{total-pending}/{total}", "asset_count": asset["asset_count"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
