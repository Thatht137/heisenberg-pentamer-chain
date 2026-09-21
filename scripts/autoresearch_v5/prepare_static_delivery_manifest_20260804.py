# -*- coding: utf-8 -*-
"""登记 Fig.1–5 静态证据包，不包含未完成动态结果。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROGRESS = ROOT / "results/research_progress"
OUT = PROGRESS / "static_delivery_manifest_20260804.json"
REPORT = PROGRESS / "report.json"
TITLE = "2026-08-04 静态证据包交付预检"


REQUIRED = [
    "docs/pentamer_reproduction_standard.md",
    "docs/claim_evidence_matrix.md",
    "docs/figure_plan.md",
    "docs/delivery_plan_to_20260810.md",
    "figures/reference_aligned_fig1_pentamer_20260803.svg",
    "figures/reference_aligned_fig1_pentamer_20260803.pdf",
    "figures/reference_aligned_fig1_pentamer_20260803.png",
    "figures/reference_aligned_fig1_pentamer_20260803.tiff",
    "figures/reference_aligned_fig2_pentamer_positive_20260803.svg",
    "figures/reference_aligned_fig2_pentamer_positive_20260803.pdf",
    "figures/reference_aligned_fig2_pentamer_positive_20260803.png",
    "figures/reference_aligned_fig2_pentamer_positive_20260803.tiff",
    "figures/reference_aligned_fig3_pentamer_positive_20260803.svg",
    "figures/reference_aligned_fig3_pentamer_positive_20260803.pdf",
    "figures/reference_aligned_fig3_pentamer_positive_20260803.png",
    "figures/reference_aligned_fig3_pentamer_positive_20260803.tiff",
    "figures/reference_aligned_fig4_pentamer_positive_20260803.svg",
    "figures/reference_aligned_fig4_pentamer_positive_20260803.pdf",
    "figures/reference_aligned_fig4_pentamer_positive_20260803.png",
    "figures/reference_aligned_fig4_pentamer_positive_20260803.tiff",
    "figures/pentamer_model_effective_chain_20260731.svg",
    "figures/pentamer_model_effective_chain_20260731.pdf",
    "figures/pentamer_model_effective_chain_20260731.png",
    "figures/pentamer_model_effective_chain_20260731.tiff",
    "figures/pentamer_momentum_filter_20260731.svg",
    "figures/pentamer_momentum_filter_20260731.pdf",
    "figures/pentamer_momentum_filter_20260731.png",
    "figures/pentamer_momentum_filter_20260731.tiff",
    "figures/reference_aligned_figures_20260803.sources.json",
    "figures/reference_aligned_fig3_pentamer_positive_20260803.sources.json",
    "figures/reference_aligned_fig4_pentamer_positive_20260803.sources.json",
    "figures/pentamer_model_effective_chain_20260731.sources.json",
    "figures/pentamer_momentum_filter_20260731.sources.json",
    "results/research_progress/figure_claim_matrix_audit_20260804.json",
    "results/research_progress/figure_caption_claim_audit_20260804.json",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    records = []
    missing = []
    for relative in REQUIRED:
        path = ROOT / relative
        if not path.is_file():
            missing.append(relative)
            continue
        records.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path)})
    result = {
        "schema_version": 1,
        "created_at": "2026-08-04T10:40:00+08:00",
        "status": "ready_static_only" if not missing else "missing_files",
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
        "included_figures": ["Fig. 1", "Fig. 2", "Fig. 3", "Fig. 4", "Fig. 5"],
        "excluded_pending": ["Fig. 6", "Fig. 7", "Fig. 8", "Fig. 9", "negative alpha"],
        "files": records,
        "report_artifact": {"path": "results/research_progress/report.html", "self_referential_hash_excluded": True, "reason": "报告包含本 manifest 的链接，不能纳入自身哈希闭环"},
        "missing": missing,
        "checks": {"all_files_present": not missing, "all_hashes_recorded": len(records) == len(REQUIRED), "dynamic_gate_closed": False},
        "delivery_boundary": "可作为静态机制、有限尺寸和纠缠证据包；不包含生产 CV/TEBD 动态结论。",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = json.loads(REPORT.read_text(encoding="utf-8-sig"))
    section = {
        "title": TITLE,
        "note": "只登记本地静态文件与哈希，不复制、不压缩、不修改 paper/。",
        "blocks": [
            {"kind": "verdict", "status": "good" if result["status"] == "ready_static_only" else "bad", "label": "静态证据包可独立交付" if result["status"] == "ready_static_only" else "静态证据包缺文件", "why": f"登记 {len(records)}/{len(REQUIRED)} 个文件；Fig.1–5 可复核，动态门仍保持关闭。"},
            {"kind": "table", "columns": ["组件", "状态", "边界"], "rows": [["标准与计划", "已登记", "只含正区范围"], ["Fig.1–5 导出", "已登记", "静态/有边界结论"], ["来源与 claim 审计", "已登记", "哈希可复核"], ["CV/TEBD 动态", "排除", "等待远端终态与交叉门"]]},
            {"kind": "kv", "pairs": [["Manifest", "results/research_progress/static_delivery_manifest_20260804.json"], ["文件数", f"{len(records)}/{len(REQUIRED)}"], ["可交付级别", "静态证据包；不是最终论文完成声明"]]},
            {"kind": "note", "label": "验收边界", "style": "pending", "text": "只有 L=80 CV、TEBD dt/dt2 和 CV–TEBD 主峰/权重门全部通过后，才把 Fig.6–8 纳入 production 动态包。"},
        ],
    }
    report["sections"] = [item for item in report["sections"] if item.get("title") != TITLE]
    report["sections"].insert(2, section)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "files": len(records), "missing": len(missing)}, ensure_ascii=False))
    if missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
