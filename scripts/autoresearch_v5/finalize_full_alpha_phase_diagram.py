#!/usr/bin/env python3
"""合并正负区 accepted-only 数据并生成 Stage D source manifest。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POSITIVE = ROOT / "results/autoresearch_v5_20260802/round19_phase_diagram_positive_mesh/phase-diagram/observations_merged.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--decision", type=Path, required=True)
    parser.add_argument("--stage-a", type=Path, required=True)
    parser.add_argument("--stage-b", type=Path, required=True)
    parser.add_argument("--stage-c", type=Path, action="append", default=[])
    parser.add_argument("--positive", type=Path, default=DEFAULT_POSITIVE)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def record_key(row: dict[str, Any]) -> tuple[float, float, int]:
    params = row["params"]
    return float(params["alpha"]), float(params["beta"]), int(params["L"])


def q_value(row: dict[str, Any]) -> float | None:
    value = row.get("diagnostics", {}).get("q_peak_over_pi")
    if isinstance(value, dict):
        value = value.get("value")
    return float(value) if value is not None else None


def boundaries(decision: dict[str, Any]) -> dict[float, dict[str, Any]]:
    result = {}
    for row in decision.get("decisions", []):
        selected = row.get("selected")
        if not selected:
            continue
        left, right = map(float, selected["alpha"])
        result[float(row["beta"])] = {
            "beta": float(row["beta"]), "alpha_left": left, "alpha_right": right,
            "alpha_mid": (left + right) / 2, "width": right - left,
            "status": row["status"], "evidence": selected.get("evidence", []),
            "dual_diagnostic": selected.get("dual_diagnostic", False),
        }
    return result


def region(alpha: float, beta: float, q: float | None,
           boundary_map: dict[float, dict[str, Any]]) -> tuple[str, str]:
    if abs(beta) <= 1e-12:
        return "beta_zero_isolated_cell_boundary", "analytic_boundary"
    if abs(alpha) <= 1e-12:
        return "alpha_zero_singular_line", "analytic_boundary"
    if alpha > 0:
        return "qpi_gapless_af", "strict_positive"
    boundary = boundary_map.get(beta)
    if boundary:
        name = ("candidate_ic_critical" if alpha < boundary["alpha_mid"]
                else "candidate_commensurate_critical")
        confidence = ("dual_diagnostic_boundary" if boundary["dual_diagnostic"]
                      else "bounded_crossover")
        return name, confidence
    if q is not None:
        return ("candidate_ic_critical" if q < 0.9 else "candidate_commensurate_critical",
                "momentum_only")
    return "negative_region_not_evaluable", "missing_boundary_slice"


def main() -> int:
    args = parse_args()
    paths = [args.decision, args.stage_a, args.stage_b, args.positive, *args.stage_c]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
    decision = load(args.decision)
    if (
        decision.get("status") not in {"stage_d_ready", "bounded_not_evaluable"}
        or decision.get("decision", {}).get("stage_d_ready") is not True
        or decision.get("decision", {}).get("boundary_thresholds_relaxed") is not False
        or decision.get("next_actions")
    ):
        raise ValueError("Stage C 尚未释放 Stage D")
    boundary_map = boundaries(decision)

    merged: dict[tuple[float, float, int], tuple[int, str, dict[str, Any]]] = {}
    sources = [(0, "positive", args.positive), (1, "stage_a", args.stage_a),
               (2, "stage_b", args.stage_b)] + [
        (3 + index, f"stage_c_r{index + 1}", path) for index, path in enumerate(args.stage_c)
    ]
    for priority, tier, path in sources:
        for row in load(path).get("records", []):
            alpha, beta, length = record_key(row)
            if row.get("status") != "success":
                continue
            if alpha < 0 and row.get("accepted_only") is not True:
                continue
            if alpha < -1 or alpha > 1 or beta < 0 or beta > 1:
                raise ValueError("记录超出完整相图范围")
            key = (alpha, beta, length)
            if key not in merged or priority >= merged[key][0]:
                merged[key] = (priority, tier, row)
    rows = []
    for (alpha, beta, length), (_, tier, row) in sorted(merged.items()):
        q = q_value(row)
        phase, confidence = region(alpha, beta, q, boundary_map)
        rows.append({
            "alpha": alpha, "beta": beta, "L": length,
            "value": float(row["value"]), "error": float(row["error"]),
            "q_peak_over_pi": q, "region": phase, "classification": confidence,
            "evidence_tier": tier, "budget": row.get("budget"),
            "artifact": str(row.get("artifact", "")),
            "validation_sha256": row.get("validation", {}).get("sha256", ""),
        })
    if not rows or not any(row["alpha"] < 0 for row in rows) or not any(row["alpha"] > 0 for row in rows):
        raise ValueError("Stage D 缺少正区或负区 accepted 数据")
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    outputs = {
        "source": out / "full_alpha_phase_diagram.source.csv",
        "boundaries": out / "full_alpha_phase_boundaries.csv",
        "decision": out / "full_alpha_phase_decision.json",
        "manifest": out / "full_alpha_phase_source_manifest.json",
    }
    if any(path.exists() for path in outputs.values()):
        raise FileExistsError("Stage D 输出已存在，拒绝覆盖")
    with outputs["source"].open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    boundary_rows = [boundary_map[beta] for beta in sorted(boundary_map)]
    fields = ["beta", "alpha_left", "alpha_right", "alpha_mid", "width",
              "status", "evidence", "dual_diagnostic"]
    with outputs["boundaries"].open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in boundary_rows:
            writer.writerow({**row, "evidence": "+".join(row["evidence"])})
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["region"]] = counts.get(row["region"], 0) + 1
    final_decision = {
        "schema_version": 1, "status": "complete_bounded" if decision.get("status") == "bounded_not_evaluable" else "complete",
        "scope": {"alpha": [-1, 1], "beta": [0, 1], "excluded": ["reference Fig.9"]},
        "working_phase_count": {"bulk_regimes": 3, "singular_lines": 1},
        "phase_names": ["candidate_ic_critical", "candidate_commensurate_critical",
                        "qpi_gapless_af", "alpha_zero_singular_line"],
        "records": len(rows), "boundaries": len(boundary_rows), "region_counts": counts,
        "strict_second_thermodynamic_phase_confirmed": all(
            row["dual_diagnostic"] and row["width"] <= 0.025 + 1e-12 for row in boundary_rows
        ) and bool(boundary_rows),
        "interpretation": "候选相名采用宽松口径；数值与边界验收门未降低。",
        "thresholds_relaxed": False,
    }
    with outputs["decision"].open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(final_decision, ensure_ascii=False, indent=2) + "\n")
    manifest = {
        "schema_version": 1, "status": "pass", "inputs": [
            {"artifact": relative(path), "sha256": sha256(path), "bytes": path.stat().st_size}
            for path in paths
        ],
        "outputs": [
            {"artifact": relative(path), "sha256": sha256(path), "bytes": path.stat().st_size}
            for name, path in outputs.items() if name != "manifest"
        ],
        "accepted_only_negative": True, "exploratory_grid_used_as_evidence": False,
        "thresholds_relaxed": False,
    }
    with outputs["manifest"].open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": final_decision["status"], "records": len(rows),
                      "boundaries": len(boundary_rows), "output": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
