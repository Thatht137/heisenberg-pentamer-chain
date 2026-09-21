#!/usr/bin/env python3
"""比较修正向量谱与小系统精确谱。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np


def load_columns(path: Path) -> dict[str, np.ndarray]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return {key: np.array([float(row[key]) for row in rows]) for key in rows[0]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exact", required=True)
    parser.add_argument("--cv", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--peak-budget", type=float, default=0.1)
    parser.add_argument("--weight-budget", type=float, default=0.15)
    parser.add_argument("--residual-budget", type=float, default=1e-5)
    args = parser.parse_args()
    exact_path = Path(args.exact)
    exact = load_columns(exact_path)
    exact_summary = json.loads(exact_path.with_name("exact_summary.json").read_text(encoding="utf-8"))
    cv = load_columns(Path(args.cv))
    if not np.allclose(exact["omega"], cv["omega"], atol=1e-12, rtol=0.0):
        raise SystemExit("omega 网格不一致")
    omega = exact["omega"]
    exact_values = exact["intensity"]
    cv_values = cv["intensity"]
    exact_peak = float(omega[np.argmax(exact_values)])
    cv_peak = float(omega[np.argmax(cv_values)])
    exact_weight = float(np.trapezoid(exact_values, omega))
    cv_weight = float(np.trapezoid(cv_values, omega))
    weight_error = abs(cv_weight - exact_weight) / max(abs(exact_weight), np.finfo(float).eps)
    relative_l2 = float(np.linalg.norm(cv_values - exact_values) / np.linalg.norm(exact_values))
    max_residual = float(np.max(cv["relative_residual"]))
    checks = {
        "peak_pass": abs(cv_peak - exact_peak) <= args.peak_budget,
        "integrated_weight_pass": weight_error <= args.weight_budget,
        "residual_pass": max_residual <= args.residual_budget,
        "nonnegative_pass": float(np.min(cv_values)) >= -1e-10 * max(float(np.max(cv_values)), 1.0),
    }
    summary = {
        "tag": "Agreement" if all(checks.values()) else "Disagreement",
        "checks": checks,
        "budgets": {
            "peak_omega": args.peak_budget,
            "integrated_weight_relative": args.weight_budget,
            "max_cv_relative_residual": args.residual_budget,
        },
        "exact_peak_omega": exact_peak,
        "cv_peak_omega": cv_peak,
        "peak_difference": abs(cv_peak - exact_peak),
        "exact_integrated_weight": exact_weight,
        "cv_integrated_weight": cv_weight,
        "integrated_weight_relative_error": weight_error,
        "spectrum_relative_l2": relative_l2,
        "max_cv_relative_residual": max_residual,
        "cv_min_intensity": float(np.min(cv_values)),
    }
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    instance = (
        f"alpha={exact_summary['alpha']:g},beta={exact_summary['beta']:g},"
        f"L={exact_summary['L']},q/pi={exact_summary['q_over_pi']:g},"
        f"eta={exact_summary['eta']:g},OBC,Sz=0"
    )
    rows = [
        ("exact_diagonalization", "peak_omega", exact_peak, 0.0, instance, summary["tag"]),
        ("correction_vector_dmrg", "peak_omega", cv_peak, args.peak_budget, instance, summary["tag"]),
        ("exact_diagonalization", "integrated_weight", exact_weight, 0.0, instance, summary["tag"]),
        (
            "correction_vector_dmrg",
            "integrated_weight",
            cv_weight,
            args.weight_budget * abs(exact_weight),
            instance,
            summary["tag"],
        ),
    ]
    with (output.parent / "cross-method-check.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["method", "observable", "value", "uncertainty", "instance", "tag"])
        writer.writerows(rows)
    print(json.dumps(summary, ensure_ascii=False))
    if summary["tag"] != "Agreement":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
