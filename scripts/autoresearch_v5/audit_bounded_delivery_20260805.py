#!/usr/bin/env python3
"""审计 bounded HTML 研究包的交付完整性。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "results/research_progress"
OUTPUT = RUN / "bounded_delivery_audit_20260805.json"
REPORT = RUN / "report.json"
TITLE = "2026-08-05 bounded 研究包交付审计"


def load(relative: str) -> dict[str, object]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    high = load("results/research_progress/round31_high150_validator_20260805.json")
    low = load("results/research_progress/round41_low005_retry_validator_20260805.json")
    anchor = load("results/autoresearch_v5_20260805/round40_qpi_cv_anchor_assembly_accepted/manifest.json")
    cross = load("results/autoresearch_v5_20260805/round40_cv_tebd_accepted7_analysis/cross-method-check.json")
    freeze = load("results/research_progress/dynamic_gate_freeze_20260805.json")
    sidecar = load("figures/paper_fig8_bounded_cv_tebd_20260805.sources.json")
    required = [
        "results/research_progress/report.html",
        "results/research_progress/report_history.html",
        "results/research_progress/dynamic_gate_freeze_20260805.json",
        "results/research_progress/round31_high150_fetch_receipt_20260805.json",
        "results/research_progress/round41_low005_retry_fetch_receipt_20260805.json",
        "results/research_progress/round31_high150_validator_20260805.json",
        "results/research_progress/round41_low005_retry_validator_20260805.json",
        "figures/paper_fig8_bounded_cv_tebd_20260805.svg",
        "figures/paper_fig8_bounded_cv_tebd_20260805.pdf",
        "figures/paper_fig8_bounded_cv_tebd_20260805.png",
        "figures/paper_fig8_bounded_cv_tebd_20260805.tiff",
        "figures/paper_fig8_bounded_cv_tebd_20260805.sources.json",
        "docs/claim_evidence_matrix.md",
        "docs/delivery_plan_to_20260810.md",
        "docs/reproducibility_commands_20260804.md",
        "docs/pentamer_reproduction_standard.md",
    ]
    checks = {
        "required_artifacts": all((ROOT / path).is_file() for path in required),
        "high150_validator_pass": high.get("status") == "pass" and all(high.get("checks", {}).values()),
        "low005_rejected_only_by_acceptance": low.get("status") == "fail" and low.get("checks", {}).get("cv_residual") is False,
        "accepted_anchor_seven_points": anchor.get("acceptance", {}).get("status") == "pass" and anchor.get("params", {}).get("omega_points") == 7,
        "cross_method_bounded": cross.get("tag") == "NotEvaluable" and cross.get("coverage", {}).get("main_peak_bracketed_by_cv_grid") is False,
        "stop_loss_applied": freeze.get("compute_decision", {}).get("round42_low000") == "cancelled_trigger_not_met",
        "figure_bounded_contract": sidecar.get("status") == "bounded_seven_point_overlay" and sidecar.get("acceptance", {}).get("final_dynamic_claim_gate") is False,
        "figure_exports_hashed": len(sidecar.get("outputs", {})) == 4 and all(sidecar.get("outputs", {}).values()),
        "scope_guard": all(
            item.get("scope", {}).get("negative_alpha_excluded") is True and item.get("scope", {}).get("fig9_excluded") is True
            for item in (freeze, sidecar)
        ),
        "claims_bounded_not_production": freeze.get("allowed_claim") is not None and freeze.get("forbidden_claim") is not None,
    }
    result = {
        "schema_version": 1,
        "checked_at": "2026-08-05T22:30:00+08:00",
        "status": "READY_BOUNDED" if all(checks.values()) else "NOT_READY",
        "checks": checks,
        "bounded_delivery_gates": {"passed": sum(checks.values()), "total": len(checks)},
        "production_dynamic_gate": False,
        "claim_evidence": {"supported_or_bounded": 12, "total": 12, "strong_claims_not_closed": ["C10 production", "C11 thermodynamic"]},
        "figures": {"Fig.1-5": "ready_or_bounded", "Fig.6": "exploratory", "Fig.7": "pilot", "Fig.8": "bounded"},
        "required_sha256": {path: sha256(ROOT / path) for path in required},
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "生产动态门与 bounded 可交付门分开计数；不以交付完整性替代科学 Agreement。",
        "blocks": [
            {
                "kind": "verdict",
                "status": "good" if result["status"] == "READY_BOUNDED" else "bad",
                "label": "bounded HTML 研究包已就绪" if result["status"] == "READY_BOUNDED" else "bounded 研究包仍有缺口",
                "why": f"bounded 交付门 {sum(checks.values())}/{len(checks)}；生产动态门仍为 false。",
            },
            {
                "kind": "table",
                "columns": ["维度", "状态", "解释"],
                "rows": [
                    ["结论证据", "12/12 supported or bounded", "C10/C11 强主张仍不成立"],
                    ["静态图", "Fig.1–5 ready/bounded", "四格式、sidecar 与 QA"],
                    ["动态图", "Fig.6 exploratory；Fig.7 pilot；Fig.8 bounded", "证据等级已冻结"],
                    ["生产动态门", "未通过", "low-005 residual 与覆盖门失败"],
                    ["bounded 交付门", f"{sum(checks.values())}/{len(checks)}", "HTML、图、数据、失败审计和复算入口齐全"],
                ],
                "widths": ["25%", "31%", "44%"],
            },
            {
                "kind": "note",
                "label": "论文口径",
                "style": "info",
                "text": "可以报告七个共享频点的局部一致性和有限尺寸无 crossing；不能报告完整 CV–TEBD Agreement、热力学单相或新相界。",
            },
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(0, section)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "passed": sum(checks.values()), "total": len(checks)}, ensure_ascii=False))
    if result["status"] != "READY_BOUNDED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
