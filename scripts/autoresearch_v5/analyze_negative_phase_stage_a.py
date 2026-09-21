#!/usr/bin/env python3
"""分析负 alpha Stage A 的有限尺寸证据。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PHASE = ROOT / "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/phase-diagram-v2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase-dir", type=Path, default=DEFAULT_PHASE)
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_PHASE / "stage_a_finite_size_diagnostic_latest.json")
    return parser.parse_args()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def q_value(row: dict[str, Any]) -> float:
    q = row.get("diagnostics", {}).get("q_peak_over_pi")
    if isinstance(q, dict):
        q = q.get("value")
    return float(q)


def difference(high: dict[str, Any], low: dict[str, Any]) -> dict[str, float]:
    value = float(high["value"]) - float(low["value"])
    error = math.hypot(float(high["error"]), float(low["error"]))
    return {"value": value, "error": error, "sigma": abs(value) / error if error else math.inf}


def main() -> int:
    args = parse_args()
    phase = args.phase_dir.resolve()
    calibration_path = args.calibration.resolve() if args.calibration else next(
        path for path in (
            phase / "accepted_calibration_through_r19.json",
            phase / "accepted_calibration_through_r17.json",
            phase / "accepted_calibration_through_r16.json",
        ) if path.is_file()
    )
    observations_path = phase / "observations.json"
    actions_path = phase / "action_index.json"
    for path in (observations_path, actions_path, calibration_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    observations = load(observations_path).get("records", [])
    calibration = load(calibration_path).get("records", [])
    controller_counts = {name: sum(row.get("status") == name for row in observations)
                         for name in ("success", "failed", "pending")}
    accepted_controller = [row for row in observations if row.get("status") == "success"
                           and float(row["params"]["beta"]) == 0.5 and float(row["params"]["alpha"]) < 0]
    accepted_calibration = [row for row in calibration if row.get("status") == "success"
                            and float(row["params"]["beta"]) == 0.5 and float(row["params"]["alpha"]) < 0]
    indexed: dict[float, dict[int, dict[str, Any]]] = {}
    for row in accepted_controller + accepted_calibration:
        indexed.setdefault(float(row["params"]["alpha"]), {})[int(row["params"]["L"])] = row

    rows = []
    alpha_summary = []
    for alpha in sorted(indexed):
        by_size = indexed[alpha]
        q_values = [q_value(row) for row in by_size.values()]
        if q_values and all(abs(value - 1.0) <= 0.02 for value in q_values):
            momentum = "commensurate_qpi"
        elif q_values and max(q_values) < 0.9:
            momentum = "incommensurate"
        else:
            momentum = "size_sensitive_or_mixed"
        summary: dict[str, Any] = {
            "alpha": alpha,
            "sizes": sorted(by_size),
            "momentum_class": momentum,
            "q_span": max(q_values) - min(q_values) if q_values else None,
            "boundary_eligible_sizes": sorted(
                length for length, row in by_size.items() if row.get("boundary_eligible", True)
            ),
        }
        if 40 in by_size and 60 in by_size:
            summary["delta_R_60_40"] = difference(by_size[60], by_size[40])
        if 60 in by_size and 80 in by_size:
            summary["delta_R_80_60"] = difference(by_size[80], by_size[60])
        alpha_summary.append(summary)
        for length in sorted(by_size):
            row = by_size[length]
            rows.append({
                "alpha": alpha, "beta": 0.5, "L": length,
                "R": float(row["value"]), "R_error": float(row["error"]),
                "q_peak_over_pi": q_value(row),
                "boundary_eligible": bool(row.get("boundary_eligible", True)),
                "artifact": row.get("artifact", ""),
            })

    sign_brackets = []
    complete_deltas = [(item["alpha"], item["delta_R_60_40"])
                       for item in alpha_summary if "delta_R_60_40" in item]
    for (left_alpha, left), (right_alpha, right) in zip(complete_deltas, complete_deltas[1:]):
        if left["value"] * right["value"] < 0:
            sign_brackets.append({
                "alpha": [left_alpha, right_alpha], "width": right_alpha - left_alpha,
                "left": left, "right": right,
                "two_sigma": min(left["sigma"], right["sigma"]) >= 2.0,
                "final_pair_ready": False,
                "status": "candidate_not_boundary",
            })

    q_brackets = []
    for left, right in zip(alpha_summary, alpha_summary[1:]):
        left_q = [row["q_peak_over_pi"] for row in rows if row["alpha"] == left["alpha"]]
        right_q = [row["q_peak_over_pi"] for row in rows if row["alpha"] == right["alpha"]]
        if left_q and right_q and abs(sorted(left_q)[len(left_q) // 2] - sorted(right_q)[len(right_q) // 2]) >= 0.1:
            q_brackets.append({"alpha": [left["alpha"], right["alpha"]],
                               "width": right["alpha"] - left["alpha"],
                               "status": "candidate_momentum_reconstruction"})

    stage_a_complete = controller_counts == {"success": 16, "failed": 0, "pending": 0} and len(accepted_calibration) == 8
    result = {
        "schema_version": 1,
        "status": "complete" if stage_a_complete else "partial",
        "scope": {"alpha": [-1.0, -0.025], "beta": 0.5, "L": [40, 60, 80]},
        "inputs": {
            "observations": {"path": observations_path.relative_to(ROOT).as_posix(), "sha256": sha256(observations_path)},
            "calibration": {"path": calibration_path.relative_to(ROOT).as_posix(), "sha256": sha256(calibration_path)},
            "actions": {"path": actions_path.relative_to(ROOT).as_posix(), "sha256": sha256(actions_path)},
        },
        "counts": {"controller": controller_counts, "accepted_calibration": len(accepted_calibration)},
        "alpha_summary": alpha_summary,
        "candidate_ratio_sign_brackets": sign_brackets,
        "candidate_q_brackets": q_brackets,
        "decision": {
            "stage_a_complete": stage_a_complete,
            "phase_boundary_confirmed": False,
            "phase_label_assigned": False,
            "leading_hypothesis": "three bulk regimes plus alpha=0 singular line; negative-side Lifshitz boundary remains provisional",
            "stage_b_ready": stage_a_complete,
            "stage_c_required": bool(sign_brackets or q_brackets),
            "reason": "候选区间尚未达到0.025宽度且缺最终L60/L80 crossing",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    csv_path = args.output.with_suffix(".csv")
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["alpha", "beta", "L"])
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"status": result["status"], "rows": len(rows), "sign_brackets": len(sign_brackets),
                      "q_brackets": len(q_brackets), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
