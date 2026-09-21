#!/usr/bin/env python3
"""测试 Stage C 全通过与首失败终态组装。"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import stage_negative_phase_stage_c_terminal as target
from ingest_negative_phase_r6 import load, sha256, write_json


ROOT = Path(__file__).resolve().parents[2]


def make_fixture(root: Path, fail_at: int | None) -> tuple[Path, Path, Path, Path, Path]:
    fetch, phase, stage = root / "fetch", root / "phase", root / "stage"
    fetch.mkdir(parents=True)
    phase.mkdir()
    stage.mkdir()
    stage_b_summary = phase / "stage_b_r1_terminal_summary.json"
    write_json(stage_b_summary, {"status": "accepted_stage_b_complete"})
    cells, actions = [], []
    for index, (alpha, length) in enumerate(((-0.35, 80), (-0.30, 40), (-0.30, 60),
                                              (-0.30, 80), (-0.25, 80))):
        cell_id, action_id = f"cell-{index:03d}", f"act-{index:03d}"
        params = {"alpha": alpha, "beta": 0.5, "L": length, "n_units": length // 5}
        budget = 64 if length < 80 else 128
        cells.append({"cell_id": cell_id, "params": params, "budget": budget,
                      "controller_action_id": action_id})
        actions.append({"action_id": action_id, "params": params,
                        "budget": budget, "boundary_thresholds_relaxed": False})
        if fail_at is not None and index > fail_at:
            continue
        cell_dir = fetch / "cells" / cell_id
        cell_dir.mkdir(parents=True)
        write_json(fetch / "receipts" / f"{cell_id}.json",
                   {"status": "pass", "cell_id": cell_id, "non_clobbering": True})
        if index == fail_at:
            write_json(cell_dir / "manifest.json", {"cell_id": cell_id, "status": "failed"})
            write_json(fetch / "validation" / f"{cell_id}.json",
                       {"status": "fail", "cell_id": cell_id,
                        "checks": {"terminal": False}, "failures": ["synthetic variance failure"]})
            continue
        write_json(cell_dir / "manifest.json", {
            "cell_id": cell_id, "status": "success", "accepted": True,
            "params": params, "settings": {"nsweeps": budget},
            "observables": {
                "dominant_structure_factor_ratio": {"value": 0.2 + index / 100, "error": 1e-4},
                "structure_factor_peak_q_over_pi": {"value": 0.6 if alpha < -0.3 else 1.0},
            },
            "provenance": {"fixture": True},
        })
        write_json(fetch / "validation" / f"{cell_id}.json",
                   {"status": "pass", "cell_id": cell_id,
                    "checks": {"terminal": True, "checksums": True}, "failures": []})
    analysis_path = phase / "stage_b_cross_slice_diagnostic.json"
    write_json(analysis_path, {"status": "action_required", "stage_c_actions": actions})
    spec_path = stage / "parameter-scan.run_spec.json"
    write_json(spec_path, {"cells": cells, "provenance": {
        "stage_b_summary_sha256": sha256(stage_b_summary),
        "stage_b_analysis_sha256": sha256(analysis_path),
    }})
    contract_path = stage / "launch-contract.json"
    write_json(contract_path, {"launch_ready": True, "stage_b_complete": True,
                               "run_spec_sha256": sha256(spec_path),
                               "stage_b_analysis_sha256": sha256(analysis_path)})
    return fetch, phase, spec_path, analysis_path, contract_path


def run_case(fail_at: int | None) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="stage-c-terminal-test-", dir=ROOT / "results") as name:
        fetch, phase, spec, analysis, contract = make_fixture(Path(name), fail_at)
        old = sys.argv
        try:
            sys.argv = ["stage_negative_phase_stage_c_terminal.py", "--fetch-dir", str(fetch),
                        "--run-spec", str(spec), "--analysis", str(analysis),
                        "--launch-contract", str(contract), "--phase-dir", str(phase)]
            assert target.main() == 0
        finally:
            sys.argv = old
        summary = load(phase / "stage_c_r1_terminal_summary.json")
        assert not summary["failed_records_contain_value_or_error"]
        return json.loads(json.dumps(summary))


def main() -> int:
    complete = run_case(None)
    assert complete["status"] == "accepted_stage_c_round_complete"
    assert complete["counts"] == {"success": 5, "failed": 0, "pending": 0}
    assert complete["next_analysis_ready"] is True
    partial = run_case(2)
    assert partial["status"] == "partial_failure"
    assert partial["counts"] == {"success": 2, "failed": 1, "pending": 2}
    assert partial["next_analysis_ready"] is False
    print("stage_c_terminal_tests PASS 2/2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
