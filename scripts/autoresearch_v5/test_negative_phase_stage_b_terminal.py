#!/usr/bin/env python3
"""测试 Stage B 全通过与首失败终态组装。"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import stage_negative_phase_stage_b_terminal as target
from ingest_negative_phase_r6 import load, sha256, write_json


ROOT = Path(__file__).resolve().parents[2]


def make_fixture(root: Path, fail_at: int | None) -> tuple[Path, Path, Path, Path, Path]:
    fetch, phase, stage = root / "fetch", root / "phase", root / "stage"
    fetch.mkdir(parents=True)
    phase.mkdir()
    stage.mkdir()
    stage_a_summary = phase / "r19_success_ingestion_summary.json"
    stage_a_analysis = phase / "stage_a_finite_size_diagnostic_latest.json"
    stage_a_calibration = phase / "accepted_calibration_through_r19.json"
    write_json(stage_a_summary, {
        "status": "accepted_stage_a_complete",
        "counts": {"controller_success_total": 16, "controller_failed_total": 0,
                   "controller_pending_total": 0, "calibration_accepted_total": 8},
    })
    write_json(stage_a_analysis, {"status": "complete", "decision": {"stage_b_ready": True}})
    write_json(stage_a_calibration, {"records": [{"id": index} for index in range(8)]})
    cells, actions = [], []
    for index in range(96):
        beta = [0.05, 0.1, 0.25, 0.75, 0.9, 1.0][index // 16]
        slot = index % 16
        alpha = [-1.0, -0.75, -0.5, -0.35, -0.25, -0.1, -0.05, -0.025][slot // 2]
        length = [40, 60][slot % 2]
        budget = 32 if alpha <= -0.5 else 64
        cell_id, action_id = f"cell-{index:03d}", f"act-{index:03d}"
        params = {"alpha": alpha, "beta": beta, "L": length, "n_units": length // 5}
        cells.append({"cell_id": cell_id, "params": params, "budget": budget,
                      "controller_action_id": action_id})
        actions.append({"action_id": action_id, "params": params,
                        "observation_status": "pending", "accepted": False})
        if fail_at is not None and index > fail_at:
            continue
        cell_dir = fetch / "cells" / cell_id
        cell_dir.mkdir(parents=True)
        receipt = {"status": "pass", "cell_id": cell_id, "non_clobbering": True}
        write_json(fetch / "receipts" / f"{cell_id}.json", receipt)
        if index == fail_at:
            write_json(cell_dir / "manifest.json", {"cell_id": cell_id, "status": "failed"})
            write_json(fetch / "validation" / f"{cell_id}.json",
                       {"status": "fail", "cell_id": cell_id, "checks": {"terminal": False},
                        "failures": ["synthetic variance failure"]})
            continue
        write_json(cell_dir / "manifest.json", {
            "cell_id": cell_id, "status": "success", "accepted": True,
            "params": params, "settings": {"nsweeps": budget},
            "observables": {
                "dominant_structure_factor_ratio": {"value": 0.2 + index / 1000, "error": 1e-4},
                "structure_factor_peak_q_over_pi": {"value": 0.6},
            },
            "provenance": {"fixture": True},
        })
        write_json(fetch / "validation" / f"{cell_id}.json",
                   {"status": "pass", "cell_id": cell_id,
                    "checks": {"terminal": True, "checksums": True}, "failures": []})
    summary_sha, analysis_sha = sha256(stage_a_summary), sha256(stage_a_analysis)
    calibration_sha = sha256(stage_a_calibration)
    spec_path = stage / "parameter-scan.run_spec.json"
    plan_path = stage / "stage-b-action-plan.json"
    contract_path = stage / "launch-contract.json"
    write_json(spec_path, {"cells": cells, "provenance": {
        "r19_success_summary_sha256": summary_sha, "stage_a_analysis_sha256": analysis_sha,
        "accepted_calibration_through_r19_sha256": calibration_sha,
    }})
    write_json(plan_path, {"canonical_action_index_mutated": False, "actions": actions})
    write_json(contract_path, {"launch_ready": True, "stage_a_complete": True,
                               "run_spec_sha256": sha256(spec_path),
                               "action_plan_sha256": sha256(plan_path)})
    return fetch, phase, spec_path, plan_path, contract_path


def run_case(fail_at: int | None) -> dict[str, object]:
    results = ROOT / "results"
    with tempfile.TemporaryDirectory(prefix="stage-b-terminal-test-", dir=results) as name:
        fetch, phase, spec, plan, contract = make_fixture(Path(name), fail_at)
        old = sys.argv
        try:
            sys.argv = ["stage_negative_phase_stage_b_terminal.py", "--fetch-dir", str(fetch),
                        "--run-spec", str(spec), "--action-plan", str(plan),
                        "--launch-contract", str(contract), "--phase-dir", str(phase)]
            assert target.main() == 0
        finally:
            sys.argv = old
        summary = load(phase / "stage_b_r1_terminal_summary.json")
        observations = load(phase / "stage_b_r1_terminal_observations.json")
        assert len(observations["records"]) == 96
        assert not summary["failed_records_contain_value_or_error"]
        return json.loads(json.dumps(summary))


def main() -> int:
    complete = run_case(None)
    assert complete["status"] == "accepted_stage_b_complete"
    assert complete["counts"] == {"success": 96, "failed": 0, "pending": 0}
    assert complete["stage_c_ready"] is True
    partial = run_case(3)
    assert partial["status"] == "partial_failure"
    assert partial["counts"] == {"success": 3, "failed": 1, "pending": 92}
    assert partial["stage_c_ready"] is False
    print("stage_b_terminal_tests PASS 2/2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
