#!/usr/bin/env python3
"""在固定 Sz 扇区计算小系统精确动力学谱。"""

from __future__ import annotations

import argparse
import csv
import json
from itertools import combinations
from pathlib import Path

import numpy as np


def sector_basis(length: int) -> tuple[list[int], dict[int, int]]:
    states = [sum(1 << site for site in sites) for sites in combinations(range(length), length // 2)]
    return states, {state: index for index, state in enumerate(states)}


def bonds(n_units: int, alpha: float, beta: float) -> list[tuple[int, int, float]]:
    result: list[tuple[int, int, float]] = []
    for unit in range(n_units):
        first = 5 * unit
        result.extend([
            (first, first + 1, alpha),
            (first + 1, first + 2, 1.0),
            (first + 2, first + 3, 1.0),
            (first + 3, first + 4, alpha),
        ])
        if unit + 1 < n_units:
            result.append((first + 4, first + 5, beta))
    return result


def hamiltonian(states: list[int], state_index: dict[int, int], bond_list: list[tuple[int, int, float]]) -> np.ndarray:
    matrix = np.zeros((len(states), len(states)), dtype=np.float64)
    for column, state in enumerate(states):
        for left, right, coupling in bond_list:
            left_up = (state >> left) & 1
            right_up = (state >> right) & 1
            matrix[column, column] += coupling * (0.25 if left_up == right_up else -0.25)
            if left_up != right_up:
                flipped = state ^ (1 << left) ^ (1 << right)
                matrix[state_index[flipped], column] += 0.5 * coupling
    return matrix


def source_diagonal(states: list[int], length: int, momentum: float) -> np.ndarray:
    phases = np.exp(1j * momentum * np.arange(1, length + 1)) / np.sqrt(length)
    result = np.empty(len(states), dtype=np.complex128)
    for index, state in enumerate(states):
        spins = np.array([0.5 if (state >> site) & 1 else -0.5 for site in range(length)])
        result[index] = np.dot(phases, spins)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--alpha", type=float, required=True)
    parser.add_argument("--beta", type=float, required=True)
    parser.add_argument("--n-units", type=int, default=2)
    parser.add_argument("--q-over-pi", type=float, default=1.0)
    parser.add_argument("--eta", type=float, default=0.1)
    parser.add_argument("--omega-min", type=float, default=0.0)
    parser.add_argument("--omega-max", type=float, default=3.0)
    parser.add_argument("--omega-step", type=float, default=0.05)
    args = parser.parse_args()
    if not 0.0 <= args.alpha <= 1.0:
        raise SystemExit("alpha 必须位于 [0,1]")
    if not 0.0 <= args.beta <= 1.0:
        raise SystemExit("beta 必须位于 [0,1]")
    length = 5 * args.n_units
    if length % 2:
        raise SystemExit("oracle 当前要求偶数格点")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    states, state_index = sector_basis(length)
    matrix = hamiltonian(states, state_index, bonds(args.n_units, args.alpha, args.beta))
    energies, vectors = np.linalg.eigh(matrix)
    source = source_diagonal(states, length, args.q_over_pi * np.pi) * vectors[:, 0]
    amplitudes = vectors.conj().T @ source
    weights = np.abs(amplitudes) ** 2
    gaps = energies - energies[0]
    omegas = np.arange(args.omega_min, args.omega_max + args.omega_step / 2, args.omega_step)
    spectrum = np.array([
        np.sum(weights * args.eta / np.pi / ((omega - gaps) ** 2 + args.eta**2))
        for omega in omegas
    ])

    with (outdir / "exact_spectrum.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["q_over_pi", "omega", "intensity"])
        writer.writerows((args.q_over_pi, omega, value) for omega, value in zip(omegas, spectrum))

    summary = {
        "method": "exact_diagonalization_fixed_sz",
        "alpha": args.alpha,
        "beta": args.beta,
        "n_units": args.n_units,
        "L": length,
        "sector": "Sz=0",
        "hilbert_dimension": len(states),
        "q_over_pi": args.q_over_pi,
        "eta": args.eta,
        "ground_energy": float(energies[0]),
        "source_norm_squared": float(np.vdot(source, source).real),
        "sum_rule_weight": float(weights.sum()),
        "peak_omega": float(omegas[np.argmax(spectrum)]),
        "integrated_weight": float(np.trapezoid(spectrum, omegas)),
    }
    (outdir / "exact_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
