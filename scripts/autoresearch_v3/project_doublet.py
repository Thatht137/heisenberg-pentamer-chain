#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""投影单五聚体基态双重态并计算有效耦合与动量形状因子。"""

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
OUT = ROOT / "results" / "autoresearch_v3_20260729" / "round1_doublet_projection"
REPRESENTATIVE = (0.14, 0.23, 0.33)


def kron_all(operators: list[np.ndarray]) -> np.ndarray:
    result = operators[0]
    for operator in operators[1:]:
        result = np.kron(result, operator)
    return result


def site_operator(local: np.ndarray, site: int) -> np.ndarray:
    identity = np.eye(2, dtype=complex)
    return kron_all([local if index == site else identity for index in range(5)])


def doublet_projection(alpha: float, spins: dict[str, list[np.ndarray]]) -> dict[str, object]:
    hamiltonian = np.zeros((32, 32), dtype=complex)
    for left, right, coupling in ((0, 1, alpha), (1, 2, 1.0), (2, 3, 1.0), (3, 4, alpha)):
        for axis in ("x", "y", "z"):
            hamiltonian += coupling * spins[axis][left] @ spins[axis][right]
    energies, vectors = np.linalg.eigh(hamiltonian)
    ground_indices = np.flatnonzero(np.abs(energies - energies[0]) <= 1e-10)
    ground = vectors[:, ground_indices]
    total_sz = sum(spins["z"])
    sz_values, rotation = np.linalg.eigh(ground.conj().T @ total_sz @ ground)
    plus = ground @ rotation[:, np.argmax(sz_values)]
    coefficients = np.array([
        2.0 * np.real(plus.conj() @ spins["z"][site] @ plus)
        for site in range(5)
    ])
    local_gap = energies[len(ground_indices)] - energies[0]
    folded_q = (2 * np.arange(5) + 1) * np.pi / 5
    folded_weight = np.array([
        abs(sum(coefficients[site] * np.exp(-1j * q * site) for site in range(5))) ** 2
        for q in folded_q
    ])
    return {
        "alpha": alpha,
        "ground_energy": float(energies[0]),
        "local_gap": float(local_gap),
        "coefficients": coefficients,
        "coefficient_sum": float(np.sum(coefficients)),
        "reflection_error": float(np.max(np.abs(coefficients - coefficients[::-1]))),
        "jeff_over_beta": float(coefficients[0] * coefficients[-1]),
        "folded_q": folded_q,
        "folded_weight": folded_weight,
        "dominant_q_over_pi": float(folded_q[np.argmax(folded_weight)] / np.pi),
        "dominant_weight_fraction": float(np.max(folded_weight) / np.sum(folded_weight)),
        "hermiticity_norm": float(np.linalg.norm(hamiltonian - hamiltonian.conj().T)),
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=False)
    sx = np.array([[0, 1], [1, 0]], dtype=complex) / 2
    sy = np.array([[0, -1j], [1j, 0]], dtype=complex) / 2
    sz = np.array([[1, 0], [0, -1]], dtype=complex) / 2
    spins = {
        axis: [site_operator(local, site) for site in range(5)]
        for axis, local in (("x", sx), ("y", sy), ("z", sz))
    }
    scan = [doublet_projection(float(alpha), spins) for alpha in np.linspace(0.01, 1.0, 100)]
    representative = [doublet_projection(alpha, spins) for alpha in REPRESENTATIVE]

    with (OUT / "projection_scan.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["alpha", "ground_energy", "local_gap", "c1", "c2", "c3", "c4", "c5", "coefficient_sum", "reflection_error", "jeff_over_beta", "dominant_q_over_pi", "dominant_weight_fraction"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in scan:
            writer.writerow({
                "alpha": item["alpha"],
                "ground_energy": item["ground_energy"],
                "local_gap": item["local_gap"],
                **{f"c{site + 1}": item["coefficients"][site] for site in range(5)},
                "coefficient_sum": item["coefficient_sum"],
                "reflection_error": item["reflection_error"],
                "jeff_over_beta": item["jeff_over_beta"],
                "dominant_q_over_pi": item["dominant_q_over_pi"],
                "dominant_weight_fraction": item["dominant_weight_fraction"],
            })
    with (OUT / "representative.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["alpha", "ground_energy", "local_gap", "c1", "c2", "c3", "c4", "c5", "coefficient_sum", "jeff_over_beta", "dominant_q_over_pi", "dominant_weight_fraction"] + [f"weight_q{index}" for index in range(5)]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in representative:
            writer.writerow({
                "alpha": item["alpha"],
                "ground_energy": item["ground_energy"],
                "local_gap": item["local_gap"],
                **{f"c{site + 1}": item["coefficients"][site] for site in range(5)},
                "coefficient_sum": item["coefficient_sum"],
                "jeff_over_beta": item["jeff_over_beta"],
                "dominant_q_over_pi": item["dominant_q_over_pi"],
                "dominant_weight_fraction": item["dominant_weight_fraction"],
                **{f"weight_q{index}": item["folded_weight"][index] for index in range(5)},
            })

    alphas = np.array([item["alpha"] for item in scan])
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 3.8))
    for site in range(5):
        axes[0].plot(alphas, [item["coefficients"][site] for item in scan], label=rf"$c_{site + 1}$")
    axes[0].set_ylabel(r"$P S_i^z P / T^z$")
    axes[0].legend(frameon=False, ncol=2, fontsize=8)
    axes[1].plot(alphas, [item["jeff_over_beta"] for item in scan], color="#b24c35")
    axes[1].set_ylabel(r"$J_{eff}/\beta=c_1c_5$")
    axes[2].plot(alphas, [item["dominant_weight_fraction"] for item in scan], color="#2b6f6d")
    axes[2].set_ylabel(r"Dominant folded-weight fraction")
    for axis in axes:
        axis.set_xlabel(r"$\alpha$")
        axis.grid(alpha=0.2)
    fig.suptitle("Isolated-pentamer doublet projection")
    fig.tight_layout()
    fig.savefig(OUT / "doublet_projection.png", dpi=180)
    plt.close(fig)

    fig, axis = plt.subplots(figsize=(7.2, 4.0))
    x = np.arange(5)
    width = 0.24
    labels = [r"$\pi/5$", r"$3\pi/5$", r"$\pi$", r"$7\pi/5$", r"$9\pi/5$"]
    for index, item in enumerate(representative):
        weights = item["folded_weight"] / np.sum(item["folded_weight"])
        axis.bar(x + (index - 1) * width, weights, width, label=rf"$\alpha={item['alpha']:g}$")
    axis.set_xticks(x, labels)
    axis.set_ylabel("Projected spectral-weight fraction")
    axis.set_xlabel("Physical momentum with effective K=pi")
    axis.legend(frameon=False)
    axis.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(OUT / "folded_form_factor.png", dpi=180)
    plt.close(fig)

    acceptance = {
        "all_hermitian": all(item["hermiticity_norm"] <= 1e-12 for item in representative),
        "doublet_sum_rule": all(abs(item["coefficient_sum"] - 1.0) <= 1e-12 for item in representative),
        "reflection_symmetry": all(item["reflection_error"] <= 1e-12 for item in representative),
        "antiferromagnetic_jeff": all(item["jeff_over_beta"] > 0 for item in representative),
        "q_pi_dominant": all(abs(item["dominant_q_over_pi"] - 1.0) <= 1e-12 for item in representative),
        "claim": "正 alpha 五聚体双重态的一阶胞间投影是反铁磁有效 S=1/2 Heisenberg 链，且物理 q=pi 形状因子最强",
    }
    (OUT / "acceptance.json").write_text(json.dumps(acceptance, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in sorted(OUT.iterdir()) if path.name != "checksums.sha256"),
        encoding="utf-8",
    )
    print(json.dumps(acceptance, ensure_ascii=False))


if __name__ == "__main__":
    main()
