#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用两个完整五聚体的扇区 ED 检验一阶有效链。"""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import eigsh


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "autoresearch_v3_20260729" / "round3_two_pentamer_ed"
PROJECTION = ROOT / "results" / "autoresearch_v3_20260729" / "round1_doublet_projection" / "representative.csv"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bonds(alpha: float, beta: float) -> list[tuple[int, int, float]]:
    result = []
    for unit in range(2):
        first = 5 * unit
        result.extend(
            [
                (first, first + 1, alpha),
                (first + 1, first + 2, 1.0),
                (first + 2, first + 3, 1.0),
                (first + 3, first + 4, alpha),
            ]
        )
    result.append((4, 5, beta))
    return result


def sector_hamiltonian(target_sz: int, chain_bonds: list[tuple[int, int, float]]):
    n_sites = 10
    n_up = n_sites // 2 + target_sz
    basis = [sum(1 << site for site in sites) for sites in itertools.combinations(range(n_sites), n_up)]
    lookup = {state: index for index, state in enumerate(basis)}
    rows, columns, values = [], [], []
    for column, state in enumerate(basis):
        diagonal = 0.0
        for left, right, coupling in chain_bonds:
            left_bit = (state >> left) & 1
            right_bit = (state >> right) & 1
            diagonal += coupling * (0.25 if left_bit == right_bit else -0.25)
            if left_bit != right_bit:
                flipped = state ^ (1 << left) ^ (1 << right)
                rows.append(lookup[flipped])
                columns.append(column)
                values.append(0.5 * coupling)
        rows.append(column)
        columns.append(column)
        values.append(diagonal)
    matrix = coo_matrix((values, (rows, columns)), shape=(len(basis), len(basis))).tocsr()
    return matrix


def ground_energy(target_sz: int, chain_bonds: list[tuple[int, int, float]]) -> tuple[float, float, int]:
    matrix = sector_hamiltonian(target_sz, chain_bonds)
    values, vectors = eigsh(matrix, k=1, which="SA", tol=1e-13)
    residual = np.linalg.norm(matrix @ vectors[:, 0] - values[0] * vectors[:, 0])
    return float(values[0]), float(residual), matrix.shape[0]


def projections() -> dict[float, dict[str, float]]:
    with PROJECTION.open(encoding="utf-8", newline="") as handle:
        return {
            float(row["alpha"]): {key: float(value) for key, value in row.items() if key != "alpha"}
            for row in csv.DictReader(handle)
        }


def calculate() -> list[dict[str, float | int]]:
    local_data = projections()
    rows = []
    for alpha in (0.14, 0.23, 0.33):
        local = local_data[alpha]
        for beta in (0.0025, 0.005, 0.01, 0.02, 0.05, 0.10, 0.20):
            energy0, residual0, dimension0 = ground_energy(0, bonds(alpha, beta))
            energy1, residual1, dimension1 = ground_energy(1, bonds(alpha, beta))
            jeff = beta * local["jeff_over_beta"]
            energy_effective = 2 * local["ground_energy"] - 0.75 * jeff
            gap = energy1 - energy0
            rows.append(
                {
                    "alpha": alpha,
                    "beta": beta,
                    "local_gap": local["local_gap"],
                    "beta_over_local_gap": beta / local["local_gap"],
                    "jeff": jeff,
                    "energy_full": energy0,
                    "energy_effective": energy_effective,
                    "energy_residual": energy0 - energy_effective,
                    "energy_residual_over_beta2": (energy0 - energy_effective) / beta**2,
                    "gap_full": gap,
                    "gap_effective": jeff,
                    "gap_ratio": gap / jeff,
                    "max_eigensolver_residual": max(residual0, residual1),
                    "dimension_sz0": dimension0,
                    "dimension_sz1": dimension1,
                }
            )
    return rows


def fit_power(rows: list[dict[str, float | int]], alpha: float, field: str) -> float:
    subset = [row for row in rows if row["alpha"] == alpha and row["beta"] <= 0.05]
    x = np.log([float(row["beta"]) for row in subset])
    y = np.log([abs(float(row[field])) for row in subset])
    return float(np.polyfit(x, y, 1)[0])


def make_figure(rows: list[dict[str, float | int]]) -> None:
    plt.rcParams.update({"font.size": 10, "axes.grid": True, "grid.alpha": 0.25})
    figure, axes = plt.subplots(1, 3, figsize=(12, 3.5), constrained_layout=True)
    for alpha in (0.14, 0.23, 0.33):
        subset = [row for row in rows if row["alpha"] == alpha]
        beta = np.array([float(row["beta"]) for row in subset])
        residual = np.array([abs(float(row["energy_residual"])) for row in subset])
        axes[0].loglog(beta, residual, "o-", label=fr"$\alpha={alpha}$")
        axes[1].plot(beta, [row["energy_residual_over_beta2"] for row in subset], "o-", label=fr"$\alpha={alpha}$")
        axes[2].plot(beta, [row["gap_ratio"] for row in subset], "o-", label=fr"$\alpha={alpha}$")
    reference_beta = np.array([0.0025, 0.05])
    anchor = min(abs(float(row["energy_residual"])) / float(row["beta"]) ** 2 for row in rows)
    axes[0].loglog(reference_beta, anchor * reference_beta**2, "k--", label=r"$\beta^2$")
    axes[0].set(xlabel=r"$\beta$", ylabel=r"$|E-E_{eff}|$", title="Energy residual")
    axes[1].set(xlabel=r"$\beta$", ylabel=r"$(E-E_{eff})/\beta^2$", title="Second-order coefficient")
    axes[2].set(xlabel=r"$\beta$", ylabel=r"$\Delta/\Delta_{eff}$", title="Spin-gap ratio")
    for axis in axes:
        axis.legend(frameon=False)
    figure.savefig(OUT / "two_pentamer_effective_ed.png", dpi=220)
    plt.close(figure)


def main() -> None:
    if OUT.exists() and any(OUT.iterdir()):
        raise SystemExit(f"拒绝覆盖已有结果: {OUT}")
    OUT.mkdir(parents=True, exist_ok=True)
    rows = calculate()
    with (OUT / "comparison.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "max_eigensolver_residual": max(float(row["max_eigensolver_residual"]) for row in rows),
        "energy_residual_power": {str(alpha): fit_power(rows, alpha, "energy_residual") for alpha in (0.14, 0.23, 0.33)},
        "small_beta_gap_error_power": {
            str(alpha): fit_power(
                [{**row, "gap_error": float(row["gap_full"]) - float(row["gap_effective"])} for row in rows],
                alpha,
                "gap_error",
            )
            for alpha in (0.14, 0.23, 0.33)
        },
        "gap_ratio_at_beta_0025": {
            str(row["alpha"]): row["gap_ratio"] for row in rows if row["beta"] == 0.0025
        },
        "gap_ratio_at_beta_020": {str(row["alpha"]): row["gap_ratio"] for row in rows if row["beta"] == 0.20},
        "all_residuals_pass": all(float(row["max_eigensolver_residual"]) <= 1e-10 for row in rows),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    make_figure(rows)
    outputs = sorted(path for path in OUT.iterdir() if path.name != "checksums.sha256")
    (OUT / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in outputs), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
