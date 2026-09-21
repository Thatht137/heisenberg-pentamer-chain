#!/usr/bin/env python3
"""生成主张、图件与复现文档的源数据清单。"""

from __future__ import annotations

import hashlib
import json
import csv
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/research_progress/source_data_inventory_20260804.json"
OUT_MD = ROOT / "results/research_progress/source_data_inventory_20260804.md"
OUT_SHA = ROOT / "results/research_progress/source_data_checksums_20260804.sha256"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    static = read_json(ROOT / "results/research_progress/paper_static_figures_manifest_20260804.json")
    high_dir = ROOT / "results/autoresearch_v5_20260805/round40_qpi_cv_high150_fetch/cell-l40-qpi-high-150"
    anchor_dir = ROOT / "results/autoresearch_v5_20260805/round40_qpi_cv_anchor_assembly_accepted"
    cross_dir = ROOT / "results/autoresearch_v5_20260805/round40_cv_tebd_accepted7_analysis"
    low_dir = ROOT / "results/autoresearch_v5_20260805/round41_qpi_cv_low005_retry_fetch_20260805_2212/cell-l40-qpi-retry-005"
    fig8_base = ROOT / "figures/paper_fig8_bounded_cv_tebd_20260805"
    round43 = ROOT / "results/autoresearch_v5_20260806/round43_handoff_final_v2"
    round43_fig8 = ROOT / "figures/round43_fig8_final_20260806_v2"
    paths = {
        ROOT / "docs/claim_evidence_matrix.md",
        ROOT / "docs/figure_plan.md",
        ROOT / "docs/delivery_plan_to_20260810.md",
        ROOT / "docs/supplementary_materials_plan_20260804.md",
        ROOT / "docs/reproducibility_commands_20260804.md",
        ROOT / "docs/local_delivery_manifest_20260804.md",
        ROOT / "docs/pentamer_reproduction_standard.md",
        ROOT / "docs/dynamic_figure_contract.example.json",
        ROOT / "results/research_progress/research_completion_dashboard_20260804.json",
        ROOT / "results/research_progress/cv_sparse_anchor_table_20260804.csv",
        ROOT / "results/research_progress/cv_sparse_anchor_table_20260804.json",
        ROOT / "results/research_progress/qpi_cv_extension_remote_snapshot_20260804_now.json",
        ROOT / "results/research_progress/round41_qpi_cv_low005_validator_20260805.json",
        ROOT / "results/research_progress/round41_qpi_cv_low005_fetch_receipt_20260805.json",
        ROOT / "results/research_progress/round41_qpi_cv_low005_terminal_assessment_20260805.json",
        ROOT / "results/research_progress/round31_high150_terminal_check_20260805_2053.json",
        ROOT / "results/research_progress/round31_high150_fetch_receipt_20260805.json",
        ROOT / "results/research_progress/round31_high150_validator_20260805.json",
        ROOT / "results/research_progress/round41_low005_retry_fetch_receipt_20260805.json",
        ROOT / "results/research_progress/round41_low005_retry_validator_20260805.json",
        ROOT / "results/research_progress/dynamic_gate_freeze_20260805.json",
        ROOT / "results/research_progress/bounded_delivery_audit_20260805.json",
        ROOT / "results/research_progress/reproducibility_command_audit_20260805.json",
        ROOT / "results/research_progress/fig8_bounded_source_data_20260805.csv",
        ROOT / "scripts/autoresearch_v5/plot_paper_static_figures_20260804.py",
        ROOT / "scripts/autoresearch_v5/plot_dynamic_figures_production.py",
        ROOT / "scripts/autoresearch_v5/plot_fig8_bounded_seven_point_20260805.py",
        ROOT / "scripts/autoresearch_v5/assemble_qpi_cv_anchors.py",
        ROOT / "scripts/autoresearch_v5/validate_cv_run.py",
        ROOT / "scripts/autoresearch_v5/analyze_cv_tebd_crosscheck.py",
        ROOT / "scripts/autoresearch_v5/audit_bounded_delivery_20260805.py",
        ROOT / "scripts/autoresearch_v5/audit_reproducibility_commands_20260805.py",
        ROOT / "scripts/autoresearch_v5/build_source_data_inventory_20260804.py",
        ROOT / "scripts/autoresearch_v5/fetch_fullq_tebd_run.py",
        ROOT / "scripts/autoresearch_v5/validate_fullq_tebd_run.py",
        ROOT / "scripts/autoresearch_v5/finalize_minimal_fullq_handoff.py",
        ROOT / "scripts/autoresearch_v5/plot_minimal_fullq_campaign.py",
        ROOT / "scripts/autoresearch_v5/test_minimal_fullq_campaign.py",
        ROOT / "scripts/autoresearch_v5/audit_minimal_fullq_local_readiness.py",
        ROOT / "scripts/autoresearch_v5/update_minimal_fullq_campaign_report_20260807.py",
        ROOT / "results/research_progress/minimal_fullq_campaign_20260807/campaign_plan.json",
        ROOT / "results/research_progress/minimal_fullq_campaign_20260807/launch_campaign.sh",
        ROOT / "results/research_progress/minimal_fullq_campaign_status_20260807.json",
        round43 / "handoff_summary.json",
        round43 / "checksums.sha256",
        round43 / "accepted11/manifest.json",
        round43 / "cross_method/cross-method-check.json",
    }
    for item in static["figures"].values():
        paths.add(ROOT / item["sidecar"])
        paths.update(ROOT / output["path"] for output in item["outputs"].values())
    paths.update(high_dir / name for name in (
        "checksums.sha256", "manifest.json", "metrics.csv", "progress.json", "resource.log",
        "spectrum.csv", "spectrum.jld2", "status.json", "stderr.log", "stdout.log", "sweep_history.csv",
    ))
    paths.update(anchor_dir / name for name in ("checksums.sha256", "manifest.json", "spectrum.csv"))
    paths.update(cross_dir / name for name in ("cross-method-check.csv", "cross-method-check.json"))
    paths.update(Path(f"{fig8_base}{suffix}") for suffix in (".svg", ".pdf", ".png", ".tiff", ".sources.json"))
    paths.update(low_dir / name for name in (
        "checksums.sha256", "manifest.json", "metrics.csv", "progress.json", "resource.log",
        "spectrum.csv", "spectrum.jld2", "status.json", "stderr.log", "stdout.log", "sweep_history.csv",
    ))
    paths.update(Path(f"{round43_fig8}{suffix}") for suffix in (".svg", ".pdf", ".png", ".tiff", ".sources.json", ".qa.json", ".source.csv"))

    high = read_json(ROOT / "results/research_progress/round31_high150_validator_20260805.json")
    low = read_json(ROOT / "results/research_progress/round41_low005_retry_validator_20260805.json")
    anchor = read_json(anchor_dir / "manifest.json")
    sidecar = read_json(Path(f"{fig8_base}.sources.json"))
    with (anchor_dir / "spectrum.csv").open(encoding="utf-8", newline="") as handle:
        anchor_rows = list(csv.DictReader(handle))
    with (ROOT / "results/research_progress/fig8_bounded_source_data_20260805.csv").open(encoding="utf-8", newline="") as handle:
        fig8_rows = list(csv.DictReader(handle))
    anchor_sources = {str(row["source_run"]) for row in anchor_rows}
    low_token = "round41_qpi_cv_low005_retry_fetch_20260805_2212"
    checks = {
        "high150_accepted": high.get("status") == "pass" and bool(high.get("checks")) and all(high["checks"].values()),
        "accepted_anchor_seven_points": anchor.get("accepted") is True and anchor.get("acceptance", {}).get("status") == "pass" and len(anchor_rows) == 7 and anchor.get("params", {}).get("omega_points") == 7,
        "accepted_anchor_excludes_low005": low_token not in "\n".join(anchor_sources) and all(float(row["omega"]) != 0.05 for row in anchor_rows),
        "fig8_is_bounded": sidecar.get("status") == "bounded_seven_point_overlay" and sidecar.get("acceptance", {}).get("final_dynamic_claim_gate") is False,
        "fig8_marks_low005_rejected": len(fig8_rows) == 8 and sum(row["accepted"] == "True" for row in fig8_rows) == 7 and any(float(row["omega"]) == 0.05 and row["accepted"] == "False" for row in fig8_rows),
        "low005_rejected_audit_only": low.get("status") == "fail" and low.get("checks", {}).get("cv_residual") is False,
        "round43_qpi_production": read_json(round43 / "handoff_summary.json").get("production_ready") is True and read_json(round43 / "handoff_summary.json").get("tag") == "Agreement",
        "minimal_fullq_tooling_ready": all((ROOT / path).is_file() for path in (
            "scripts/autoresearch_v5/fetch_fullq_tebd_run.py",
            "scripts/autoresearch_v5/validate_fullq_tebd_run.py",
            "scripts/autoresearch_v5/finalize_minimal_fullq_handoff.py",
            "scripts/autoresearch_v5/plot_minimal_fullq_campaign.py",
            "scripts/autoresearch_v5/test_minimal_fullq_campaign.py",
        )),
    }

    evidence_sets = [
        {
            "id": "high150_accepted",
            "grade": "accepted_cv_point",
            "summary": "omega=1.50 已通过本地 validator，作为第七个 accepted-only CV 点。",
            "paths": [rel(high_dir / name) for name in ("checksums.sha256", "manifest.json", "spectrum.csv")] + [
                "results/research_progress/round31_high150_fetch_receipt_20260805.json",
                "results/research_progress/round31_high150_validator_20260805.json",
            ],
        },
        {
            "id": "accepted_only_anchor_7",
            "grade": "accepted_only",
            "summary": "七个频点 0.20, 0.25, 0.30, 0.35, 0.55, 1.00, 1.50；不含 low-005。",
            "paths": [rel(anchor_dir / name) for name in ("checksums.sha256", "manifest.json", "spectrum.csv")] + [rel(cross_dir / "cross-method-check.json")],
        },
        {
            "id": "fig8_bounded",
            "grade": "bounded_not_production",
            "summary": "Fig.8 仅呈现七点 overlay 与 low-005 失败标记；production dynamic gate=false。",
            "paths": [rel(Path(f"{fig8_base}{suffix}")) for suffix in (".svg", ".pdf", ".png", ".tiff", ".sources.json")] + [
                "results/research_progress/fig8_bounded_source_data_20260805.csv",
                "results/research_progress/dynamic_gate_freeze_20260805.json",
            ],
        },
        {
            "id": "low005_rejected",
            "grade": "rejected_audit_only",
            "summary": "omega=0.05 residual=1.1767005759300015e-5 > 1e-5；保留失败证据，禁止混入 accepted-only 或 production。",
            "excluded_from": ["accepted_only_anchor_7", "production_dynamic_claims"],
            "paths": [rel(low_dir / name) for name in ("checksums.sha256", "manifest.json", "spectrum.csv")] + [
                "results/research_progress/round41_low005_retry_fetch_receipt_20260805.json",
                "results/research_progress/round41_low005_retry_validator_20260805.json",
            ],
        },
        {
            "id": "round43_qpi_production",
            "grade": "production_agreement_bounded_scope",
            "summary": "accepted11、validator 与 peak/weight 门通过；Agreement 仅限 alpha=0.23,beta=0.5,L=40,q=pi。",
            "paths": [
                rel(round43 / "handoff_summary.json"),
                rel(round43 / "accepted11/manifest.json"),
                rel(round43 / "cross_method/cross-method-check.json"),
            ] + [rel(Path(f"{round43_fig8}{suffix}")) for suffix in (".svg", ".pdf", ".png", ".tiff", ".sources.json", ".qa.json", ".source.csv")],
        },
        {
            "id": "minimal_fullq_tooling",
            "grade": "tooling_ready_compute_pending",
            "summary": "六 cell 计划、非覆盖回传、独立 validator、dt/dt2 handoff 与四格式绘图已完成；真实 production 数据仍在计算。",
            "paths": [
                "results/research_progress/minimal_fullq_campaign_20260807/campaign_plan.json",
                "results/research_progress/minimal_fullq_campaign_status_20260807.json",
                "scripts/autoresearch_v5/fetch_fullq_tebd_run.py",
                "scripts/autoresearch_v5/validate_fullq_tebd_run.py",
                "scripts/autoresearch_v5/finalize_minimal_fullq_handoff.py",
                "scripts/autoresearch_v5/plot_minimal_fullq_campaign.py",
                "scripts/autoresearch_v5/test_minimal_fullq_campaign.py",
            ],
        },
    ]
    records = []
    for path in sorted(paths):
        records.append({
            "path": path.relative_to(ROOT).as_posix(),
            "exists": path.is_file(),
            "bytes": path.stat().st_size if path.is_file() else None,
            "sha256": sha256(path) if path.is_file() else None,
        })
    status = "pass" if all(item["exists"] for item in records) and all(checks.values()) else "incomplete"
    payload = {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": status,
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
        "acceptance_checks": checks,
        "evidence_sets": evidence_sets,
        "records": records,
        "dynamic_boundary": "Fig.8 同时保留 round43 q=pi production Agreement 与七点 bounded 对照；full-q Fig.6/7 仍等待六 run 和三组 dt/dt2 门。low-005 失败证据永久隔离。",
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Source-data inventory",
        "",
        f"状态：`{payload['status']}`；条目：{len(records)}。",
        "",
        "## 动态证据分级",
        "",
        "| 集合 | 分级 | 处理 |",
        "|---|---|---|",
    ]
    lines.extend(f"| `{item['id']}` | `{item['grade']}` | {item['summary']} |" for item in evidence_sets)
    lines.extend(["", "## 分离验收", "", "| 检查 | 结果 |", "|---|---|"])
    lines.extend(f"| `{name}` | `{'pass' if value else 'fail'}` |" for name, value in checks.items())
    lines.extend(["", "## 哈希清单", "", "| 路径 | 字节 | SHA-256 |", "|---|---:|---|"])
    lines.extend(f"| `{item['path']}` | {item['bytes'] if item['bytes'] is not None else '-'} | `{item['sha256'] or 'MISSING'}` |" for item in records)
    lines.extend(["", "> low-005 仅作为失败审计记录；它不属于 accepted11。round43 production 与七点 bounded Fig.8 独立保留，full-q 数据未终态前不得生成 production Fig.6/7。", ""])
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    OUT_SHA.write_text("".join(f"{item['sha256']}  {item['path']}\n" for item in records if item["exists"]), encoding="ascii")
    print(json.dumps({"status": payload["status"], "records": len(records), "checks": checks}, ensure_ascii=False))
    if payload["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
