#!/usr/bin/env python3
"""测试 Stage C 再二分计算包。"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import make_negative_phase_stage_c_next as target
from ingest_negative_phase_r6 import load, sha256, write_json


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="stage-c-next-test-", dir=ROOT / "results") as name:
        root = Path(name)
        analysis = root / "analysis.json"
        summary = root / "stage_b_summary.json"
        output = root / "stage-c-negative-refine-r2"
        actions = []
        for length in (60, 80):
            actions.append({
                "action_id": f"act-{length}",
                "params": {"alpha": -0.275, "beta": 0.5, "L": length,
                           "n_units": length // 5},
                "budget": 64 if length == 60 else 128,
                "stage": "C-R2-refine", "reason": "dual_diagnostic_bisection_to_width_0.025",
                "boundary_thresholds_relaxed": False,
            })
        write_json(analysis, {
            "status": "refinement_required", "round": 1, "next_actions": actions,
            "decision": {"boundary_thresholds_relaxed": False},
        })
        write_json(summary, {"status": "accepted_stage_b_complete"})
        old = sys.argv
        try:
            sys.argv = ["make_negative_phase_stage_c_next.py", "--analysis", str(analysis),
                        "--stage-b-summary", str(summary), "--round", "2",
                        "--output-dir", str(output)]
            assert target.main() == 0
        finally:
            sys.argv = old
        spec = load(output / "parameter-scan.run_spec.json")
        contract = load(output / "launch-contract.json")
        upload = load(output / "server_upload_manifest.json")
        assert len(spec["cells"]) == 2
        assert {cell["params"]["L"] for cell in spec["cells"]} == {60, 80}
        assert contract["run_spec_sha256"] == sha256(output / "parameter-scan.run_spec.json")
        assert contract["source_hashes_sha256"] == sha256(output / "stage_c_source_hashes.sha256")
        assert upload["cell_count"] == 2 and upload["remote_git_pull"] is False
        assert len({row["sha256"] for row in upload["files"]}) > 1
    print("stage_c_next_package_tests PASS 1/1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
