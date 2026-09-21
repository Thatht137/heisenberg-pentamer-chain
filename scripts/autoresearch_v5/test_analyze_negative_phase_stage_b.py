#!/usr/bin/env python3
"""测试 Stage B 跨切片 guard 与最小 Stage C 动作。"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import analyze_negative_phase_stage_b as target


ROOT = Path(__file__).resolve().parents[2]
ALPHAS = [-1.0, -0.75, -0.5, -0.35, -0.25, -0.1, -0.05, -0.025]
BETAS = [0.05, 0.1, 0.25, 0.75, 0.9, 1.0]


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return target.sha256(path)


def fixture(root: Path, complete: bool = True) -> tuple[Path, Path, Path, Path]:
    stage_a, stage_b, summary, output = (root / name for name in
                                         ("stage_a.json", "stage_b.json", "summary.json", "output.json"))
    alpha_summary = [{"alpha": alpha, "sizes": [40, 60, 80]} for alpha in ALPHAS]
    write(stage_a, {
        "status": "complete", "alpha_summary": alpha_summary,
        "candidate_ratio_sign_brackets": [{"alpha": [-0.35, -0.25]}],
        "candidate_q_brackets": [{"alpha": [-0.35, -0.25]}],
        "decision": {"stage_b_ready": True},
    })
    records = []
    for beta in BETAS:
        for alpha in ALPHAS:
            sign = -0.02 if alpha <= -0.35 else 0.02
            q = 0.6 if alpha <= -0.35 else 1.0
            for length in (40, 60):
                value = 0.3 + (sign if length == 60 else 0.0)
                records.append({
                    "params": {"alpha": alpha, "beta": beta, "L": length},
                    "status": "success", "value": value, "error": 1e-4,
                    "diagnostics": {"q_peak_over_pi": {"value": q}},
                })
    write(stage_b, {"records": records})
    counts = {"success": 96, "failed": 0, "pending": 0} if complete else {
        "success": 3, "failed": 1, "pending": 92}
    write(summary, {"status": "accepted_stage_b_complete" if complete else "partial_failure",
                    "counts": counts, "canonical_controller_mutated": False,
                    "observations": {"sha256": sha256(stage_b)}})
    return stage_a, stage_b, summary, output


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="stage-b-analysis-test-", dir=ROOT / "results") as name:
        stage_a, stage_b, summary, output = fixture(Path(name))
        old = sys.argv
        try:
            sys.argv = ["analyze_negative_phase_stage_b.py", "--stage-a", str(stage_a),
                        "--stage-b-summary", str(summary), "--stage-b-observations", str(stage_b),
                        "--output", str(output)]
            assert target.main() == 0
        finally:
            sys.argv = old
        result = json.loads(output.read_text(encoding="utf-8"))
        assert result["status"] == "action_required"
        assert result["counts"] == {"slices": 7, "refinement_targets": 7,
                                    "dual_diagnostic_targets": 7, "actions": 33}
        assert len({item["action_id"] for item in result["stage_c_actions"]}) == 33
        assert all(item["params"]["alpha"] in {-0.35, -0.3, -0.25}
                   for item in result["stage_c_actions"])
        assert all(item["budget"] in {64, 128} for item in result["stage_c_actions"])
    with tempfile.TemporaryDirectory(prefix="stage-b-analysis-gate-test-", dir=ROOT / "results") as name:
        stage_a, stage_b, summary, output = fixture(Path(name), complete=False)
        old = sys.argv
        try:
            sys.argv = ["analyze_negative_phase_stage_b.py", "--stage-a", str(stage_a),
                        "--stage-b-summary", str(summary), "--stage-b-observations", str(stage_b),
                        "--output", str(output)]
            try:
                target.main()
            except ValueError:
                pass
            else:
                raise AssertionError("Stage B partial 未被拒绝")
        finally:
            sys.argv = old
        assert not output.exists()
    print("stage_b_analysis_tests PASS 2/2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
