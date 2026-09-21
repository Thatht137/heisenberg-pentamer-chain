#!/usr/bin/env python3
"""测试最终相图四格式输出与 QA。"""

from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

import plot_final_full_alpha_phase_diagram as target
from ingest_negative_phase_r6 import load, write_json


ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="stage-d-plot-test-", dir=ROOT / "results") as name:
        root = Path(name)
        source, boundaries, decision = root / "source.csv", root / "boundaries.csv", root / "decision.json"
        fields = ["alpha", "beta", "L", "value", "error", "q_peak_over_pi", "region",
                  "classification", "evidence_tier", "budget", "artifact", "validation_sha256"]
        with source.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for beta in (0.1, 0.5, 0.9):
                writer.writerow({"alpha": -0.5, "beta": beta, "L": 80, "value": 0.2,
                                 "error": 0.001, "q_peak_over_pi": 0.6,
                                 "region": "candidate_ic_critical", "classification": "dual",
                                 "evidence_tier": "stage_c", "budget": 128, "artifact": "a", "validation_sha256": "x"})
                writer.writerow({"alpha": -0.25, "beta": beta, "L": 80, "value": 0.3,
                                 "error": 0.001, "q_peak_over_pi": 1.0,
                                 "region": "candidate_commensurate_critical", "classification": "dual",
                                 "evidence_tier": "stage_c", "budget": 128, "artifact": "b", "validation_sha256": "y"})
                writer.writerow({"alpha": 0.5, "beta": beta, "L": 80, "value": 0.3,
                                 "error": 0.001, "q_peak_over_pi": "",
                                 "region": "qpi_gapless_af", "classification": "strict_positive",
                                 "evidence_tier": "positive", "budget": 64, "artifact": "c", "validation_sha256": ""})
        boundary_fields = ["beta", "alpha_left", "alpha_right", "alpha_mid", "width",
                           "status", "evidence", "dual_diagnostic"]
        with boundaries.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=boundary_fields)
            writer.writeheader()
            for beta, mid in ((0.1, -0.31), (0.5, -0.2875), (0.9, -0.27)):
                writer.writerow({"beta": beta, "alpha_left": mid - 0.0125,
                                 "alpha_right": mid + 0.0125, "alpha_mid": mid, "width": 0.025,
                                 "status": "confirmed_candidate_boundary",
                                 "evidence": "momentum_reconstruction+two_sigma_ratio_sign",
                                 "dual_diagnostic": True})
        write_json(decision, {"status": "complete"})
        prefix = root / "final_full_alpha_phase_diagram"
        old = sys.argv
        try:
            sys.argv = ["plot_final_full_alpha_phase_diagram.py", "--source", str(source),
                        "--boundaries", str(boundaries), "--decision", str(decision),
                        "--output-prefix", str(prefix)]
            assert target.main() == 0
        finally:
            sys.argv = old
        for suffix in ("svg", "pdf", "png", "tiff", "sources.json", "qa.json"):
            assert prefix.with_suffix("." + suffix).is_file()
        qa = load(prefix.with_suffix(".qa.json"))
        assert qa["status"] == "pass" and all(qa["checks"].values())
    print("stage_d_plot_tests PASS 1/1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
