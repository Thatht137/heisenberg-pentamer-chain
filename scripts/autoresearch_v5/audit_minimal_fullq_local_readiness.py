#!/usr/bin/env python3
"""审计精简 full-q 任务的本机准备状态。"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "results/research_progress/minimal_fullq_local_readiness_20260807.json"


def project_python() -> str:
    """优先使用项目虚拟环境，保证绘图依赖一致。"""
    candidate = ROOT / ".venv" / "Scripts" / "python.exe"
    return str(candidate) if candidate.is_file() else sys.executable


def main() -> None:
    required = [
        "scripts/autoresearch_v5/fetch_fullq_tebd_run.py",
        "scripts/autoresearch_v5/validate_fullq_tebd_run.py",
        "scripts/autoresearch_v5/finalize_minimal_fullq_handoff.py",
        "scripts/autoresearch_v5/plot_minimal_fullq_campaign.py",
        "scripts/autoresearch_v5/test_minimal_fullq_campaign.py",
        "scripts/autoresearch_v5/update_manuscript_draft_report_20260807.py",
        "results/research_progress/minimal_fullq_campaign_20260807/campaign_plan.json",
        "results/research_progress/minimal_fullq_campaign_20260807/launch_campaign.sh",
        "docs/reproducibility_commands_20260804.md",
        "docs/figure_plan.md",
        "docs/claim_evidence_matrix.md",
    ]
    files_present = all((ROOT / path).is_file() for path in required)
    campaign_path = ROOT / "results/research_progress/minimal_fullq_campaign_20260807/campaign_plan.json"
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    six_cells = len(campaign.get("cells", [])) == 6
    positive_scope = all(
        0.0 <= float(cell["alpha"]) <= 1.0 and 0.0 <= float(cell["beta"]) <= 1.0
        for cell in campaign.get("cells", [])
    )
    inventory = json.loads(
        (ROOT / "results/research_progress/source_data_inventory_20260804.json").read_text(encoding="utf-8")
    )
    inventory_pass = inventory.get("status") == "pass" and inventory.get("acceptance_checks", {}).get("minimal_fullq_tooling_ready") is True
    figure_text = (ROOT / "docs/figure_plan.md").read_text(encoding="utf-8")
    claim_text = (ROOT / "docs/claim_evidence_matrix.md").read_text(encoding="utf-8")
    docs_current = "round43" in figure_text and "production Agreement" in figure_text and "full-q" in claim_text
    test_python = project_python()
    test = subprocess.run(
        [test_python, "-m", "unittest", "scripts.autoresearch_v5.test_minimal_fullq_campaign"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    test_output = (test.stdout + "\n" + test.stderr).strip()
    checks = {
        "required_files": files_present,
        "six_pre_registered_cells": six_cells,
        "positive_scope_only": positive_scope,
        "source_inventory": inventory_pass,
        "documents_current": docs_current,
        "synthetic_e2e_tests": test.returncode == 0 and "Ran 6 tests" in test_output,
    }
    payload = {
        "schema_version": 1,
        "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "test_python": test_python,
        "test_summary": test_output.splitlines()[-4:],
        "local_work_complete": all(checks.values()),
        "compute_dependent_remaining": [
            "六个生产 full-q run 的终态数据",
            "三组真实 dt/dt2 交叉验收",
            "基于真实数据导出最终 Fig.6/7"
        ],
        "scope": {"alpha_beta": "[0,1]", "negative_alpha_excluded": True, "fig9_excluded": True},
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    if payload["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
