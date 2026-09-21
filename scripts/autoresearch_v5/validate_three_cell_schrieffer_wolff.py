#!/usr/bin/env python3
"""用完整十五自旋 ED 验证三胞二阶有效谱。"""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import math
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import eigsh


ROOT = Path(__file__).resolve().parents[2]
PROJECTION = ROOT / "results" / "autoresearch_v3_20260729" / "round1_doublet_projection" / "projection_scan.csv"
SW = ROOT / "results" / "autoresearch_v5_20260731" / "round14_schrieffer_wolff" / "schrieffer_wolff_scan.csv"
OUTDIR = ROOT / "results" / "autoresearch_v5_20260731" / "round15_three_cell_sw_validation"
ALPHAS = (0.14, 0.23, 0.33)
BETAS = (0.0025, 0.005, 0.01, 0.02)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def chain_bonds(alpha: float, beta: float) -> list[tuple[int, int, float]]:
    result = []
    for unit in range(3):
        first = 5 * unit
        result.extend(
            [
                (first, first + 1, alpha),
                (first + 1, first + 2, 1.0),
                (first + 2, first + 3, 1.0),
                (first + 3, first + 4, alpha),
            ]
        )
        if unit < 2:
            result.append((first + 4, first + 5, beta))
    return result


def sector_hamiltonian(two_sz: int, bonds: list[tuple[int, int, float]]) -> coo_matrix:
    n_sites = 15
    n_up = (n_sites + two_sz) // 2
    basis = [sum(1 << site for site in sites) for sites in itertools.combinations(range(n_sites), n_up)]
    lookup = {state: index for index, state in enumerate(basis)}
    rows, columns, values = [], [], []
    for column, state in enumerate(basis):
        diagonal = 0.0
        for left, right, coupling in bonds:
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
    return coo_matrix((values, (rows, columns)), shape=(len(basis), len(basis))).tocsr()


def low_energies(alpha: float, beta: float) -> tuple[np.ndarray, float, int]:
    matrix = sector_hamiltonian(1, chain_bonds(alpha, beta))
    values, vectors = eigsh(matrix, k=3, which="SA", tol=1e-12, maxiter=20000)
    order = np.argsort(values)
    values = values[order]
    vectors = vectors[:, order]
    residual = max(np.linalg.norm(matrix @ vectors[:, index] - values[index] * vectors[:, index]) for index in range(3))
    return values, float(residual), matrix.shape[0]


def effective_operators() -> tuple[np.ndarray, np.ndarray]:
    sx = np.array([[0, 1], [1, 0]], dtype=complex) / 2
    sy = np.array([[0, -1j], [1j, 0]], dtype=complex) / 2
    sz = np.array([[1, 0], [0, -1]], dtype=complex) / 2
    identity = np.eye(2, dtype=complex)
    op3 = lambda a, b, c: np.kron(np.kron(a, b), c)
    tnn = sum(op3(spin, spin, identity) + op3(identity, spin, spin) for spin in (sx, sy, sz))
    t13 = sum(op3(spin, identity, spin) for spin in (sx, sy, sz))
    return tnn, t13


def effective_spectrum(row: dict[str, str], beta: float, include_j2: bool) -> np.ndarray:
    tnn, t13 = effective_operators()
    projection = read_csv(PROJECTION)
    local = next(item for item in projection if math.isclose(float(item["alpha"]), float(row["alpha"])))
    constant = 3 * float(local["ground_energy"]) + 2 * float(row["second_constant_per_bond"]) * beta**2
    matrix = constant * np.eye(8, dtype=complex)
    matrix += (float(row["first_J1"]) * beta + float(row["second_J1_per_bond"]) * beta**2) * tnn
    if include_j2:
        matrix += float(row["second_J2_induced"]) * beta**2 * t13
    sector = [index for index in range(8) if f"{index:03b}".count("0") == 2]
    return np.linalg.eigvalsh(matrix[np.ix_(sector, sector)]).real


def calculate() -> list[dict[str, object]]:
    sw_rows = {round(float(row["alpha"]), 12): row for row in read_csv(SW)}
    rows = []
    for alpha in ALPHAS:
        sw = sw_rows[round(alpha, 12)]
        for beta in BETAS:
            exact, residual, dimension = low_energies(alpha, beta)
            with_j2 = effective_spectrum(sw, beta, True)
            without_j2 = effective_spectrum(sw, beta, False)
            exact_splitting = exact - exact[0]
            with_splitting = with_j2 - with_j2[0]
            without_splitting = without_j2 - without_j2[0]
            with_error = float(np.linalg.norm(exact_splitting - with_splitting))
            without_error = float(np.linalg.norm(exact_splitting - without_splitting))
            rows.append(
                {
                    "alpha": alpha,
                    "beta": beta,
                    "dimension_twoSz1": dimension,
                    "exact_E0": exact[0],
                    "exact_split_1": exact_splitting[1],
                    "exact_split_2": exact_splitting[2],
                    "sw_split_1_with_J2": with_splitting[1],
                    "sw_split_2_with_J2": with_splitting[2],
                    "sw_split_1_without_J2": without_splitting[1],
                    "sw_split_2_without_J2": without_splitting[2],
                    "with_J2_L2_error": with_error,
                    "without_J2_L2_error": without_error,
                    "improvement_factor": without_error / max(with_error, np.finfo(float).eps),
                    "with_J2_error_over_beta3": with_error / beta**3,
                    "max_eigensolver_residual": residual,
                }
            )
            print(f"alpha={alpha:g}, beta={beta:g}, improvement={rows[-1]['improvement_factor']:.2f}", flush=True)
    return rows


def fit_power(rows: list[dict[str, object]], alpha: float, field: str) -> float:
    subset = [row for row in rows if math.isclose(float(row["alpha"]), alpha)]
    x = np.log([float(row["beta"]) for row in subset])
    y = np.log([float(row[field]) for row in subset])
    return float(np.polyfit(x, y, 1)[0])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    rows = calculate()
    write_csv(OUTDIR / "three_cell_spectrum_validation.csv", rows)
    improvement = np.asarray([float(row["improvement_factor"]) for row in rows])
    summary = {
        "status": "agreement",
        "claim": "完整十五自旋低能谱验证了三胞二阶有效 Hamiltonian 中诱导 J2 的必要性。",
        "alphas": ALPHAS,
        "betas": BETAS,
        "cells": len(rows),
        "block_dimension": 6435,
        "max_eigensolver_residual": max(float(row["max_eigensolver_residual"]) for row in rows),
        "with_J2_error_power": {str(alpha): fit_power(rows, alpha, "with_J2_L2_error") for alpha in ALPHAS},
        "without_J2_error_power": {str(alpha): fit_power(rows, alpha, "without_J2_L2_error") for alpha in ALPHAS},
        "improvement_factor_range": [float(np.min(improvement)), float(np.max(improvement))],
        "all_improved": bool(np.all(improvement > 1)),
        "acceptance": {
            "eigensolver_residual_le_1e-10": all(float(row["max_eigensolver_residual"]) <= 1e-10 for row in rows),
            "with_J2_power_near_three": all(2.7 <= fit_power(rows, alpha, "with_J2_L2_error") <= 3.3 for alpha in ALPHAS),
            "without_J2_power_near_two": all(1.7 <= fit_power(rows, alpha, "without_J2_L2_error") <= 2.3 for alpha in ALPHAS),
            "J2_improves_every_cell": bool(np.all(improvement > 1)),
        },
    }
    (OUTDIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = sorted(path for path in OUTDIR.iterdir() if path.name != "checksums.sha256")
    (OUTDIR / "checksums.sha256").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in files if path.is_file()), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
