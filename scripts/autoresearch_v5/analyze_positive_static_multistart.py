#!/usr/bin/env python3
"""比较候选脊线的 center/domain 双初态结果。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_metrics(path: Path) -> dict[str, float | str]:
    values: dict[str, float | str] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                values[row["metric"]] = float(row["value"])
            except ValueError:
                values[row["metric"]] = row["value"]
    return values


def read_index(path: Path, key: str, value: str) -> dict[str, float]:
    with path.open(encoding="utf-8", newline="") as handle:
        return {row[key]: float(row[value]) for row in csv.DictReader(handle)}


def read_schmidt(path: Path) -> dict[str, list[float]]:
    by_bond: dict[str, list[float]] = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            by_bond[row["bond"]].append(float(row["probability"]))
    return {bond: sorted(values, reverse=True) for bond, values in by_bond.items()}


def max_abs_difference(left: dict[str, float], right: dict[str, float]) -> float:
    if set(left) != set(right):
        return math.inf
    return max((abs(left[key] - right[key]) for key in left), default=0.0)


def max_schmidt_l1(left: dict[str, list[float]], right: dict[str, list[float]]) -> float:
    if set(left) != set(right):
        return math.inf
    differences: list[float] = []
    for bond in left:
        if len(left[bond]) != len(right[bond]):
            return math.inf
        differences.append(sum(abs(a - b) for a, b in zip(left[bond], right[bond])))
    return max(differences, default=0.0)


def compare_cell_dirs(
    center_dir: Path,
    domain_dir: Path,
    budgets: dict[str, float],
) -> dict[str, object]:
    center = read_metrics(center_dir / "metrics.csv")
    domain = read_metrics(domain_dir / "metrics.csv")
    length = int(float(center["L"]))
    if int(float(domain["L"])) != length:
        raise ValueError("双初态长度不一致")
    metrics = {
        "energy_density_abs": abs(
            float(center["energy_sz0"]) / length - float(domain["energy_sz0"]) / length
        ),
        "spin_gap_abs": abs(float(center["spin_gap"]) - float(domain["spin_gap"])),
        "string_profile_abs": max_abs_difference(
            read_index(center_dir / "string_profile.csv", "distance_units", "O_mean"),
            read_index(domain_dir / "string_profile.csv", "distance_units", "O_mean"),
        ),
        "bond_correlation_abs": max_abs_difference(
            read_index(center_dir / "bond_correlations.csv", "bond", "correlation"),
            read_index(domain_dir / "bond_correlations.csv", "bond", "correlation"),
        ),
        "schmidt_probability_l1": max_schmidt_l1(
            read_schmidt(center_dir / "schmidt_spectrum.csv"),
            read_schmidt(domain_dir / "schmidt_spectrum.csv"),
        ),
    }
    checks = {
        name: math.isfinite(value) and value <= budgets[f"{name}_max"]
        for name, value in metrics.items()
    }
    return {"metrics": metrics, "checks": checks, "accepted": all(checks.values())}


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-spec", required=True)
    parser.add_argument("--paths", required=True)
    parser.add_argument("--mode", choices=("pilot", "full"), default="full")
    parser.add_argument("--outdir")
    args = parser.parse_args()

    run_spec_path = Path(args.run_spec).resolve()
    run_spec = json.loads(run_spec_path.read_text(encoding="utf-8"))
    paths_path = Path(args.paths).resolve()
    paths = json.loads(paths_path.read_text(encoding="utf-8"))
    variants = {row["variant_id"]: row for row in paths["variants"]}
    run_dir = (ROOT / str(run_spec["run_dir"]).replace("\\", "/")).resolve()
    run_dir.relative_to((ROOT / "results").resolve())
    outdir = Path(args.outdir).resolve() if args.outdir else run_dir / f"analysis_multistart_{args.mode}"
    outdir.relative_to((ROOT / "results").resolve())
    outdir.mkdir(parents=True, exist_ok=True)
    budgets = {
        key: float(value)
        for key, value in run_spec["settings"]["initialization_validation"].items()
    }

    expected: dict[tuple[str, int], dict[str, str]] = defaultdict(dict)
    for cell in run_spec["cells"]:
        variant = variants[str(cell["params"]["variant_id"])]
        length = int(cell["params"]["L"])
        if variant["role"] != "ridge" or (args.mode == "pilot" and length != 40):
            continue
        expected[(str(variant["path_id"]), length)][str(variant["init_mode"])] = str(cell["cell_id"])

    rows: list[dict[str, object]] = []
    incomplete: list[dict[str, object]] = []
    for (path_id, length), modes in sorted(expected.items()):
        if set(modes) != {"center", "domain"}:
            incomplete.append({"path_id": path_id, "L": length, "reason": "run spec 缺少双初态"})
            continue
        cell_dirs = {mode: run_dir / "cells" / cell_id for mode, cell_id in modes.items()}
        invalid = []
        for mode, cell_dir in cell_dirs.items():
            status_path = cell_dir / "status.json"
            if not status_path.is_file():
                invalid.append(f"{mode}:missing")
                continue
            status = json.loads(status_path.read_text(encoding="utf-8"))
            if status.get("status") != "success" or not status.get("accepted"):
                invalid.append(f"{mode}:not_accepted")
        if invalid:
            incomplete.append({"path_id": path_id, "L": length, "reason": ";".join(invalid)})
            continue
        comparison = compare_cell_dirs(cell_dirs["center"], cell_dirs["domain"], budgets)
        variant = variants[f"{path_id}-center"]
        rows.append({
            "path_id": path_id,
            "group": variant["group"],
            "alpha": variant["alpha"],
            "beta": variant["beta"],
            "L": length,
            **comparison["metrics"],
            "accepted": comparison["accepted"],
        })

    columns = [
        "path_id", "group", "alpha", "beta", "L", "energy_density_abs",
        "spin_gap_abs", "string_profile_abs", "bond_correlation_abs",
        "schmidt_probability_l1", "accepted",
    ]
    with (outdir / "multistart_comparison.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    expected_pairs = 3 if args.mode == "pilot" else 9
    accepted_pairs = sum(bool(row["accepted"]) for row in rows)
    complete = len(rows) == expected_pairs and not incomplete
    summary = {
        "status": "pass" if complete and accepted_pairs == expected_pairs else "pending_or_failed",
        "mode": args.mode,
        "expected_pairs": expected_pairs,
        "compared_pairs": len(rows),
        "accepted_pairs": accepted_pairs,
        "budgets": budgets,
        "rows": rows,
        "incomplete": incomplete,
        "source_sha256": {
            str(run_spec_path.relative_to(ROOT)): sha256(run_spec_path),
            str(paths_path.relative_to(ROOT)): sha256(paths_path),
        },
    }
    summary_path = outdir / "multistart_summary.json"
    write_json(summary_path, summary)
    files = sorted(path for path in outdir.iterdir() if path.is_file() and path.name != "checksums.sha256")
    (outdir / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    if summary["status"] != "pass":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
