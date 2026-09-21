#!/usr/bin/env python3
"""分析 Stage C 一轮细化并决定确认、再二分或仅作交叉。"""

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
    parser.add_argument("--initial-analysis", type=Path,
                        default=DEFAULT_PHASE / "stage_b_cross_slice_diagnostic.json")
    parser.add_argument("--stage-a-observations", type=Path, default=DEFAULT_PHASE / "observations.json")
    parser.add_argument("--stage-b-observations", type=Path,
                        default=DEFAULT_PHASE / "stage_b_r1_terminal_observations.json")
    parser.add_argument("--stage-c-summary", type=Path,
                        default=DEFAULT_PHASE / "stage_c_r1_terminal_summary.json")
    parser.add_argument("--stage-c-observations", type=Path,
                        default=DEFAULT_PHASE / "stage_c_r1_terminal_observations.json")
    parser.add_argument("--round", type=int, default=1)
    parser.add_argument("--output", type=Path,
                        default=DEFAULT_PHASE / "stage_c_r1_boundary_decision.json")
    return parser.parse_args()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def key(row: dict[str, Any]) -> tuple[float, float, int]:
    params = row["params"]
    return float(params["alpha"]), float(params["beta"]), int(params["L"])


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
    payload = json.dumps(["stage-c", round_id + 1, beta, alpha, length], separators=(",", ":"))
    return "act-" + hashlib.sha256(payload.encode()).hexdigest()[:20]


def next_action(round_id: int, beta: float, alpha: float, length: int) -> dict[str, Any]:
    return {
        "action_id": action_id(round_id, beta, alpha, length),
        "params": {"alpha": alpha, "beta": beta, "L": length, "n_units": length // 5},
        "budget": 64 if length == 60 else 128,
        "stage": f"C-R{round_id + 1}-refine",
        "reason": "dual_diagnostic_bisection_to_width_0.025",
        "boundary_thresholds_relaxed": False,
    }


def main() -> int:
    args = parse_args()
    inputs = [args.initial_analysis, args.stage_a_observations, args.stage_b_observations,
              args.stage_c_summary, args.stage_c_observations]
    for path in inputs:
        if not path.is_file():
            raise FileNotFoundError(path)
    initial, summary = load(args.initial_analysis), load(args.stage_c_summary)
    stage_c_doc = load(args.stage_c_observations)
    if (
        initial.get("status") != "action_required"
        or summary.get("status") != "accepted_stage_c_round_complete"
        or summary.get("next_analysis_ready") is not True
        or summary.get("observations", {}).get("sha256") != sha256(args.stage_c_observations)
        or summary.get("boundary_thresholds_relaxed") is not False
        or any(row.get("status") != "success" for row in stage_c_doc.get("records", []))
    ):
        raise ValueError("Stage C 终态未满足边界分析门")

    indexed: dict[tuple[float, float], dict[int, dict[str, Any]]] = {}
    for path in (args.stage_a_observations, args.stage_b_observations, args.stage_c_observations):
        for row in load(path).get("records", []):
            if row.get("status") != "success" or row.get("accepted_only") is not True:
                continue
            if row.get("boundary_eligible") is False:
                continue
            alpha, beta, length = key(row)
            indexed.setdefault((beta, alpha), {})[length] = row

    decisions, actions = [], []
    target_width = float(initial.get("criteria", {}).get("target_width", 0.025))
    sigma_min = float(initial.get("criteria", {}).get("sigma", 2.0))
    for slice_doc in initial.get("slices", []):
        beta = float(slice_doc["beta"])
        for target in slice_doc.get("refinement_targets", []):
            left, right = map(float, target["alpha"])
            candidates = []
            for beta_alpha, by_size in indexed.items():
                beta_value, alpha = beta_alpha
                if abs(beta_value - beta) <= 1e-12 and left - 1e-12 <= alpha <= right + 1e-12:
                    item = point(alpha, by_size)
                    if item:
                        candidates.append(item)
            candidates.sort(key=lambda item: item["alpha"])
            brackets = []
            for low, high in zip(candidates, candidates[1:]):
                low_delta, high_delta = low["delta_R_80_60"], high["delta_R_80_60"]
                momentum = {low["momentum_class"], high["momentum_class"]} == {
                    "incommensurate", "commensurate_qpi"
                }
                ratio = (low_delta["value"] * high_delta["value"] < 0
                         and min(low_delta["sigma"], high_delta["sigma"]) >= sigma_min)
                evidence = (["momentum_reconstruction"] if momentum else []) + (
                    ["two_sigma_ratio_sign"] if ratio else [])
                if evidence:
                    brackets.append({"alpha": [low["alpha"], high["alpha"]],
                                     "width": high["alpha"] - low["alpha"],
                                     "evidence": evidence, "dual_diagnostic": len(evidence) == 2,
                                     "left": low, "right": high})
            dual = [item for item in brackets if item["dual_diagnostic"]]
            if len(dual) == 1:
                selected = dual[0]
                if selected["width"] <= target_width + 1e-12:
                    status = "confirmed_candidate_boundary"
                else:
                    status = "refine_again"
                    midpoint = round(sum(selected["alpha"]) / 2, 12)
                    for length in (60, 80):
                        if (beta, midpoint) not in indexed or length not in indexed[(beta, midpoint)]:
                            actions.append(next_action(args.round, beta, midpoint, length))
            elif brackets:
                selected = min(brackets, key=lambda item: item["width"])
                status = "crossover_or_not_evaluable"
            else:
                selected, status = None, "no_supported_internal_boundary"
            decisions.append({"beta": beta, "initial_alpha": [left, right],
                              "points": candidates, "candidate_brackets": brackets,
                              "selected": selected, "status": status})

    dedup = {(row["params"]["beta"], row["params"]["alpha"], row["params"]["L"]): row
             for row in actions}
    actions = [dedup[item] for item in sorted(dedup)]
    confirmed = [row for row in decisions if row["status"] == "confirmed_candidate_boundary"]
    unresolved = [row for row in decisions if row["status"] in {
        "refine_again", "crossover_or_not_evaluable"
    }]
    result = {
        "schema_version": 1,
        "status": "refinement_required" if actions else "stage_d_ready" if not unresolved else "bounded_not_evaluable",
        "round": args.round,
        "inputs": {path.stem: {"artifact": path.resolve().relative_to(ROOT).as_posix(),
                                "sha256": sha256(path)} for path in inputs},
        "criteria": {"sigma": sigma_min, "target_width": target_width,
                     "final_size_pair": [60, 80], "dual_diagnostic": True},
        "decisions": decisions, "confirmed_boundaries": confirmed,
        "next_actions": actions,
        "counts": {"targets": len(decisions), "confirmed": len(confirmed),
                   "unresolved": len(unresolved), "next_actions": len(actions)},
        "decision": {"stage_d_ready": not actions,
                     "bounded_not_evaluable": bool(unresolved) and not actions,
                     "phase_label_assigned": False,
                     "boundary_thresholds_relaxed": False},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise FileExistsError(f"拒绝覆盖: {args.output}")
    with args.output.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], **result["counts"],
                      "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
