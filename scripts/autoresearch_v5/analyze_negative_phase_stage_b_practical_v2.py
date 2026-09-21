#!/usr/bin/env python3
"""分析 Practical V2 的 accepted-only Stage B，并生成 Stage C 动作。"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PHASE = ROOT / "results/autoresearch_v5_20260809/round44_phase_diagram_full_alpha/phase-diagram-v2"
SUMMARY = PHASE / "stage_b_practical_v2_completion_summary.json"
ACCEPTED = PHASE / "stage_b_practical_v2_accepted_index_final.json"
BOUNDED = PHASE / "stage_b_practical_v2_bounded_records_final.json"
STAGE_A = PHASE / "stage_a_finite_size_diagnostic_latest.json"
OUTPUT = PHASE / "stage_b_practical_v2_cross_slice_diagnostic_v2.json"
ALPHAS = (-1.0, -0.75, -0.5, -0.35, -0.25, -0.1, -0.05, -0.025)
BETAS = (0.05, 0.1, 0.25, 0.75, 0.9, 1.0)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def observable(manifest: dict[str, Any], name: str) -> dict[str, float]:
    row = manifest["observables"][name]
    return {"value": float(row["value"]), "error": float(row["error"])}


def difference(high: dict[str, float], low: dict[str, float]) -> dict[str, float]:
    value = high["value"] - low["value"]
    error = math.hypot(high["error"], low["error"])
    return {"value": value, "error": error, "sigma": abs(value) / error if error else math.inf}


def action_id(beta: float, alpha: float, length: int) -> str:
    payload = json.dumps(["stage-c-practical-v2-r1", beta, alpha, length], separators=(",", ":"))
    return "act-" + hashlib.sha256(payload.encode()).hexdigest()[:20]


def stage_c_action(beta: float, alpha: float, length: int, reason: str) -> dict[str, Any]:
    return {
        "action_id": action_id(beta, alpha, length),
        "params": {"alpha": alpha, "beta": beta, "L": length, "n_units": length // 5},
        "budget": 64,
        "stage": "C-R1-practical-v2-refine",
        "reason": reason,
        "boundary_thresholds_relaxed": False,
    }


def main() -> int:
    for path in (SUMMARY, ACCEPTED, BOUNDED, STAGE_A):
        if not path.is_file():
            raise FileNotFoundError(path)
    summary, accepted, bounded, stage_a = map(load, (SUMMARY, ACCEPTED, BOUNDED, STAGE_A))
    if (
        summary.get("status") != "accepted_stage_b_complete_with_bounded"
        or summary.get("counts") != {"grid": 96, "accepted": 89, "bounded": 7, "pending": 0}
        or summary.get("inputs", {}).get("accepted_index", {}).get("sha256") != sha256(ACCEPTED)
        or summary.get("inputs", {}).get("bounded_records", {}).get("sha256") != sha256(BOUNDED)
        or stage_a.get("status") != "complete"
    ):
        raise ValueError("Stage B Practical V2 终态证据不匹配")

    manifests: dict[tuple[float, float, int], dict[str, Any]] = {}
    for row in accepted["records"]:
        manifest_path = ROOT / row["artifact"]
        manifest = load(manifest_path)
        params = manifest["params"]
        key = float(params["alpha"]), float(params["beta"]), int(params["L"])
        if key != (float(row["params"]["alpha"]), float(row["params"]["beta"]), int(row["params"]["L"])):
            raise ValueError(f"索引与 manifest 参数不匹配: {manifest_path}")
        manifests[key] = manifest
    bounded_keys = {(float(row["params"]["alpha"]), float(row["params"]["beta"]), int(row["params"]["L"]))
                    for row in bounded["records"]}

    slices: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    for beta in BETAS:
        points: list[dict[str, Any]] = []
        for alpha in ALPHAS:
            by_size = {length: manifests.get((alpha, beta, length)) for length in (40, 60)}
            missing = [length for length, manifest in by_size.items() if manifest is None]
            if missing:
                points.append({"alpha": alpha, "status": "bounded_missing_size",
                               "missing_sizes": missing, "boundary_eligible": False})
                continue
            low = observable(by_size[40], "dominant_structure_factor_ratio")
            high = observable(by_size[60], "dominant_structure_factor_ratio")
            q40 = observable(by_size[40], "structure_factor_peak_q_over_pi")
            q60 = observable(by_size[60], "structure_factor_peak_q_over_pi")
            q_median = (q40["value"] + q60["value"]) / 2
            momentum = "commensurate_qpi" if abs(q40["value"] - 1) <= 0.02 and abs(q60["value"] - 1) <= 0.02 else (
                "incommensurate" if max(q40["value"], q60["value"]) < 0.9 else "size_sensitive_or_mixed")
            points.append({"alpha": alpha, "status": "accepted_pair", "sizes": [40, 60],
                           "delta_R_60_40": difference(high, low), "q_peak_median": q_median,
                           "q_peak_by_size": {"40": q40, "60": q60},
                           "momentum_class": momentum, "boundary_eligible": True})
        sign_brackets: list[dict[str, Any]] = []
        momentum_brackets: list[dict[str, Any]] = []
        for left, right in zip(points, points[1:]):
            if left["status"] != "accepted_pair" or right["status"] != "accepted_pair":
                continue
            bracket = [left["alpha"], right["alpha"]]
            left_delta, right_delta = left["delta_R_60_40"], right["delta_R_60_40"]
            if left_delta["value"] * right_delta["value"] < 0 and min(left_delta["sigma"], right_delta["sigma"]) >= 2:
                sign_brackets.append({"alpha": bracket, "width": bracket[1] - bracket[0],
                                      "left": left_delta, "right": right_delta})
            if abs(left["q_peak_median"] - right["q_peak_median"]) >= 0.1:
                momentum_brackets.append({"alpha": bracket, "width": bracket[1] - bracket[0],
                                          "q_left": left["q_peak_median"],
                                          "q_right": right["q_peak_median"]})
        for bracket in sorted({tuple(row["alpha"]) for row in sign_brackets + momentum_brackets}):
            evidence = []
            if any(row["alpha"] == list(bracket) for row in sign_brackets):
                evidence.append("two_sigma_ratio_sign")
            if any(row["alpha"] == list(bracket) for row in momentum_brackets):
                evidence.append("momentum_reconstruction")
            target = {"beta": beta, "alpha": list(bracket), "width": bracket[1] - bracket[0],
                      "evidence": evidence, "dual_diagnostic": len(evidence) == 2,
                      "status": "candidate_not_boundary"}
            targets.append(target)
        slices.append({"beta": beta, "points": points, "sign_brackets": sign_brackets,
                       "momentum_brackets": momentum_brackets,
                       "bounded_grid_keys": [list(key) for key in sorted(bounded_keys) if key[1] == beta]})

    for row in stage_a.get("candidate_q_brackets", []):
        bracket = tuple(map(float, row["alpha"]))
        ratio_match = any(tuple(map(float, item["alpha"])) == bracket
                          and item.get("two_sigma") is True
                          for item in stage_a.get("candidate_ratio_sign_brackets", []))
        targets.append({"beta": 0.5, "alpha": list(bracket), "width": bracket[1] - bracket[0],
                        "evidence": ["momentum_reconstruction"] + (["two_sigma_ratio_sign"] if ratio_match else []),
                        "dual_diagnostic": ratio_match, "status": "candidate_not_boundary"})

    unique_targets = {(item["beta"], *item["alpha"]): item for item in targets}
    actions: dict[tuple[float, float, int], dict[str, Any]] = {}
    for item in unique_targets.values():
        left, right = map(float, item["alpha"])
        midpoint = round((left + right) / 2, 12)
        reason = "+".join(item["evidence"])
        requested = [(left, 80), (right, 80)]
        if right - left > 0.025 + 1e-12:
            requested.extend([(midpoint, 60), (midpoint, 80)])
        for alpha, length in requested:
            if (alpha, float(item["beta"]), length) not in manifests:
                actions[(float(item["beta"]), alpha, length)] = stage_c_action(float(item["beta"]), alpha, length, reason)

    result = {
        "schema_version": 1,
        "status": "action_required" if actions else "no_internal_boundary_candidates",
        "policy": "Practical V2 accepted-only",
        "inputs": {
            "stage_b_summary": {"artifact": relative(SUMMARY), "sha256": sha256(SUMMARY)},
            "accepted_index": {"artifact": relative(ACCEPTED), "sha256": sha256(ACCEPTED)},
            "bounded_records": {"artifact": relative(BOUNDED), "sha256": sha256(BOUNDED)},
            "stage_a": {"artifact": relative(STAGE_A), "sha256": sha256(STAGE_A)},
        },
        "criteria": {"sigma": 2.0, "target_width": 0.025, "final_size_pair": [60, 80],
                     "sweeps": 64, "dual_diagnostic_for_phase_name": True},
        "slices": slices,
        "refinement_targets": sorted(unique_targets.values(), key=lambda row: (row["beta"], row["alpha"])),
        "stage_c_actions": [actions[key] for key in sorted(actions)],
        "counts": {"slices": 7, "accepted": 89, "bounded": 7,
                   "refinement_targets": len(unique_targets), "actions": len(actions)},
        "decision": {"phase_boundary_confirmed": False, "phase_label_assigned": False,
                     "stage_c_required": bool(actions), "boundary_thresholds_relaxed": False,
                     "bounded_points_excluded": True, "no_bridging_across_bounded_holes": True},
    }
    if OUTPUT.exists():
        raise FileExistsError(f"拒绝覆盖: {OUTPUT}")
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], **result["counts"],
                      "output": relative(OUTPUT)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
