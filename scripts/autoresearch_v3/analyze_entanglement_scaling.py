#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""汇总纠缠熵扫描并生成两条中心荷诊断。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
WINDOWS = ((0.10, 0.90), (0.15, 0.85), (0.20, 0.80), (0.25, 0.75))
CENTRAL_WINDOW_INDEX = 2


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_checksums(cell: Path) -> bool:
    path = cell / "checksums.sha256"
    if not path.is_file():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        target = cell / name
        if not target.is_file() or sha256(target) != expected:
            return False
    return True


def read_profile(path: Path) -> list[dict[str, object]]:
    rows = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append({
                "bond": int(row["bond"]),
                "cut_class": int(row["cut_class"]),
                "unit_cut": int(row["unit_cut"]),
                "intercell": row["intercell"].lower() == "true",
                "entropy": float(row["entropy"]),
            })
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"没有可写数据: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fit_profile(profile: list[dict[str, object]], units: int, window: tuple[float, float]) -> dict[str, float]:
    selected = [
        row for row in profile
        if row["intercell"] and window[0] * units <= int(row["unit_cut"]) <= window[1] * units
    ]
    cuts = np.asarray([int(row["unit_cut"]) for row in selected], dtype=float)
    entropy = np.asarray([float(row["entropy"]) for row in selected])
    if len(cuts) < 5 or len(np.unique(cuts.astype(int) % 2)) < 2:
        raise ValueError(f"拟合点不足: N={units}, window={window}")
    chord = np.log((2.0 * units / np.pi) * np.sin(np.pi * cuts / units))
    parity = cuts.astype(int) % 2
    design = np.column_stack([chord, parity == 0, parity == 1])
    coefficients, _, _, _ = np.linalg.lstsq(design, entropy, rcond=None)
    residual = entropy - design @ coefficients
    dof = len(entropy) - design.shape[1]
    variance = float(np.sum(residual**2) / dof)
    covariance = variance * np.linalg.inv(design.T @ design)
    return {
        "c": 6.0 * float(coefficients[0]),
        "stat_error": 6.0 * math.sqrt(max(float(covariance[0, 0]), 0.0)),
        "residual_rms": math.sqrt(float(np.mean(residual**2))),
        "points": len(selected),
    }


def robust_profile_fit(high: list[dict[str, object]], low: list[dict[str, object]], units: int) -> dict[str, float]:
    high_fits = [fit_profile(high, units, window) for window in WINDOWS]
    low_fit = fit_profile(low, units, WINDOWS[CENTRAL_WINDOW_INDEX])
    central = high_fits[CENTRAL_WINDOW_INDEX]
    window_error = max(abs(item["c"] - central["c"]) for item in high_fits)
    bond_error = abs(central["c"] - low_fit["c"])
    total_error = math.sqrt(central["stat_error"] ** 2 + window_error**2 + bond_error**2)
    return {
        "c_profile": central["c"],
        "c_error": total_error,
        "stat_error": central["stat_error"],
        "window_error": window_error,
        "bond_dimension_error": bond_error,
        "residual_rms": central["residual_rms"],
        "fit_points": int(central["points"]),
    }


def linear_fit(rows: list[dict[str, object]]) -> tuple[float, float]:
    sizes = np.asarray([float(row["N_units"]) for row in rows])
    entropy = np.asarray([float(row["entropy"]) for row in rows])
    errors = np.asarray([float(row["entropy_error"]) for row in rows])
    design = np.column_stack([np.log(sizes), np.ones_like(sizes)])
    weighted = design / errors[:, None]
    target = entropy / errors
    coefficients, _, _, _ = np.linalg.lstsq(weighted, target, rcond=None)
    return float(coefficients[0]), float(coefficients[1])


def plot_summary(outdir: Path, profiles: dict[tuple[str, int, int], list[dict[str, object]]], mid_rows: list[dict[str, object]], fit_rows: list[dict[str, object]]) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(12, 8.5))
    colors = plt.cm.viridis(np.linspace(0.12, 0.88, 5))
    for axis, model in zip(axes[0], ("heisenberg", "pentamer")):
        for color, units in zip(colors, (8, 12, 16, 20, 24)):
            rows = [row for row in profiles[(model, units, 400)] if row["intercell"]]
            cuts = np.asarray([int(row["unit_cut"]) for row in rows])
            entropy = np.asarray([float(row["entropy"]) for row in rows])
            axis.plot(cuts / units, entropy, "o-", ms=2.8, lw=1.0, color=color, label=f"N={units}")
        axis.set_xlabel("effective cut m/N")
        axis.set_ylabel("S(m)")
        axis.set_title("Heisenberg oracle" if model == "heisenberg" else "pentamer inter-cell cuts")
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8, ncol=2)

    axis = axes[1, 0]
    for model, marker, color in (("heisenberg", "s", "tab:green"), ("pentamer", "o", "tab:blue")):
        selected = [row for row in mid_rows if row["model"] == model]
        sizes = np.asarray([int(row["N_units"]) for row in selected])
        entropy = np.asarray([float(row["entropy"]) for row in selected])
        errors = np.asarray([float(row["entropy_error"]) for row in selected])
        slope, intercept = linear_fit(selected)
        axis.errorbar(np.log(sizes), entropy, yerr=errors, fmt=marker, capsize=3, color=color, label=f"{model}, 6A={6*slope:.3f}")
        grid = np.linspace(np.log(sizes.min()), np.log(sizes.max()), 100)
        axis.plot(grid, slope * grid + intercept, color=color, lw=1.2)
    axis.set_xlabel("ln N")
    axis.set_ylabel("S(N/2)")
    axis.set_title("mid-chain size scaling")
    axis.grid(alpha=0.25)
    axis.legend(fontsize=8)

    axis = axes[1, 1]
    for model, marker, color in (("heisenberg", "s", "tab:green"), ("pentamer", "o", "tab:blue")):
        selected = [row for row in fit_rows if row["model"] == model]
        sizes = np.asarray([int(row["N_units"]) for row in selected])
        values = np.asarray([float(row["c_profile"]) for row in selected])
        errors = np.asarray([float(row["c_error"]) for row in selected])
        axis.errorbar(1.0 / sizes, values, yerr=errors, fmt=marker + "-", capsize=3, color=color, label=model)
    axis.axhline(1.0, color="black", ls="--", lw=1, label="target 1")
    axis.set_xlabel("1/N")
    axis.set_ylabel("6 x profile slope")
    axis.set_title("profile estimator")
    axis.grid(alpha=0.25)
    axis.legend(fontsize=8)
    figure.tight_layout()
    figure.savefig(outdir / "entanglement_validation.png", dpi=180)
    plt.close(figure)


def self_test() -> None:
    units = 24
    rows = []
    for cut in range(1, units):
        chord = math.log((2.0 * units / math.pi) * math.sin(math.pi * cut / units))
        rows.append({
            "unit_cut": cut,
            "intercell": True,
            "entropy": chord / 6.0 + (0.31 if cut % 2 == 0 else 0.47),
        })
    result = fit_profile(rows, units, WINDOWS[1])
    if abs(result["c"] - 1.0) > 1e-10:
        raise SystemExit(f"自检失败: c={result['c']}")
    print("SELF_TEST_OK c=1")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", nargs="?")
    parser.add_argument("--outdir")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.run_dir:
        raise SystemExit("缺少 run_dir")
    run_dir = Path(args.run_dir).resolve()
    outdir = Path(args.outdir).resolve() if args.outdir else run_dir / "analysis"
    outdir.mkdir(parents=True, exist_ok=True)
    spec = json.loads((run_dir / "run_spec.json").read_text(encoding="utf-8"))
    expected = {cell["cell_id"] for cell in spec["cells"]}
    cells = sorted((run_dir / "cells").glob("cell-*"))
    found = {cell.name for cell in cells}
    if found != expected:
        raise SystemExit(f"cell 集合不一致: missing={sorted(expected-found)}, extra={sorted(found-expected)}")

    summary_rows = []
    all_profile_rows = []
    profiles: dict[tuple[str, int, int], list[dict[str, object]]] = {}
    for cell in cells:
        manifest = json.loads((cell / "manifest.json").read_text(encoding="utf-8"))
        params = manifest["params"]
        settings = manifest["settings"]
        diagnostics = manifest["diagnostics"]
        model = str(params["model"])
        units = int(params["N_units"])
        maxdim = int(settings["maxdim"])
        checksum_ok = verify_checksums(cell)
        usable = (
            manifest["status"] == "success"
            and checksum_ok
            and abs(float(manifest["observables"]["total_sz"])) <= 1e-8
            and float(diagnostics["variance_per_site"]) <= 1e-8
            and float(diagnostics["final_energy_change"]) <= 1e-8
        )
        production_accepted = (
            usable
            and maxdim == 400
            and float(diagnostics["max_truncation_error"]) <= 1e-8
        )
        summary_rows.append({
            "cell_id": cell.name,
            "model": model,
            "N_units": units,
            "L": int(params["L"]),
            "maxdim": maxdim,
            "actual_maxdim": int(diagnostics["actual_maxdim"]),
            "energy": float(manifest["observables"]["energy"]),
            "variance_per_site": float(diagnostics["variance_per_site"]),
            "max_truncation_error": float(diagnostics["max_truncation_error"]),
            "final_energy_change": float(diagnostics["final_energy_change"]),
            "total_sz": float(manifest["observables"]["total_sz"]),
            "algorithm_seconds": float(diagnostics["algorithm_seconds"]),
            "peak_rss_kb": int(diagnostics["peak_rss_kb"]),
            "checksum_ok": checksum_ok,
            "usable": usable,
            "production_accepted": production_accepted,
        })
        profile = read_profile(cell / "entropy_profile.csv")
        profiles[(model, units, maxdim)] = profile
        for row in profile:
            all_profile_rows.append({"cell_id": cell.name, "model": model, "N_units": units, "L": int(params["L"]), "maxdim": maxdim, **row})

    write_csv(outdir / "cell_summary.csv", summary_rows)
    write_csv(outdir / "entropy_profiles.csv", all_profile_rows)
    if not all(bool(row["usable"]) for row in summary_rows):
        raise SystemExit("至少一个 cell 不可用于收敛误差估计")
    high_rows = [row for row in summary_rows if int(row["maxdim"]) == 400]
    if not all(bool(row["production_accepted"]) for row in high_rows):
        raise SystemExit("至少一个 D=400 cell 未通过生产验收")

    mid_rows = []
    fit_rows = []
    for model in ("heisenberg", "pentamer"):
        for units in (8, 12, 16, 20, 24):
            high = profiles[(model, units, 400)]
            low = profiles[(model, units, 80)]
            center = units // 2
            high_mid = next(float(row["entropy"]) for row in high if row["intercell"] and int(row["unit_cut"]) == center)
            low_mid = next(float(row["entropy"]) for row in low if row["intercell"] and int(row["unit_cut"]) == center)
            mid_rows.append({
                "model": model,
                "N_units": units,
                "entropy": high_mid,
                "entropy_error": max(abs(high_mid - low_mid), 1e-8),
                "D_low": 80,
                "D_high": 400,
            })
            fit_rows.append({"model": model, "N_units": units, **robust_profile_fit(high, low, units)})
    write_csv(outdir / "midchain_scaling.csv", mid_rows)
    write_csv(outdir / "profile_fit_summary.csv", fit_rows)
    for model in ("heisenberg", "pentamer"):
        selected = [row for row in mid_rows if row["model"] == model]
        write_csv(outdir / f"midchain_scaling_{model}.csv", selected)
        write_csv(
            outdir / f"midchain_scaling_{model}_N12plus.csv",
            [row for row in selected if int(row["N_units"]) >= 12],
        )
    plot_summary(outdir, profiles, mid_rows, fit_rows)

    by_model = defaultdict(list)
    for row in mid_rows:
        by_model[str(row["model"])].append(row)
    slopes = {model: 6.0 * linear_fit(rows)[0] for model, rows in by_model.items()}
    profile_largest = {row["model"]: row for row in fit_rows if int(row["N_units"]) == 24}
    comparison = {
        "cells_expected": len(expected),
        "cells_usable": sum(bool(row["usable"]) for row in summary_rows),
        "production_cells_accepted": sum(bool(row["production_accepted"]) for row in summary_rows),
        "all_checksums_ok": all(bool(row["checksum_ok"]) for row in summary_rows),
        "midchain_slope_times_6": slopes,
        "midchain_slope_ratio_pentamer_to_oracle": slopes["pentamer"] / slopes["heisenberg"],
        "largest_profile_estimator": {model: row["c_profile"] for model, row in profile_largest.items()},
        "largest_profile_ratio_pentamer_to_oracle": profile_largest["pentamer"]["c_profile"] / profile_largest["heisenberg"]["c_profile"],
        "max_entropy_D_difference": max(float(row["entropy_error"]) for row in mid_rows),
    }
    (outdir / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    with (outdir / "checksums.sha256").open("w", encoding="utf-8") as handle:
        for path in sorted(outdir.iterdir()):
            if path.is_file() and path.name != "checksums.sha256":
                handle.write(f"{sha256(path)}  {path.name}\n")
    print(json.dumps(comparison, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
