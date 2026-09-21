#!/usr/bin/env python3
"""回放负 alpha 历史结果，比较不同方差门。"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


THRESHOLDS = (1e-8, 3e-8, 5e-8, 1e-7, 2e-7)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def finite(value: object) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"非有限数值: {value}")
    return number


def child_gates(child: dict, variance_max: float) -> tuple[bool, list[str], float]:
    failures: list[str] = []
    diagnostics = child.get("diagnostics") or {}
    acceptance = child.get("acceptance") or {}
    max_variance = 0.0

    if child.get("status") != "success" or child.get("returncode") != 0:
        failures.append("execution")
    for sector in ("sz0", "sz1"):
        variance = finite(diagnostics.get(f"variance_per_site_{sector}"))
        truncation = finite(diagnostics.get(f"final_truncation_error_{sector}"))
        max_variance = max(max_variance, variance)
        if variance > variance_max:
            failures.append(f"variance_{sector}")
        if truncation > 1e-9:
            failures.append(f"truncation_{sector}")
    if abs(finite(diagnostics.get("total_sz0"))) > 1e-8:
        failures.append("sector_sz0")
    if abs(finite(diagnostics.get("total_sz1")) - 1.0) > 1e-8:
        failures.append("sector_sz1")
    if finite((child.get("observables") or {}).get("spin_gap")) < -1e-8:
        failures.append("negative_gap")

    for key in (
        "execution_success",
        "truncation_sz0_le_1e-9",
        "truncation_sz1_le_1e-9",
        "sz0_sector",
        "sz1_sector",
        "nonnegative_gap",
        "all_sweeps_completed",
        "fullq_file",
        "fullq_count",
        "measurement_files",
    ):
        if acceptance.get(key) is not True:
            failures.append(f"flag_{key}")
    return not failures, sorted(set(failures)), max_variance


def find_parents(root: Path, path_token: str) -> list[Path]:
    parents = []
    for path in root.rglob("manifest.json"):
        if path_token and path_token not in str(path):
            continue
        if (path.parent / "start_center" / "manifest.json").is_file() and (
            path.parent / "start_ferro_j2" / "manifest.json"
        ).is_file():
            parents.append(path)
    return sorted(parents)


def audit_parent(path: Path) -> dict:
    parent = load(path)
    center = load(path.parent / "start_center" / "manifest.json")
    ferro = load(path.parent / "start_ferro_j2" / "manifest.json")
    params = parent.get("params") or {}
    settings = parent.get("settings") or {}
    parent_acceptance = parent.get("acceptance") or {}

    row = {
        "cell_id": parent.get("cell_id"),
        "manifest": str(path),
        "alpha": finite(params.get("alpha")),
        "beta": finite(params.get("beta")),
        "L": int(params.get("L")),
        "sweeps": int(settings.get("nsweeps")),
        "parent_energy_consistency": parent_acceptance.get("energy_consistency") is True,
        "old_accepted": parent.get("accepted") is True,
    }
    max_variance = 0.0
    for threshold in THRESHOLDS:
        center_ok, center_failures, center_max = child_gates(center, threshold)
        ferro_ok, ferro_failures, ferro_max = child_gates(ferro, threshold)
        max_variance = max(max_variance, center_max, ferro_max)
        ok = center_ok and ferro_ok and row["parent_energy_consistency"]
        row[f"pass_{threshold:.0e}"] = ok
        row[f"failures_{threshold:.0e}"] = sorted(set(center_failures + ferro_failures))
    row["max_variance_per_site"] = max_variance
    row["q_peak_over_pi"] = finite(
        ((parent.get("observables") or {}).get("structure_factor_peak_q_over_pi") or {}).get("value")
    )
    row["q_peak_error"] = finite(
        ((parent.get("observables") or {}).get("structure_factor_peak_q_over_pi") or {}).get("error")
    )
    row["ratio"] = finite(
        ((parent.get("observables") or {}).get("dominant_structure_factor_ratio") or {}).get("value")
    )
    row["ratio_error"] = finite(
        ((parent.get("observables") or {}).get("dominant_structure_factor_ratio") or {}).get("error")
    )
    return row


def summarize(rows: list[dict]) -> dict:
    physical_keys = sorted({(r["alpha"], r["beta"], r["L"]) for r in rows})
    result = {"manifest_count": len(rows), "physical_point_count": len(physical_keys), "thresholds": {}}
    for threshold in THRESHOLDS:
        field = f"pass_{threshold:.0e}"
        accepted = 0
        sweep_counts: dict[str, int] = {}
        unresolved = []
        convergence_pairs = []
        for key in physical_keys:
            options = [r for r in rows if (r["alpha"], r["beta"], r["L"]) == key and r[field]]
            if options:
                best = min(options, key=lambda r: (r["sweeps"], r["max_variance_per_site"], r["cell_id"]))
                accepted += 1
                sweep_counts[str(best["sweeps"])] = sweep_counts.get(str(best["sweeps"]), 0) + 1
                sweep_levels = sorted({r["sweeps"] for r in options})
                if len(sweep_levels) > 1:
                    low = min((r for r in options if r["sweeps"] == sweep_levels[0]), key=lambda r: r["max_variance_per_site"])
                    high = min((r for r in options if r["sweeps"] == sweep_levels[-1]), key=lambda r: r["max_variance_per_site"])
                    convergence_pairs.append({
                        "alpha": key[0], "beta": key[1], "L": key[2],
                        "low_sweeps": low["sweeps"], "high_sweeps": high["sweeps"],
                        "q_peak_delta": abs(low["q_peak_over_pi"] - high["q_peak_over_pi"]),
                        "ratio_delta": abs(low["ratio"] - high["ratio"]),
                    })
            else:
                unresolved.append({"alpha": key[0], "beta": key[1], "L": key[2]})
        result["thresholds"][f"{threshold:.0e}"] = {
            "accepted_physical_points": accepted,
            "unresolved_physical_points": len(unresolved),
            "minimal_sweep_distribution": sweep_counts,
            "convergence_pair_count": len(convergence_pairs),
            "convergence_max_q_peak_delta": max((r["q_peak_delta"] for r in convergence_pairs), default=None),
            "convergence_max_ratio_delta": max((r["ratio_delta"] for r in convergence_pairs), default=None),
            "convergence_pairs": convergence_pairs,
            "unresolved": unresolved,
        }
    return result


def write_csv(path: Path, rows: list[dict]) -> None:
    columns = [
        "cell_id",
        "alpha",
        "beta",
        "L",
        "sweeps",
        "max_variance_per_site",
        "parent_energy_consistency",
        "old_accepted",
        "q_peak_over_pi",
        "q_peak_error",
        "ratio",
        "ratio_error",
    ]
    for threshold in THRESHOLDS:
        columns.extend((f"pass_{threshold:.0e}", f"failures_{threshold:.0e}"))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for source in rows:
            row = dict(source)
            for threshold in THRESHOLDS:
                field = f"failures_{threshold:.0e}"
                row[field] = ";".join(row[field])
            writer.writerow({key: row.get(key) for key in columns})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch-root", type=Path, required=True)
    parser.add_argument("--path-token", default="stage-b-negative-coarse")
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-csv", type=Path, required=True)
    args = parser.parse_args()

    parents = find_parents(args.fetch_root, args.path_token)
    if not parents:
        raise SystemExit("未找到双初态父 manifest")
    rows = [audit_parent(path) for path in parents]
    summary = summarize(rows)
    payload = {
        "schema_version": 1,
        "purpose": "reference-author variance-threshold feedback sensitivity audit",
        "fixed_gates": {
            "final_truncation_error_max": 1e-9,
            "sector_tolerance": 1e-8,
            "spin_gap_min": -1e-8,
            "two_initial_states": True,
            "energy_consistency": True,
            "files_and_measurements": True,
        },
        "summary": summary,
        "records": rows,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(args.output_csv, rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
