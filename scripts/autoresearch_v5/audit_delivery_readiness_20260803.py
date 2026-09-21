"""审计 8/10 HTML 与可复算证据包的就绪程度。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "research_progress" / "delivery_readiness_audit_20260803.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def exists(relative: str) -> bool:
    return (ROOT / relative).is_file()


def load_json(relative: str) -> dict[str, object]:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def main() -> None:
    phase = load_json("results/research_progress/positive_phase_audit_20260803.json")
    cv = load_json("results/research_progress/l40_cv_triplet_recheck_20260803.json")
    pilot = load_json("results/research_progress/positive_tebd_pilot_audit_20260803.json")
    tebd = load_json("results/research_progress/tebd_readiness_audit_20260803.json")
    diagnostic = load_json("results/research_progress/l80_anchor_diagnostic_20260803_0953.json")
    anchor_validator_path = "results/research_progress/l80_anchor_validator_20260803.json"
    anchor_validator = load_json(anchor_validator_path) if exists(anchor_validator_path) else {}
    tebd_crosscheck_path = "results/autoresearch_v5_20260803/round30_qpi_maxdim96_analysis/summary.json"
    tebd_crosscheck = load_json(tebd_crosscheck_path) if exists(tebd_crosscheck_path) else {}
    cv_tebd_path = "results/autoresearch_v5_20260804/round39_cv_tebd_accepted6_analysis/cross-method-check.json"
    cv_tebd = load_json(cv_tebd_path) if exists(cv_tebd_path) else {}

    required_files = [
        "results/research_progress/report.json",
        "results/research_progress/report.html",
        "results/research_progress/local_integrity_audit_20260803.json",
        "results/research_progress/computation_progress_standard_20260803.json",
        "results/research_progress/l80_anchor_diagnostic_20260803_0953.json",
        "results/research_progress/l80_anchor_diagnostic_20260803_1314.json",
        "results/research_progress/server_progress_snapshot_20260803_1314.json",
        "results/research_progress/figure_provenance_audit_20260803.json",
        "results/research_progress/tebd_handoff_audit_20260803.json",
        "results/research_progress/server_progress_snapshot_20260803_1351.json",
        "results/research_progress/l80_anchor_diagnostic_20260803_1351.json",
        anchor_validator_path,
        "docs/delivery_plan_to_20260810.md",
        "docs/pentamer_reproduction_standard.md",
        "docs/claim_evidence_matrix.md",
        "docs/figure_plan.md",
        "figures/positive_region_evidence_20260803.svg",
        "figures/positive_region_evidence_20260803.pdf",
        "figures/positive_tebd_pilot_audit_20260803.svg",
        "figures/positive_tebd_pilot_audit_20260803.pdf",
    ]
    required_ok = all(exists(path) for path in required_files)
    phase_ok = (
        phase.get("scope", {}).get("negative_alpha_included") is False
        and phase.get("guard", {}).get("status") == "NO_SIGNIFICANT_CROSSING"
        and phase.get("records", {}).get("merged_success") == 105
        and phase.get("records", {}).get("internal_difference_not_significant") == 0
    )
    cv_ok = cv.get("status") == "pass" and all(bool(value) for value in cv.get("checks", {}).values())
    pilot_ok = pilot.get("status") == "pilot_only" and pilot.get("scope", {}).get("negative_alpha_included") is False
    tebd_ready = tebd.get("status") == "READY_TO_START_AFTER_ANCHOR" and all(
        bool(value) for value in tebd.get("checks", {}).values()
    )
    diagnostic_ok = (
        diagnostic.get("diagnosis") == "active_compute_not_stuck"
        and str(diagnostic.get("evidence", {}).get("process_state", "")).startswith("R")
        and diagnostic.get("evidence", {}).get("code_hash_matches_run_config") is True
    )
    anchor_terminal = anchor_validator.get("status") == "pass" and all(
        bool(value) for value in anchor_validator.get("checks", {}).values()
    )
    tebd_crosscheck_terminal = (
        tebd_crosscheck.get("status") == "pass"
        and tebd_crosscheck.get("qpi_production_status") == "pass"
        and all(bool(value) for value in tebd_crosscheck.get("gates", {}).values())
    )
    cv_tebd_terminal = cv_tebd.get("status") == "pass" and cv_tebd.get("tag") == "Agreement"
    dynamic_pending = not (anchor_terminal and tebd_crosscheck_terminal and cv_tebd_terminal)
    checks = {
        "required_files": required_ok,
        "positive_phase_audit": phase_ok,
        "cv_l40_recheck": cv_ok,
        "positive_tebd_pilot_audit": pilot_ok,
        "tebd_production_ready_after_anchor": tebd_ready,
        "l80_runtime_diagnosis": diagnostic_ok,
        "l80_anchor_terminal": anchor_terminal,
        "tebd_crosscheck_terminal": tebd_crosscheck_terminal,
        "final_dynamic_claim_gate": not dynamic_pending,
    }
    source_files = required_files + [
        "results/research_progress/positive_phase_audit_20260803.json",
        "results/research_progress/positive_tebd_pilot_audit_20260803.json",
        "results/research_progress/tebd_readiness_audit_20260803.json",
        "results/research_progress/l80_anchor_diagnostic_20260803_0953.json",
        "results/research_progress/l40_cv_triplet_recheck_20260803.json",
        "results/research_progress/local_integrity_audit_20260803.json",
        "results/research_progress/computation_progress_standard_20260803.json",
        "results/research_progress/l80_anchor_diagnostic_20260803_1314.json",
        "results/research_progress/server_progress_snapshot_20260803_1314.json",
        "results/research_progress/figure_provenance_audit_20260803.json",
        "results/research_progress/tebd_handoff_audit_20260803.json",
        "results/research_progress/server_progress_snapshot_20260803_1351.json",
        "results/research_progress/l80_anchor_diagnostic_20260803_1351.json",
        anchor_validator_path,
    ]
    if exists(tebd_crosscheck_path):
        source_files.append(tebd_crosscheck_path)
    if exists(cv_tebd_path):
        source_files.append(cv_tebd_path)
    result = {
        "schema_version": 1,
        "created_at": "2026-08-03",
        "status": "PARTIAL_READY" if required_ok and phase_ok and cv_ok and pilot_ok and tebd_ready and diagnostic_ok else "NOT_READY",
        "scope": {"alpha_min": 0.0, "beta_min": 0.0, "negative_alpha_included": False, "fig9_included": False},
        "checks": checks,
        "completed_evidence": [
            "静态机制、有效理论和有限尺寸证据已登记",
            "105 条正区记录和 56 个内部尺寸差通过 guard 复核",
            "L=40 CV 三频点现场重验通过",
            "正区 TEBD pilot 已完成限制性审计并生成图表",
            "TEBD 生产配置与 raw-spectrum 分离检查通过",
            "L=80 CV anchor 已回传，manifest、checksum 和 CV residual 通过",
            "L=40 q=pi TEBD 的 dt、时间窗和 96/320 键维交叉通过",
        ],
        "pending_evidence": [
            *([] if anchor_terminal else ["L=80 omega=0.25 anchor 终态、manifest、checksum 和 CV residual"]),
            *([] if tebd_crosscheck_terminal else ["L=40 dt/dt2 TEBD 原始谱、时间窗和键维交叉验收"]),
            *([] if cv_tebd_terminal else ["CV/TEBD 主峰覆盖和 0--1.5 积分权重交叉门槛"]),
        ],
        "source_sha256": {path: sha256(ROOT / path) for path in source_files if exists(path)},
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "checks_passed": sum(checks.values()), "checks_total": len(checks)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
