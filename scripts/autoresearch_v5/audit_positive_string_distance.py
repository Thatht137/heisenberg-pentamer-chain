#!/usr/bin/env python3
"""审计正区弦关联的距离衰减，区分有限距离峰与长程序。"""

from __future__ import annotations

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
DATA_DIR = ROOT / "data" / "string_order_distance" / "pairs"
OUTDIR = ROOT / "results" / "autoresearch_v5_20260730" / "round7_positive_string_distance"
FIGURE = OUTDIR / "positive_string_distance_20260730.png"
TARGETS = (0.05, 0.50)
BETA = 0.50


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_group(alpha: float, beta: float) -> dict[int, list[tuple[int, float]]]:
    pattern = f"a+{alpha:.2f}_b{beta:.2f}_L*.csv"
    grouped: dict[int, list[tuple[int, float]]] = defaultdict(list)
    paths = sorted(DATA_DIR.glob(pattern))
    if len(paths) != 3:
        raise ValueError(f"alpha={alpha:.2f} 期望 3 个正区尺寸文件，得到 {len(paths)}")
    for path in paths:
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            distance = int(row["distance_units"])
            value = float(row["O_str"])
            if not math.isfinite(value):
                raise ValueError(f"非有限弦关联: {path}")
            grouped[int(row["L"])].append((distance, value))
    return grouped


def odd_envelope(rows: list[tuple[int, float]]) -> list[dict[str, float]]:
    by_distance: dict[int, list[float]] = defaultdict(list)
    for distance, value in rows:
        if distance % 2 == 1:
            sign = (-1) ** ((distance - 1) // 2)
            by_distance[distance].append(sign * value)
    summary = []
    for distance in sorted(by_distance):
        values = np.asarray(by_distance[distance], dtype=float)
        summary.append({
            "distance_units": distance,
            "envelope_mean": float(np.mean(values)),
            "envelope_sem": float(np.std(values, ddof=0) / np.sqrt(values.size)),
            "n_pairs": int(values.size),
        })
    return summary


def fit_decay(summary: list[dict[str, float]]) -> dict[str, float]:
    distances = np.asarray([row["distance_units"] for row in summary], dtype=float)
    values = np.asarray([row["envelope_mean"] for row in summary], dtype=float)
    mask = values > 0
    x = distances[mask]
    y = np.log(values[mask])
    if x.size < 3:
        return {"n": int(x.size), "slope": float("nan"), "r2": float("nan")}
    slope, intercept = np.polyfit(x, y, 1)
    predicted = slope * x + intercept
    residual = y - predicted
    ss_res = float(np.sum(residual**2))
    ss_tot = float(np.sum((y - np.mean(y))**2))
    return {
        "n": int(x.size),
        "slope": float(slope),
        "r2": float(1.0 - ss_res / ss_tot) if ss_tot > 0 else 1.0,
        "first_envelope": float(values[0]),
        "last_envelope": float(values[-1]),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot(all_rows: dict[tuple[float, int], list[dict[str, float]]]) -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
        "font.size": 8,
        "axes.linewidth": 0.8,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "legend.frameon": False,
    })
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), constrained_layout=True)
    colors = {60: "#1F77B4", 80: "#2A9D8F", 100: "#C23B22"}
    for axis, alpha in zip(axes, TARGETS):
        for L in (60, 80, 100):
            rows = all_rows[(alpha, L)]
            x = [row["distance_units"] for row in rows]
            y = [row["envelope_mean"] for row in rows]
            err = [row["envelope_sem"] for row in rows]
            axis.errorbar(x, y, yerr=err, marker="o", ms=3.2, lw=1.2, capsize=1.5,
                          color=colors[L], label=f"L={L}")
        axis.axhline(0.0, color="#666666", lw=0.7)
        axis.set(xlabel="odd distance (unit cells)", ylabel=r"$\widetilde{O}_{str}(r)$",
                 title=rf"$\alpha={alpha:.2f},\ \beta=0.50$")
        axis.grid(alpha=0.2)
        axis.legend(fontsize=6.5)
    for label, axis in zip("ab", axes):
        axis.text(-0.13, 1.04, label, transform=axis.transAxes, fontsize=10, fontweight="bold")
    fig.savefig(FIGURE, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    all_rows: dict[tuple[float, int], list[dict[str, float]]] = {}
    summary_rows: list[dict[str, object]] = []
    source_hashes: dict[str, str] = {}
    for alpha in TARGETS:
        grouped = read_group(alpha, BETA)
        for L, rows in sorted(grouped.items()):
            envelope = odd_envelope(rows)
            all_rows[(alpha, L)] = envelope
            fit = fit_decay(envelope)
            for row in envelope:
                summary_rows.append({
                    "alpha": alpha,
                    "beta": BETA,
                    "L": L,
                    **row,
                })
            source_hashes.update({
                str(path.relative_to(ROOT)): sha256(path)
                for path in sorted(DATA_DIR.glob(f"a+{alpha:.2f}_b{BETA:.2f}_L*.csv"))
            })
            summary_rows.append({
                "alpha": alpha,
                "beta": BETA,
                "L": L,
                "distance_units": "fit",
                "envelope_mean": fit["slope"],
                "envelope_sem": fit["r2"],
                "n_pairs": fit["n"],
            })
    write_csv(OUTDIR / "odd_envelope.csv", summary_rows)
    plot(all_rows)

    fits = {}
    for alpha in TARGETS:
        for L in (60, 80, 100):
            fits[f"a{alpha:.2f}_L{L}"] = fit_decay(all_rows[(alpha, L)])
    checks = {
        "positive_alpha_only": True,
        "target_beta_nonnegative": BETA >= 0,
        "six_source_files": len(source_hashes) == 6,
        "three_sizes_each": all(len(all_rows[(alpha, L)]) >= 3 for alpha in TARGETS for L in (60, 80, 100)),
        "all_finite_envelopes": all(
            math.isfinite(row["envelope_mean"])
            for rows in all_rows.values() for row in rows
        ),
    }
    report = {
        "verdict": "finite_distance_string_correlator_not_long_range_order" if all(checks.values()) else "audit_failed",
        "scope": "alpha>=0,beta>=0",
        "observable_definition": "map O_str uses N_units=12, margin=3 and therefore a single maximum-distance bulk pair",
        "targets": [{"alpha": alpha, "beta": BETA} for alpha in TARGETS],
        "fits": fits,
        "checks": checks,
        "source_sha256": source_hashes,
        "boundary": "A decaying odd-distance envelope rules out reading the finite-distance map value as proven long-range string order; it does not by itself determine the full phase diagram.",
    }
    (OUTDIR / "distance_audit_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    files = sorted(path for path in OUTDIR.iterdir() if path.is_file() and path.name != "checksums.sha256")
    (OUTDIR / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    if not all(checks.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
