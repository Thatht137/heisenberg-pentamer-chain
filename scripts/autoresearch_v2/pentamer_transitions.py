#!/usr/bin/env python3
"""计算正 alpha 单五聚体能级与 Sz(q) 选择定则。"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "autoresearch_v2_20260729" / "round3_local_transitions"
ALPHAS = (0.14, 0.23, 0.33)


def kron_all(ops: list[np.ndarray]) -> np.ndarray:
    result = ops[0]
    for op in ops[1:]:
        result = np.kron(result, op)
    return result


def site_op(local: np.ndarray, site: int) -> np.ndarray:
    identity = np.eye(2, dtype=complex)
    return kron_all([local if index == site else identity for index in range(5)])


def simultaneous_basis(hamiltonian: np.ndarray, spin2: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    energies, vectors = np.linalg.eigh(hamiltonian)
    start = 0
    while start < len(energies):
        stop = start + 1
        while stop < len(energies) and abs(energies[stop] - energies[start]) < 1e-10:
            stop += 1
        block = vectors[:, start:stop]
        _, rotation = np.linalg.eigh(block.conj().T @ spin2 @ block)
        vectors[:, start:stop] = block @ rotation
        start = stop
    spin2_values = np.real(np.diag(vectors.conj().T @ spin2 @ vectors))
    spins = 0.5 * (-1.0 + np.sqrt(1.0 + 4.0 * np.maximum(spin2_values, 0.0)))
    return energies, vectors, np.round(2.0 * spins) / 2.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=False)
    sx = np.array([[0, 1], [1, 0]], dtype=complex) / 2
    sy = np.array([[0, -1j], [1j, 0]], dtype=complex) / 2
    sz = np.array([[1, 0], [0, -1]], dtype=complex) / 2
    ops = {axis: [site_op(local, site) for site in range(5)] for axis, local in (("x", sx), ("y", sy), ("z", sz))}
    spin2 = sum(sum(ops[axis]) @ sum(ops[axis]) for axis in ("x", "y", "z"))
    qvals = np.linspace(0.0, 2.0 * np.pi, 101)
    rows: list[dict[str, float | int]] = []
    summaries = []

    fig, axes = plt.subplots(1, 3, figsize=(12.6, 3.8), sharey=True)
    for panel, alpha in enumerate(ALPHAS):
        hamiltonian = np.zeros((32, 32), dtype=complex)
        for left, right, coupling in ((0, 1, alpha), (1, 2, 1.0), (2, 3, 1.0), (3, 4, alpha)):
            for axis in ("x", "y", "z"):
                hamiltonian += coupling * ops[axis][left] @ ops[axis][right]
        energies, vectors, spins = simultaneous_basis(hamiltonian, spin2)
        ground = np.flatnonzero(np.abs(energies - energies[0]) < 1e-10)
        sector_weight = {0.5: 0.0, 1.5: 0.0, 2.5: 0.0}
        lowest_allowed = {0.5: np.inf, 1.5: np.inf, 2.5: np.inf}
        plot_q, plot_e, plot_w = [], [], []
        for q in qvals:
            operator = sum(np.exp(-1j * q * site) * ops["z"][site] for site in range(5)) / np.sqrt(5)
            amplitudes = vectors.conj().T @ operator @ vectors[:, ground]
            weights = np.mean(np.abs(amplitudes) ** 2, axis=1)
            for level, weight in enumerate(weights):
                excitation = energies[level] - energies[0]
                rows.append({
                    "alpha": alpha,
                    "q_over_pi": q / np.pi,
                    "level": level + 1,
                    "excitation": excitation,
                    "spin_S": spins[level],
                    "weight": weight,
                })
                if excitation > 1e-9:
                    sector_weight[float(spins[level])] += float(weight)
                    if weight > 1e-10:
                        lowest_allowed[float(spins[level])] = min(lowest_allowed[float(spins[level])], excitation)
                    if weight > 1e-5:
                        plot_q.append(q / np.pi)
                        plot_e.append(excitation)
                        plot_w.append(weight)
        summaries.append({
            "alpha": alpha,
            "ground_energy": float(energies[0]),
            "ground_spin": float(spins[0]),
            "ground_degeneracy": int(len(ground)),
            "hermiticity_norm": float(np.linalg.norm(hamiltonian - hamiltonian.conj().T)),
            "commutator_norm": float(np.linalg.norm(hamiltonian @ spin2 - spin2 @ hamiltonian)),
            "weight_S_half": sector_weight[0.5],
            "weight_S_three_half": sector_weight[1.5],
            "weight_S_five_half": sector_weight[2.5],
            "lowest_allowed_S_half": lowest_allowed[0.5],
            "lowest_allowed_S_three_half": lowest_allowed[1.5],
            "max_forbidden_fraction": sector_weight[2.5] / max(sum(sector_weight.values()), np.finfo(float).eps),
        })
        axes[panel].scatter(plot_q, plot_e, s=np.clip(np.asarray(plot_w) * 90, 2, 28), c=plot_e, cmap="viridis", alpha=0.75)
        axes[panel].set_title(rf"$\alpha={alpha:g}$")
        axes[panel].set_xlabel(r"$q/\pi$")
        axes[panel].set_xlim(0, 2)
        axes[panel].grid(alpha=0.2)
    axes[0].set_ylabel(r"$(E_n-E_0)/J_1$")
    fig.suptitle(r"Isolated pentamer: allowed $S^z(q)$ transitions")
    fig.tight_layout()
    fig.savefig(OUT / "positive_transition_weights.png", dpi=180)
    plt.close(fig)

    with (OUT / "transitions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (OUT / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summaries[0]))
        writer.writeheader()
        writer.writerows(summaries)
    acceptance = {
        "all_hermitian": all(item["hermiticity_norm"] <= 1e-12 for item in summaries),
        "all_su2_commutators": all(item["commutator_norm"] <= 1e-12 for item in summaries),
        "all_ground_doublets": all(item["ground_spin"] == 0.5 and item["ground_degeneracy"] == 2 for item in summaries),
        "s_half_to_five_half_forbidden": all(item["max_forbidden_fraction"] <= 1e-12 for item in summaries),
        "interpretation": "Sz(q) 是秩一自旋算符；S=1/2 基态可到 S=1/2、3/2，不能直接到 S=5/2",
    }
    (OUT / "acceptance.json").write_text(json.dumps(acceptance, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in sorted(OUT.iterdir()) if path.name != "checksums.sha256"),
        encoding="utf-8",
    )
    print(json.dumps(acceptance, ensure_ascii=False))


if __name__ == "__main__":
    main()
