#!/usr/bin/env python3
"""审计现有正 alpha 数据并生成复用矩阵。"""

from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "five_rounds_20260729" / "round1_inventory"
DATA = ROOT / "data"


def read_phase_map(path: Path) -> tuple[list[dict[str, float]], dict[str, object]]:
    rows: list[dict[str, float]] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            row = {key: float(raw[key]) for key in ("alpha", "beta", "O_str", "energy")}
            if not all(math.isfinite(value) for value in row.values()):
                raise ValueError(f"发现非有限值: {row}")
            rows.append(row)

    grouped: dict[tuple[float, float], list[dict[str, float]]] = defaultdict(list)
    for row in rows:
        grouped[(row["alpha"], row["beta"])].append(row)

    selected = [min(group, key=lambda item: item["energy"]) for group in grouped.values()]
    positive = sorted(
        (row for row in selected if row["alpha"] >= -1e-12),
        key=lambda row: (row["alpha"], row["beta"]),
    )
    duplicate_groups = [group for group in grouped.values() if len(group) > 1]
    max_energy_spread = max(
        (max(row["energy"] for row in group) - min(row["energy"] for row in group) for group in duplicate_groups),
        default=0.0,
    )
    max_order_spread = max(
        (max(row["O_str"] for row in group) - min(row["O_str"] for row in group) for group in duplicate_groups),
        default=0.0,
    )
    audit = {
        "path": str(path.relative_to(ROOT)),
        "rows": len(rows),
        "unique_pairs": len(grouped),
        "duplicate_rows": len(rows) - len(grouped),
        "duplicate_groups": len(duplicate_groups),
        "max_duplicate_energy_spread": max_energy_spread,
        "max_duplicate_order_spread": max_order_spread,
        "positive_unique_pairs": len(positive),
        "positive_alpha_values": len({row["alpha"] for row in positive}),
        "beta_values": len({row["beta"] for row in positive}),
    }
    return positive, audit


def write_clean_phase(rows: list[dict[str, float]]) -> Path:
    path = OUT / "positive_phase_map_clean.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["alpha", "beta", "O_str", "energy"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def plot_phase(rows: list[dict[str, float]], audit: dict[str, object]) -> Path:
    alphas = sorted({row["alpha"] for row in rows})
    betas = sorted({row["beta"] for row in rows})
    values = np.full((len(betas), len(alphas)), np.nan)
    alpha_index = {value: index for index, value in enumerate(alphas)}
    beta_index = {value: index for index, value in enumerate(betas)}
    for row in rows:
        values[beta_index[row["beta"]], alpha_index[row["alpha"]]] = row["O_str"]

    fig, ax = plt.subplots(figsize=(8.2, 5.2), constrained_layout=True)
    image = ax.pcolormesh(alphas, betas, values, shading="nearest", cmap="viridis")
    colorbar = fig.colorbar(image, ax=ax)
    colorbar.set_label(r"$O_{str}$")
    ax.set_xlabel(r"$\alpha=J_2/J_1$")
    ax.set_ylabel(r"$\beta=J_3/J_1$")
    ax.set_title("Positive-alpha reconnaissance map")
    ax.text(
        0.01,
        0.99,
        f"{audit['positive_unique_pairs']} unique points\n"
        f"{audit['duplicate_rows']} duplicate rows removed",
        transform=ax.transAxes,
        ha="left",
        va="top",
        color="white",
        fontsize=9,
        bbox={"facecolor": "black", "alpha": 0.55, "pad": 5},
    )
    path = OUT / "positive_phase_map_audit.png"
    fig.savefig(path, dpi=220)
    plt.close(fig)
    return path


def count_positive_files(directory: Path, pattern: str = "*.csv") -> int:
    if not directory.exists():
        return 0
    count = 0
    for path in directory.rglob(pattern):
        match = re.search(r"(?:^|[_-])a(?:lpha=)?([+-]?\d+(?:\.\d+)?)", path.name)
        if match is None or float(match.group(1)) >= 0:
            count += 1
    return count


def build_reuse_matrix() -> list[dict[str, object]]:
    positive_tebd_csv = [path for path in DATA.glob("Sqw_tebd_pentamer_alpha=*.csv") if "alpha=-" not in path.name]
    positive_raw = [path for path in DATA.glob("NDSF_pentamer_alpha=*.jld2") if "alpha=-" not in path.name]
    return [
        {
            "asset": "single_pentamer_ed",
            "location": "data/single_pentamer_levels.csv",
            "positive_files": int((DATA / "single_pentamer_levels.csv").exists()),
            "grade": "accept",
            "next_action": "reuse_positive_slice",
        },
        {
            "asset": "phase_map",
            "location": "data/phase_diagram_80x60_hires.csv",
            "positive_files": 1,
            "grade": "reconnaissance",
            "next_action": "validate_three_positive_points",
        },
        {
            "asset": "spin_gap",
            "location": "data/spin_gap/tasks",
            "positive_files": count_positive_files(DATA / "spin_gap" / "tasks"),
            "grade": "baseline",
            "next_action": "reuse_for_size_trend",
        },
        {
            "asset": "bond_correlations",
            "location": "data/bond_correlations",
            "positive_files": count_positive_files(DATA / "bond_correlations"),
            "grade": "baseline",
            "next_action": "reuse",
        },
        {
            "asset": "static_structure_factor",
            "location": "data/static_structure_factor",
            "positive_files": count_positive_files(DATA / "static_structure_factor"),
            "grade": "baseline",
            "next_action": "reuse",
        },
        {
            "asset": "entanglement_spectrum",
            "location": "data/entanglement_spectrum",
            "positive_files": count_positive_files(DATA / "entanglement_spectrum"),
            "grade": "baseline",
            "next_action": "reuse_with_convergence_caveat",
        },
        {
            "asset": "positive_tebd_spectrum",
            "location": "data/Sqw_tebd_pentamer_alpha=*.csv",
            "positive_files": len(positive_tebd_csv),
            "grade": "mixed",
            "next_action": "retain_only_points_with_raw_correlator",
        },
        {
            "asset": "positive_tebd_raw",
            "location": "data/NDSF_pentamer_alpha=*.jld2",
            "positive_files": len(positive_raw),
            "grade": "pilot",
            "next_action": "reuse_for_report_and_dt_baseline",
        },
    ]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    phase_rows, phase_audit = read_phase_map(DATA / "phase_diagram_80x60_hires.csv")
    clean_path = write_clean_phase(phase_rows)
    figure_path = plot_phase(phase_rows, phase_audit)
    matrix = build_reuse_matrix()

    matrix_path = OUT / "reuse_matrix.csv"
    with matrix_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(matrix[0]))
        writer.writeheader()
        writer.writerows(matrix)

    inventory = {
        "scope": {"alpha_min": 0.0, "alpha_max": 1.0, "negative_alpha_excluded": True},
        "phase_map": phase_audit,
        "reuse_matrix": matrix,
        "outputs": [str(path.relative_to(ROOT)) for path in (clean_path, figure_path, matrix_path)],
    }
    inventory_path = OUT / "inventory.json"
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(phase_audit, ensure_ascii=False, indent=2))
    print(f"wrote {inventory_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

