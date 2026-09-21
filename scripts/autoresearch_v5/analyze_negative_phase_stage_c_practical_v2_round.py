#!/usr/bin/env python3
"""分析 Practical V2 Stage C，并生成下一轮最小二分动作。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initial-analysis", type=Path, required=True)
    parser.add_argument("--stage-a-observations", type=Path, required=True)
    parser.add_argument("--stage-b-index", type=Path, required=True)
    parser.add_argument("--stage-c-summary", type=Path, required=True)
    parser.add_argument("--stage-c-observations", type=Path, action="append", required=True)
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(params: dict[str, Any]) -> tuple[float, float, int]:
    return float(params["alpha"]), float(params["beta"]), int(params["L"])


def q_value(row: dict[str, Any]) -> float:
    value = row["diagnostics"]["q_peak_over_pi"]
    return float(value["value"] if isinstance(value, dict) else value)


def delta(high: dict[str, Any], low: dict[str, Any]) -> dict[str, float]:
    value = float(high["value"]) - float(low["value"])
    error = math.hypot(float(high["error"]), float(low["error"]))
    return {"value": value, "error": error, "sigma": abs(value) / error if error else math.inf}


def point(alpha: float, by_size: dict[int, dict[str, Any]]) -> dict[str, Any] | None:
    if 60 not in by_size or 80 not in by_size:
        return None
    q60, q80 = q_value(by_size[60]), q_value(by_size[80])
    if max(q60, q80) < 0.9:
        momentum = "incommensurate"
    elif min(q60, q80) >= 0.98:
        momentum = "commensurate_qpi"
    else:
        momentum = "size_sensitive_or_mixed"
    return {"alpha": alpha, "sizes": [60, 80], "q": {"L60": q60, "L80": q80},
            "momentum_class": momentum, "delta_R_80_60": delta(by_size[80], by_size[60])}


def action_id(round_id: int, beta: float, alpha: float, length: int) -> str:
    raw = json.dumps(["stage-c-practical-v2", round_id + 1, beta, alpha, length], separators=(",", ":"))
    return "act-" + hashlib.sha256(raw.encode()).hexdigest()[:20]


def next_action(round_id: int, beta: float, alpha: float, length: int) -> dict[str, Any]:
    return {"action_id": action_id(round_id, beta, alpha, length),
            "params": {"alpha": alpha, "beta": beta, "L": length, "n_units": length // 5},
            "budget": 64, "stage": f"C-Practical-V2-R{round_id + 1}",
            "reason": "dual_diagnostic_bisection_to_width_0.025",
            "boundary_thresholds_relaxed": False}


def manifest_record(path: Path) -> dict[str, Any]:
    manifest = load(path)
    ratio = manifest["observables"]["dominant_structure_factor_ratio"]
    return {"params": manifest["params"], "status": "success", "value": ratio["value"],
            "error": ratio["error"], "budget": manifest["settings"]["nsweeps"],
            "artifact": path.resolve().relative_to(ROOT).as_posix(), "accepted_only": True,
            "boundary_eligible": True,
            "diagnostics": {"q_peak_over_pi": manifest["observables"]["structure_factor_peak_q_over_pi"]}}


def main() -> int:
    args = parse_args()
    inputs = [args.initial_analysis, args.stage_a_observations, args.stage_b_index,
              args.stage_c_summary, *args.stage_c_observations]
    for path in inputs:
        if not path.is_file():
            raise FileNotFoundError(path)
    initial, summary = load(args.initial_analysis), load(args.stage_c_summary)
    if (
        initial.get("status") != "action_required"
        or summary.get("status") != "accepted_stage_c_round_complete"
        or summary.get("policy") != "Practical V2"
        or summary.get("round") != args.round
        or summary.get("next_analysis_ready") is not True
        or summary.get("boundary_thresholds_relaxed") is not False
    ):
        raise ValueError("Practical V2 Stage C 终态未满足分析门")

    indexed: dict[tuple[float, float], dict[int, dict[str, Any]]] = {}
    for row in load(args.stage_a_observations).get("records", []):
        if row.get("status") == "success" and row.get("accepted_only") is True:
            alpha, beta, length = key(row["params"])
            indexed.setdefault((beta, alpha), {})[length] = row
    for row in load(args.stage_b_index).get("records", []):
        record = manifest_record(ROOT / row["artifact"])
        alpha, beta, length = key(record["params"])
        indexed.setdefault((beta, alpha), {})[length] = record
    for path in args.stage_c_observations:
        for row in load(path).get("records", []):
            if row.get("status") == "success" and row.get("accepted_only") is True:
                alpha, beta, length = key(row["params"])
                indexed.setdefault((beta, alpha), {})[length] = row

    target_width = float(initial["criteria"]["target_width"])
    sigma_min = float(initial["criteria"]["sigma"])
    decisions: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    confirmed: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for target in initial.get("refinement_targets", []):
        beta = float(target["beta"])
        left, right = map(float, target["alpha"])
        candidates = []
        for (beta_value, alpha), by_size in indexed.items():
            if abs(beta_value - beta) <= 1e-12 and left - 1e-12 <= alpha <= right + 1e-12:
                item = point(alpha, by_size)
                if item:
                    candidates.append(item)
        candidates.sort(key=lambda row: row["alpha"])
        brackets = []
        for low, high in zip(candidates, candidates[1:]):
            low_delta, high_delta = low["delta_R_80_60"], high["delta_R_80_60"]
            momentum = {low["momentum_class"], high["momentum_class"]} == {
                "incommensurate", "commensurate_qpi"}
            ratio = low_delta["value"] * high_delta["value"] < 0 and min(
                low_delta["sigma"], high_delta["sigma"]) >= sigma_min
            evidence = (["momentum_reconstruction"] if momentum else []) + (
                ["two_sigma_ratio_sign"] if ratio else [])
            if evidence:
                brackets.append({"alpha": [low["alpha"], high["alpha"]],
                                 "width": high["alpha"] - low["alpha"],
                                 "evidence": evidence, "dual_diagnostic": len(evidence) == 2,
                                 "left": low, "right": high})
        dual = [row for row in brackets if row["dual_diagnostic"]]
        selected = min(dual, key=lambda row: row["width"]) if dual else None
        if selected and selected["width"] <= target_width + 1e-12:
            status = "confirmed_candidate_boundary"
            confirmed.append({"beta": beta, **selected})
        elif selected:
            status = "refine_again"
            midpoint = round(sum(selected["alpha"]) / 2, 12)
            for length in (60, 80):
                if (beta, midpoint) not in indexed or length not in indexed[(beta, midpoint)]:
                    actions.append(next_action(args.round, beta, midpoint, length))
        else:
            status = "single_diagnostic_or_not_evaluable" if brackets else "no_supported_internal_boundary"
            unresolved.append({"beta": beta, "initial_alpha": [left, right], "status": status,
                               "candidate_brackets": brackets})
        decisions.append({"beta": beta, "initial_alpha": [left, right], "points": candidates,
                          "candidate_brackets": brackets, "selected": selected, "status": status})

    dedup = {(row["params"]["beta"], row["params"]["alpha"], row["params"]["L"]): row for row in actions}
    actions = [dedup[item] for item in sorted(dedup)]
    state = "refinement_required" if actions else "stage_d_ready" if not unresolved else "bounded_not_evaluable"
    result = {"schema_version": 1, "status": state, "round": args.round,
              "inputs": {path.stem: {"artifact": path.resolve().relative_to(ROOT).as_posix(),
                                      "sha256": sha256(path)} for path in inputs},
              "criteria": {"sigma": sigma_min, "target_width": target_width,
                           "final_size_pair": [60, 80], "dual_diagnostic": True, "max_sweeps": 64},
              "decisions": decisions, "confirmed_boundaries": confirmed,
              "unresolved_targets": unresolved, "next_actions": actions,
              "counts": {"targets": len(decisions), "confirmed": len(confirmed),
                         "unresolved": len(unresolved), "next_actions": len(actions)},
              "decision": {"stage_d_ready": not actions and not unresolved,
                           "bounded_not_evaluable": bool(unresolved) and not actions,
                           "phase_label_assigned": False, "boundary_thresholds_relaxed": False}}
    if args.output.exists():
        raise FileExistsError(f"拒绝覆盖: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": state, **result["counts"],
                      "output": args.output.resolve().relative_to(ROOT).as_posix()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
