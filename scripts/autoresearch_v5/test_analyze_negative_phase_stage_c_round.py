#!/usr/bin/env python3
"""测试 Stage C 再二分与最终释放判定。"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import analyze_negative_phase_stage_c_round as target
from ingest_negative_phase_r6 import load, sha256, write_json


ROOT = Path(__file__).resolve().parents[2]


def record(alpha: float, length: int, value: float, q: float) -> dict[str, object]:
    return {
        "params": {"alpha": alpha, "beta": 0.5, "L": length, "n_units": length // 5},
        "status": "success", "accepted_only": True, "boundary_eligible": True,
        "value": value, "error": 0.001,
        "diagnostics": {"q_peak_over_pi": {"value": q}},
    }


def run_case(target_width: float) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="stage-c-analysis-test-", dir=ROOT / "results") as name:
        root = Path(name)
        phase = root / "phase"
        phase.mkdir()
        initial = phase / "initial.json"
        write_json(initial, {
            "status": "action_required", "criteria": {"target_width": target_width, "sigma": 2.0},
            "slices": [{"beta": 0.5, "refinement_targets": [
                {"alpha": [-0.35, -0.25], "evidence": ["momentum_reconstruction",
                                                         "two_sigma_ratio_sign"]},
            ]}],
        })
        stage_a = phase / "stage_a.json"
        write_json(stage_a, {"records": []})
        stage_b = phase / "stage_b.json"
        write_json(stage_b, {"records": [
            record(-0.35, 60, 0.40, 0.60), record(-0.25, 60, 0.20, 1.00),
        ]})
        stage_c = phase / "stage_c.json"
        write_json(stage_c, {"records": [
            record(-0.35, 80, 0.35, 0.60),
            record(-0.30, 60, 0.32, 0.60), record(-0.30, 80, 0.29, 0.60),
            record(-0.25, 80, 0.24, 1.00),
        ]})
        summary = phase / "summary.json"
        write_json(summary, {
            "status": "accepted_stage_c_round_complete", "next_analysis_ready": True,
            "observations": {"sha256": sha256(stage_c)},
            "boundary_thresholds_relaxed": False,
        })
        output = phase / "output.json"
        old = sys.argv
        try:
            sys.argv = ["analyze_negative_phase_stage_c_round.py",
                        "--phase-dir", str(phase), "--initial-analysis", str(initial),
                        "--stage-a-observations", str(stage_a),
                        "--stage-b-observations", str(stage_b),
                        "--stage-c-summary", str(summary),
                        "--stage-c-observations", str(stage_c),
                        "--output", str(output)]
            assert target.main() == 0
        finally:
            sys.argv = old
        return load(output)


def main() -> int:
    refine = run_case(0.025)
    assert refine["status"] == "refinement_required"
    assert refine["counts"] == {"targets": 1, "confirmed": 0,
                                "unresolved": 1, "next_actions": 2}
    assert {row["params"]["alpha"] for row in refine["next_actions"]} == {-0.275}
    assert {row["params"]["L"] for row in refine["next_actions"]} == {60, 80}
    final = run_case(0.05)
    assert final["status"] == "stage_d_ready"
    assert final["counts"] == {"targets": 1, "confirmed": 1,
                               "unresolved": 0, "next_actions": 0}
    assert final["decision"]["stage_d_ready"] is True
    print("stage_c_analysis_tests PASS 2/2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
