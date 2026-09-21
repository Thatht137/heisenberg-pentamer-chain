#!/usr/bin/env python3
"""汇总 Stage A/B，并生成 Stage C 最小精修动作。"""

from __future__ import annotations

import argparse
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
    parser.add_argument("--stage-a", type=Path, default=DEFAULT_PHASE / "stage_a_finite_size_diagnostic_latest.json")
    parser.add_argument("--stage-b-summary", type=Path, default=DEFAULT_PHASE / "stage_b_r1_terminal_summary.json")
    parser.add_argument("--stage-b-observations", type=Path,
                        default=DEFAULT_PHASE / "stage_b_r1_terminal_observations.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_PHASE / "stage_b_cross_slice_diagnostic.json")
    return parser.parse_args()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def q_value(row: dict[str, Any]) -> float:
    value = row.get("diagnostics", {}).get("q_peak_over_pi")
    if isinstance(value, dict):
        value = value.get("value")
    return float(value)


def delta(high: dict[str, Any], low: dict[str, Any]) -> dict[str, float]:
    value = float(high["value"]) - float(low["value"])
    error = math.hypot(float(high["error"]), float(low["error"]))
    return {"value": value, "error": error,
            "sigma": abs(value) / error if error else math.inf}


def action_id(beta: float, alpha: float, length: int) -> str:
    payload = json.dumps(["stage-c-r1", beta, alpha, length], separators=(",", ":"))
    return "act-" + hashlib.sha256(payload.encode()).hexdigest()[:20]


def action(beta: float, alpha: float, length: int, reason: str) -> dict[str, Any]:
    return {
        "action_id": action_id(beta, alpha, length),
        "params": {"alpha": alpha, "beta": beta, "L": length, "n_units": length // 5},
        "budget": 64 if length < 80 else 128,
        "stage": "C-R1-refine", "reason": reason,
        "boundary_thresholds_relaxed": False,
    }


def slice_summary(beta: float, rows: list[dict[str, Any]]) -> dict[str, Any]:
    indexed: dict[float, dict[int, dict[str, Any]]] = {}
    for row in rows:
        indexed.setdefault(float(row["params"]["alpha"]), {})[int(row["params"]["L"])] = row
    points = []
    for alpha in sorted(indexed):
        by_size = indexed[alpha]
        if 40 not in by_size or 60 not in by_size:
            raise ValueError(f"beta={beta}, alpha={alpha} 缺 L40/L60")
        q_values = [q_value(by_size[length]) for length in (40, 60)]
        if all(abs(value - 1.0) <= 0.02 for value in q_values):
            momentum = "commensurate_qpi"
        elif max(q_values) < 0.9:
            momentum = "incommensurate"
        else:
            momentum = "size_sensitive_or_mixed"
        points.append({"alpha": alpha, "sizes": sorted(by_size),
                       "delta_R_60_40": delta(by_size[60], by_size[40]),
                       "q_peak_median": sum(q_values) / 2, "momentum_class": momentum})
    sign, momentum = [], []
    for left, right in zip(points, points[1:]):
        left_delta, right_delta = left["delta_R_60_40"], right["delta_R_60_40"]
        bracket = [left["alpha"], right["alpha"]]
        if left_delta["value"] * right_delta["value"] < 0 and min(left_delta["sigma"], right_delta["sigma"]) >= 2:
            sign.append({"alpha": bracket, "width": bracket[1] - bracket[0],
                         "left": left_delta, "right": right_delta})
        if abs(left["q_peak_median"] - right["q_peak_median"]) >= 0.1:
            momentum.append({"alpha": bracket, "width": bracket[1] - bracket[0],
                             "q_left": left["q_peak_median"], "q_right": right["q_peak_median"]})
    targets = []
    brackets = sorted({tuple(item["alpha"]) for item in sign + momentum})
    for left, right in brackets:
        evidence = []
        if any(item["alpha"] == [left, right] for item in sign):
            evidence.append("two_sigma_ratio_sign")
        if any(item["alpha"] == [left, right] for item in momentum):
            evidence.append("momentum_reconstruction")
        targets.append({"beta": beta, "alpha": [left, right], "width": right - left,
                        "evidence": evidence, "dual_diagnostic": len(evidence) == 2,
                        "status": "candidate_not_boundary"})
    return {"beta": beta, "points": points, "sign_brackets": sign,
            "momentum_brackets": momentum, "refinement_targets": targets}


def stage_a_slice(stage_a: dict[str, Any]) -> dict[str, Any]:
    targets: dict[tuple[float, float], set[str]] = {}
    for item in stage_a.get("candidate_ratio_sign_brackets", []):
        targets.setdefault(tuple(item["alpha"]), set()).add("two_sigma_ratio_sign")
    for item in stage_a.get("candidate_q_brackets", []):
        targets.setdefault(tuple(item["alpha"]), set()).add("momentum_reconstruction")
    return {
        "beta": 0.5, "points": stage_a.get("alpha_summary", []),
        "sign_brackets": stage_a.get("candidate_ratio_sign_brackets", []),
        "momentum_brackets": stage_a.get("candidate_q_brackets", []),
        "refinement_targets": [
            {"beta": 0.5, "alpha": list(bracket), "width": bracket[1] - bracket[0],
             "evidence": sorted(evidence), "dual_diagnostic": len(evidence) == 2,
             "status": "candidate_not_boundary"}
            for bracket, evidence in sorted(targets.items())
        ],
    }


def main() -> int:
    args = parse_args()
    for path in (args.stage_a, args.stage_b_summary, args.stage_b_observations):
        if not path.is_file():
            raise FileNotFoundError(path)
    stage_a, stage_b_summary = load(args.stage_a), load(args.stage_b_summary)
    stage_b_doc = load(args.stage_b_observations)
    if (
        stage_a.get("status") != "complete"
        or stage_a.get("decision", {}).get("stage_b_ready") is not True
        or stage_b_summary.get("status") != "accepted_stage_b_complete"
        or stage_b_summary.get("counts") != {"success": 96, "failed": 0, "pending": 0}
        or stage_b_summary.get("observations", {}).get("sha256") != sha256(args.stage_b_observations)
        or stage_b_summary.get("canonical_controller_mutated") is not False
    ):
        raise ValueError("Stage A/B 尚未满足 Stage C 分析门")
    records = stage_b_doc.get("records", [])
    if len(records) != 96 or any(row.get("status") != "success" for row in records):
        raise ValueError("Stage B accepted-only observations 不完整")
    betas = sorted({float(row["params"]["beta"]) for row in records})
    if betas != [0.05, 0.1, 0.25, 0.75, 0.9, 1.0]:
        raise ValueError("Stage B beta 切片不匹配")
    slices = [slice_summary(beta, [row for row in records if float(row["params"]["beta"]) == beta])
              for beta in betas]
    slices.append(stage_a_slice(stage_a))
    slices.sort(key=lambda item: item["beta"])

    planned: dict[tuple[float, float, int], dict[str, Any]] = {}
    for item in slices:
        beta = float(item["beta"])
        available = {(float(point["alpha"]), int(length))
                     for point in item["points"] for length in point.get("sizes", [40, 60])}
        for target in item["refinement_targets"]:
            left, right = map(float, target["alpha"])
            midpoint = round((left + right) / 2, 12)
            reason = "+".join(target["evidence"])
            for alpha, length in ((left, 80), (right, 80),
                                  (midpoint, 40), (midpoint, 60), (midpoint, 80)):
                if (alpha, length) not in available:
                    planned[(beta, alpha, length)] = action(beta, alpha, length, reason)
    actions = [planned[item] for item in sorted(planned)]
    result = {
        "schema_version": 1, "status": "action_required" if actions else "no_internal_boundary_candidates",
        "inputs": {
            "stage_a": {"artifact": args.stage_a.resolve().relative_to(ROOT).as_posix(),
                        "sha256": sha256(args.stage_a)},
            "stage_b_summary": {"artifact": args.stage_b_summary.resolve().relative_to(ROOT).as_posix(),
                                "sha256": sha256(args.stage_b_summary)},
            "stage_b_observations": {"artifact": args.stage_b_observations.resolve().relative_to(ROOT).as_posix(),
                                     "sha256": sha256(args.stage_b_observations)},
        },
        "criteria": {"sigma": 2.0, "target_width": 0.025,
                     "final_size_pair": [60, 80], "dual_diagnostic_for_phase_name": True},
        "slices": slices, "stage_c_actions": actions,
        "counts": {"slices": 7, "refinement_targets": sum(len(item["refinement_targets"]) for item in slices),
                   "dual_diagnostic_targets": sum(sum(target["dual_diagnostic"] for target in item["refinement_targets"])
                                                  for item in slices),
                   "actions": len(actions)},
        "decision": {"phase_boundary_confirmed": False, "phase_label_assigned": False,
                     "stage_c_required": bool(actions), "boundary_thresholds_relaxed": False},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise FileExistsError(f"拒绝覆盖: {args.output}")
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], **result["counts"],
                      "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
