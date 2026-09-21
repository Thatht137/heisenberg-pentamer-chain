#!/usr/bin/env python3
"""测试 Stage D accepted-only 合并与 source manifest。"""

from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

import finalize_full_alpha_phase_diagram as target
from ingest_negative_phase_r6 import load, sha256, write_json


ROOT = Path(__file__).resolve().parents[2]


def row(alpha: float, beta: float, length: int, accepted: bool = True) -> dict[str, object]:
    result = {
        "params": {"alpha": alpha, "beta": beta, "L": length, "n_units": length // 5},
        "status": "success", "value": 0.2, "error": 0.001, "budget": 64,
        "artifact": f"fixture-{alpha}-{beta}-{length}.json",
        "diagnostics": {"q_peak_over_pi": {"value": 0.6 if alpha < -0.3 else 1.0}},
    }
    if alpha < 0:
        result["accepted_only"] = accepted
        result["boundary_eligible"] = True
    return result


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="stage-d-test-", dir=ROOT / "results") as name:
        root = Path(name)
        decision, stage_a, stage_b, stage_c, positive = [root / filename for filename in (
            "decision.json", "stage_a.json", "stage_b.json", "stage_c.json", "positive.json")]
        write_json(decision, {
            "status": "stage_d_ready", "next_actions": [],
            "decision": {"stage_d_ready": True, "boundary_thresholds_relaxed": False},
            "decisions": [{
                "beta": 0.5, "status": "confirmed_candidate_boundary",
                "selected": {"alpha": [-0.30, -0.275], "width": 0.025,
                             "evidence": ["momentum_reconstruction", "two_sigma_ratio_sign"],
                             "dual_diagnostic": True},
            }],
        })
        write_json(stage_a, {"records": [row(-0.5, 0.5, 60), row(-0.25, 0.5, 60)]})
        write_json(stage_b, {"records": []})
        write_json(stage_c, {"records": [row(-0.275, 0.5, 80), row(-0.4, 0.5, 40, False)]})
        write_json(positive, {"records": [row(0.5, 0.5, 60), row(0.0, 0.5, 60)]})
        output = root / "output"
        old = sys.argv
        try:
            sys.argv = ["finalize_full_alpha_phase_diagram.py", "--decision", str(decision),
                        "--stage-a", str(stage_a), "--stage-b", str(stage_b),
                        "--stage-c", str(stage_c), "--positive", str(positive),
                        "--output-dir", str(output)]
            assert target.main() == 0
        finally:
            sys.argv = old
        final = load(output / "full_alpha_phase_decision.json")
        manifest = load(output / "full_alpha_phase_source_manifest.json")
        with (output / "full_alpha_phase_diagram.source.csv").open(encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        assert final["status"] == "complete"
        assert final["strict_second_thermodynamic_phase_confirmed"] is True
        assert len(rows) == 5
        assert not any(row["artifact"] == "fixture--0.4-0.5-40.json" for row in rows)
        assert manifest["status"] == "pass" and manifest["accepted_only_negative"] is True
        for item in manifest["outputs"]:
            assert sha256(ROOT / item["artifact"]) == item["sha256"]
    print("stage_d_finalize_tests PASS 1/1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
