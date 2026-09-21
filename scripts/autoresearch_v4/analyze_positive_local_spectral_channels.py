#!/usr/bin/env python3
"""扫描正 alpha 五聚体的局域多重态与单自旋谱权。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "results" / "autoresearch_v4_20260730" / "round2_local_spectral_channels_v4"
REPRESENTATIVE_ALPHAS = (0.14, 0.23, 0.33, 1.0)
FOLDED_Q_OVER_PI = (0.2, 0.6, 1.0, 1.4, 1.8)
DFT_Q_OVER_PI = (0.0, 0.4, 0.8, 1.2, 1.6)
ALPHA_GRID = np.round(np.linspace(0.01, 1.0, 100), 12)


@dataclass(frozen=True)
class Multiplet:
    energy: float
    spin: float
    parity: int
    vectors: np.ndarray

    @property
    def degeneracy(self) -> int:
        return self.vectors.shape[1]


def kron_all(operators: list[np.ndarray]) -> np.ndarray:
    result = operators[0]
    for operator in operators[1:]:
        result = np.kron(result, operator)
    return result


def site_operator(local: np.ndarray, site: int) -> np.ndarray:
    identity = np.eye(2, dtype=complex)
    return kron_all([local if index == site else identity for index in range(5)])


def reflection_operator() -> np.ndarray:
    reflection = np.zeros((32, 32), dtype=complex)
    for state in range(32):
        bits = f"{state:05b}"
        reflected = int(bits[::-1], 2)
        reflection[reflected, state] = 1.0
    return reflection


def group_indices(values: np.ndarray, tolerance: float) -> list[np.ndarray]:
    order = np.argsort(values)
    groups: list[list[int]] = []
    for index in order:
        if not groups or abs(values[index] - values[groups[-1][0]]) > tolerance:
            groups.append([int(index)])
        else:
            groups[-1].append(int(index))
    return [np.asarray(group, dtype=int) for group in groups]


def build_operators() -> tuple[dict[str, list[np.ndarray]], np.ndarray, np.ndarray]:
    sx = np.array([[0, 1], [1, 0]], dtype=complex) / 2
    sy = np.array([[0, -1j], [1j, 0]], dtype=complex) / 2
    sz = np.array([[1, 0], [0, -1]], dtype=complex) / 2
    operators = {
        axis: [site_operator(local, site) for site in range(5)]
        for axis, local in (("x", sx), ("y", sy), ("z", sz))
    }
    spin2 = sum(sum(operators[axis]) @ sum(operators[axis]) for axis in ("x", "y", "z"))
    return operators, spin2, reflection_operator()


def hamiltonian(alpha: float, operators: dict[str, list[np.ndarray]]) -> np.ndarray:
    matrix = np.zeros((32, 32), dtype=complex)
    bonds = ((0, 1, alpha), (1, 2, 1.0), (2, 3, 1.0), (3, 4, alpha))
    for left, right, coupling in bonds:
        for axis in ("x", "y", "z"):
            matrix += coupling * operators[axis][left] @ operators[axis][right]
    return matrix


def resolve_multiplets(
    matrix: np.ndarray,
    spin2: np.ndarray,
    reflection: np.ndarray,
) -> list[Multiplet]:
    energies, vectors = np.linalg.eigh(matrix)
    multiplets: list[Multiplet] = []
    for energy_group in group_indices(energies, 1e-9):
        energy_basis = vectors[:, energy_group]
        spin2_block = energy_basis.conj().T @ spin2 @ energy_basis
        spin2_values, spin_rotation = np.linalg.eigh(spin2_block)
        spin_basis = energy_basis @ spin_rotation
        spins = 0.5 * (-1.0 + np.sqrt(1.0 + 4.0 * np.maximum(spin2_values, 0.0)))
        rounded_spins = np.round(2.0 * spins) / 2.0
        for spin_group in group_indices(rounded_spins, 1e-7):
            current_spin = float(rounded_spins[spin_group[0]])
            current_basis = spin_basis[:, spin_group]
            parity_block = current_basis.conj().T @ reflection @ current_basis
            parity_values, parity_rotation = np.linalg.eigh(parity_block)
            parity_basis = current_basis @ parity_rotation
            rounded_parities = np.where(parity_values >= 0.0, 1, -1)
            for parity_group in group_indices(rounded_parities.astype(float), 0.5):
                parity = int(rounded_parities[parity_group[0]])
                multiplets.append(Multiplet(
                    energy=float(np.mean(energies[energy_group])),
                    spin=current_spin,
                    parity=parity,
                    vectors=parity_basis[:, parity_group],
                ))
    return sorted(multiplets, key=lambda item: item.energy)


def spectral_operator(q: float, sz_operators: list[np.ndarray]) -> np.ndarray:
    return sum(
        np.exp(-1j * q * site) * operator
        for site, operator in enumerate(sz_operators)
    ) / np.sqrt(5.0)


def projector_weight(source: Multiplet, target: Multiplet, operator: np.ndarray) -> float:
    amplitudes = target.vectors.conj().T @ operator @ source.vectors
    return float(np.linalg.norm(amplitudes, ord="fro") ** 2 / source.degeneracy)


def branch_labels(multiplets: list[Multiplet]) -> list[str]:
    counts: dict[tuple[float, int], int] = {}
    labels = []
    for multiplet in multiplets:
        key = (multiplet.spin, multiplet.parity)
        counts[key] = counts.get(key, 0) + 1
        parity = "+" if multiplet.parity > 0 else "-"
        labels.append(f"S{multiplet.spin:.1f}_r{parity}_{counts[key]}")
    return labels


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_output(*arguments: str) -> str:
    result = subprocess.run(
        ("git", *arguments),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def analyze(output: Path) -> dict[str, object]:
    output.mkdir(parents=True, exist_ok=False)
    operators, spin2, reflection = build_operators()
    sz_operators = operators["z"]
    all_alphas = sorted(set(ALPHA_GRID.tolist()) | set(REPRESENTATIVE_ALPHAS))

    multiplet_rows: list[dict[str, object]] = []
    folded_rows: list[dict[str, object]] = []
    representative_rows: list[dict[str, object]] = []
    plot_records: dict[float, dict[str, object]] = {}
    validation_errors = {
        "hermiticity": 0.0,
        "su2_commutator": 0.0,
        "reflection_commutator": 0.0,
        "orthonormality": 0.0,
        "multiplet_degeneracy": 0.0,
        "dft_sum_rule": 0.0,
        "q0_inelastic": 0.0,
        "qpi_wrong_parity": 0.0,
        "s_five_half_fraction": 0.0,
    }

    for alpha in all_alphas:
        matrix = hamiltonian(alpha, operators)
        multiplets = resolve_multiplets(matrix, spin2, reflection)
        labels = branch_labels(multiplets)
        ground = multiplets[0]
        ground_energy = ground.energy
        weights_by_q: dict[float, list[float]] = {}

        validation_errors["hermiticity"] = max(
            validation_errors["hermiticity"],
            float(np.linalg.norm(matrix - matrix.conj().T)),
        )
        validation_errors["su2_commutator"] = max(
            validation_errors["su2_commutator"],
            float(np.linalg.norm(matrix @ spin2 - spin2 @ matrix)),
        )
        validation_errors["reflection_commutator"] = max(
            validation_errors["reflection_commutator"],
            float(np.linalg.norm(matrix @ reflection - reflection @ matrix)),
        )
        full_basis = np.column_stack([item.vectors for item in multiplets])
        validation_errors["orthonormality"] = max(
            validation_errors["orthonormality"],
            float(np.linalg.norm(full_basis.conj().T @ full_basis - np.eye(32))),
        )
        validation_errors["multiplet_degeneracy"] = max(
            validation_errors["multiplet_degeneracy"],
            max(abs(item.degeneracy - int(round(2 * item.spin + 1))) for item in multiplets),
        )

        for q_over_pi in sorted(set(FOLDED_Q_OVER_PI) | set(DFT_Q_OVER_PI)):
            operator = spectral_operator(q_over_pi * np.pi, sz_operators)
            weights_by_q[q_over_pi] = [
                projector_weight(ground, target, operator)
                for target in multiplets
            ]

        dft_total = sum(sum(weights_by_q[q]) for q in DFT_Q_OVER_PI)
        validation_errors["dft_sum_rule"] = max(
            validation_errors["dft_sum_rule"], abs(dft_total - 1.25)
        )
        q0_inelastic = sum(
            weight
            for target, weight in zip(multiplets, weights_by_q[0.0])
            if target.energy - ground_energy > 1e-9
        )
        validation_errors["q0_inelastic"] = max(
            validation_errors["q0_inelastic"], q0_inelastic
        )
        qpi_total = sum(weights_by_q[1.0])
        qpi_wrong_parity = sum(
            weight
            for target, weight in zip(multiplets, weights_by_q[1.0])
            if target.parity != ground.parity
        )
        validation_errors["qpi_wrong_parity"] = max(
            validation_errors["qpi_wrong_parity"], qpi_wrong_parity
        )
        five_half_weight = sum(
            sum(
                weight
                for target, weight in zip(multiplets, weights_by_q[q])
                if target.spin == 2.5
            )
            for q in FOLDED_Q_OVER_PI
        )
        folded_total = sum(sum(weights_by_q[q]) for q in FOLDED_Q_OVER_PI)
        validation_errors["s_five_half_fraction"] = max(
            validation_errors["s_five_half_fraction"],
            five_half_weight / max(folded_total, np.finfo(float).eps),
        )

        sector_energies: dict[float, list[float]] = {0.5: [], 1.5: [], 2.5: []}
        sector_qpi_weights: dict[float, float] = {0.5: 0.0, 1.5: 0.0, 2.5: 0.0}
        for target_index, (label, target, qpi_weight) in enumerate(
            zip(labels, multiplets, weights_by_q[1.0])
        ):
            excitation = target.energy - ground_energy
            sector_energies[target.spin].append(excitation)
            if excitation > 1e-9:
                sector_qpi_weights[target.spin] += qpi_weight
            multiplet_rows.append({
                "alpha": alpha,
                "branch": label,
                "spin_S": target.spin,
                "parity": target.parity,
                "degeneracy": target.degeneracy,
                "energy": target.energy,
                "excitation": excitation,
                "qpi_weight": qpi_weight,
            })
            for q_over_pi in FOLDED_Q_OVER_PI:
                weight = weights_by_q[q_over_pi][target_index]
                folded_rows.append({
                    "alpha": alpha,
                    "q_over_pi": q_over_pi,
                    "branch": label,
                    "spin_S": target.spin,
                    "parity": target.parity,
                    "excitation": excitation,
                    "weight": weight,
                })

        positive_doublet = [value for value in sector_energies[0.5] if value > 1e-9]
        positive_quartet = [value for value in sector_energies[1.5] if value > 1e-9]
        positive_sextet = [value for value in sector_energies[2.5] if value > 1e-9]
        if alpha in REPRESENTATIVE_ALPHAS:
            representative_rows.append({
                "alpha": alpha,
                "ground_energy": ground_energy,
                "ground_spin": ground.spin,
                "ground_parity": ground.parity,
                "lowest_excited_doublet": min(positive_doublet),
                "lowest_quartet": min(positive_quartet),
                "sextet_gap": min(positive_sextet),
                "quartet_to_doublet_gap_ratio": min(positive_quartet) / min(positive_doublet),
                "qpi_inelastic_S_half": sector_qpi_weights[0.5],
                "qpi_inelastic_S_three_half": sector_qpi_weights[1.5],
                "qpi_S_five_half": sector_qpi_weights[2.5],
                "qpi_total_weight": qpi_total,
            })
            q_dense = np.linspace(0.0, 2.0, 401)
            dense_weights = []
            for q_over_pi in q_dense:
                operator = spectral_operator(q_over_pi * np.pi, sz_operators)
                dense_weights.append([
                    projector_weight(ground, target, operator)
                    for target in multiplets
                ])
            plot_records[alpha] = {
                "multiplets": multiplets,
                "labels": labels,
                "q": q_dense,
                "weights": np.asarray(dense_weights),
            }

    alpha_one_energies = sorted(
        row["energy"] for row in multiplet_rows if row["alpha"] == 1.0
    )
    alpha_one_anchor = sorted((
        -1.9278862533,
        -1.2071067811865475,
        -0.8090169943749475,
        -0.660818587,
        -0.30901699437494745,
        0.20710678118654757,
        0.30901699437494745,
        0.5887048404,
        0.8090169943749475,
        1.0,
    ))
    alpha_one_error = float(np.max(np.abs(np.asarray(alpha_one_energies) - alpha_one_anchor)))

    legacy_rows = list(csv.DictReader(
        (ROOT / "results" / "autoresearch_v2_20260729" / "round3_local_transitions" / "summary.csv").open(
            encoding="utf-8"
        )
    ))
    legacy_errors = []
    for legacy in legacy_rows:
        current = next(row for row in representative_rows if row["alpha"] == float(legacy["alpha"]))
        legacy_errors.extend((
            abs(current["ground_energy"] - float(legacy["ground_energy"])),
            abs(current["lowest_excited_doublet"] - float(legacy["lowest_allowed_S_half"])),
            abs(current["lowest_quartet"] - float(legacy["lowest_allowed_S_three_half"])),
        ))
    legacy_error = float(max(legacy_errors))

    alpha_claim_rows = []
    for alpha in all_alphas:
        current = [row for row in multiplet_rows if row["alpha"] == alpha]
        inelastic = [row for row in current if row["excitation"] > 1e-9]
        qpi_inelastic = sum(float(row["qpi_weight"]) for row in inelastic)
        quartet_weight = sum(
            float(row["qpi_weight"]) for row in inelastic if row["spin_S"] == 1.5
        )
        lowest_doublet = min(
            (row for row in inelastic if row["spin_S"] == 0.5),
            key=lambda row: float(row["excitation"]),
        )
        lowest_quartet = min(
            (row for row in inelastic if row["spin_S"] == 1.5),
            key=lambda row: float(row["excitation"]),
        )
        alpha_claim_rows.append({
            "alpha": alpha,
            "ground_spin": current[0]["spin_S"],
            "ground_parity": current[0]["parity"],
            "lowest_doublet_parity": lowest_doublet["parity"],
            "lowest_doublet_qpi": float(lowest_doublet["qpi_weight"]),
            "lowest_quartet_parity": lowest_quartet["parity"],
            "lowest_quartet_fraction": float(lowest_quartet["qpi_weight"]) / qpi_inelastic,
            "quartet_fraction": quartet_weight / qpi_inelastic,
        })
    claim = {
        "verdict": "momentum_filtered_local_multiplets",
        "scope": "isolated pentamer, 0.01 <= alpha <= 1.00, single-spin Sz(q)",
        "claim": "最低激发双重态在 q=pi 因反射宇称严格变暗，q=pi 局域非弹性权重由四重态主导",
        "all_ground_doublet_even": all(
            row["ground_spin"] == 0.5 and row["ground_parity"] == 1
            for row in alpha_claim_rows
        ),
        "all_lowest_excited_doublet_odd": all(
            row["lowest_doublet_parity"] == -1 for row in alpha_claim_rows
        ),
        "all_lowest_quartet_even": all(
            row["lowest_quartet_parity"] == 1 for row in alpha_claim_rows
        ),
        "max_lowest_doublet_qpi_weight": max(
            row["lowest_doublet_qpi"] for row in alpha_claim_rows
        ),
        "quartet_fraction_of_qpi_inelastic_range": [
            min(row["quartet_fraction"] for row in alpha_claim_rows),
            max(row["quartet_fraction"] for row in alpha_claim_rows),
        ],
        "lowest_quartet_fraction_of_qpi_inelastic_range": [
            min(row["lowest_quartet_fraction"] for row in alpha_claim_rows),
            max(row["lowest_quartet_fraction"] for row in alpha_claim_rows),
        ],
        "max_sextet_fraction": validation_errors["s_five_half_fraction"],
        "interpretation": "q=pi 首个局域可见分支是 S=3/2 四重态；最低 S=1/2 双重态只在离开 q=pi 后可见；S=5/2 对单自旋探针为暗态",
        "boundary": "孤立单胞选择定则不等价于有限 beta 链上色散；正式分支归属仍需生产级 DSF 验证",
    }

    write_csv(output / "multiplet_scan.csv", multiplet_rows)
    write_csv(output / "folded_transition_weights.csv", folded_rows)
    write_csv(output / "representative_summary.csv", representative_rows)
    plot_results(output, multiplet_rows, representative_rows, plot_records)
    (output / "claim_summary.json").write_text(
        json.dumps(claim, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    validation = {
        "scope": "alpha in [0.01, 1.00], isolated five-site OBC pentamer, single-spin Sz(q)",
        "alpha_points": len(all_alphas),
        "hilbert_dimension": 32,
        "multiplet_inventory": "5 doublets + 4 quartets + 1 sextet",
        "max_errors": validation_errors,
        "alpha_one_exact_anchor_error": alpha_one_error,
        "legacy_three_point_crosscheck_error": legacy_error,
        "gates": {
            "hermiticity": validation_errors["hermiticity"] <= 1e-12,
            "su2": validation_errors["su2_commutator"] <= 1e-12,
            "reflection": validation_errors["reflection_commutator"] <= 1e-12,
            "orthonormality": validation_errors["orthonormality"] <= 1e-10,
            "multiplet_counting": validation_errors["multiplet_degeneracy"] == 0.0,
            "dft_sum_rule": validation_errors["dft_sum_rule"] <= 1e-12,
            "q0_conservation": validation_errors["q0_inelastic"] <= 1e-12,
            "qpi_parity_rule": validation_errors["qpi_wrong_parity"] <= 1e-12,
            "rank_one_dark_sextet": validation_errors["s_five_half_fraction"] <= 1e-12,
            "alpha_one_anchor": alpha_one_error <= 1e-9,
            "legacy_crosscheck": legacy_error <= 1e-12,
        },
    }
    validation["all_gates_pass"] = all(validation["gates"].values())
    (output / "validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    completed_at = datetime.now(timezone.utc).isoformat()
    source_path = Path(__file__).resolve()
    run_manifest = {
        "run_id": output.name,
        "status": "completed",
        "completed_at_utc": completed_at,
        "host": platform.node(),
        "operator": "Codex",
        "git_commit": git_output("rev-parse", "HEAD"),
        "git_status_short": git_output("status", "--short"),
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "matplotlib_version": matplotlib.__version__,
        "source": str(source_path.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256(source_path),
        "command": "python -X utf8 scripts/autoresearch_v4/analyze_positive_local_spectral_channels.py",
        "model": "isolated five-site spin-1/2 Heisenberg pentamer",
        "parameters": {
            "J1": 1.0,
            "alpha_min": 0.01,
            "alpha_max": 1.0,
            "alpha_points": len(all_alphas),
            "boundary": "OBC",
            "hilbert_dimension": 32,
            "observable": "projector-resolved Sz(q) spectral weight",
        },
        "deterministic": True,
    }
    (output / "run.json").write_text(
        json.dumps(run_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "status.json").write_text(
        json.dumps({"status": "completed", "completed_at_utc": completed_at}, indent=2),
        encoding="utf-8",
    )
    (output / "stdout.log").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output / "stderr.log").write_text("", encoding="utf-8")
    files = sorted(path for path in output.iterdir() if path.name != "checksums.sha256")
    (output / "checksums.sha256").write_text(
        "".join(f"{sha256(path)}  {path.name}\n" for path in files), encoding="utf-8"
    )
    return validation


def plot_results(
    output: Path,
    multiplet_rows: list[dict[str, object]],
    representative_rows: list[dict[str, object]],
    plot_records: dict[float, dict[str, object]],
) -> None:
    plt.rcParams.update({
        "font.family": "Arial",
        "font.size": 8,
        "axes.labelsize": 9,
        "legend.fontsize": 7,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    })
    colors = {0.5: "#0072B2", 1.5: "#D55E00", 2.5: "#5B5B5B"}
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.7), layout="constrained")

    branch_names = sorted(set(row["branch"] for row in multiplet_rows))
    for branch in branch_names:
        rows = [row for row in multiplet_rows if row["branch"] == branch]
        spin = float(rows[0]["spin_S"])
        parity = int(rows[0]["parity"])
        axes[0, 0].plot(
            [row["alpha"] for row in rows],
            [row["excitation"] for row in rows],
            color=colors[spin],
            linestyle="-" if parity > 0 else "--",
            linewidth=1.0,
            alpha=0.9,
        )
    axes[0, 0].set(xlabel=r"$\alpha$", ylabel=r"$(E_n-E_0)/J_1$", title="(a) Multiplet spectrum")

    for spin in (0.5, 1.5, 2.5):
        rows = [
            row for row in multiplet_rows
            if row["spin_S"] == spin
            and row["excitation"] > 1e-9
            and row["qpi_weight"] > 1e-10
        ]
        if not rows:
            continue
        axes[0, 1].scatter(
            [row["alpha"] for row in rows],
            [row["excitation"] for row in rows],
            s=np.clip(np.asarray([row["qpi_weight"] for row in rows]) * 420.0, 1.0, 32.0),
            color=colors[spin],
            alpha=0.65,
            label=rf"$S={spin:g}$",
        )
    axes[0, 1].set(xlabel=r"$\alpha$", ylabel=r"$(E_n-E_0)/J_1$", title=r"(b) $q=\pi$ spectral weight")
    axes[0, 1].legend(frameon=False)
    axes[0, 1].text(0.98, 0.97, r"$S=5/2$: dark", transform=axes[0, 1].transAxes, ha="right", va="top")

    record = plot_records[0.23]
    multiplets = record["multiplets"]
    labels = record["labels"]
    weights = record["weights"]
    ground_energy = multiplets[0].energy
    candidates = [
        index for index, item in enumerate(multiplets)
        if item.energy - ground_energy > 1e-9 and item.spin in (0.5, 1.5)
    ]
    candidates = sorted(candidates, key=lambda index: multiplets[index].energy)[:3]
    for index in candidates:
        item = multiplets[index]
        axes[1, 0].plot(
            record["q"],
            weights[:, index],
            linewidth=1.4,
            label=rf"{labels[index]}, $\Delta={item.energy-ground_energy:.3f}$",
        )
    axes[1, 0].set(
        xlabel=r"$q/\pi$",
        ylabel="projector weight",
        title=r"(c) Form factors at $\alpha=0.23$",
    )
    axes[1, 0].legend(frameon=False)

    alphas = [row["alpha"] for row in representative_rows]
    axes[1, 1].plot(
        alphas,
        [row["lowest_excited_doublet"] for row in representative_rows],
        "o-",
        color=colors[0.5],
        label=r"lowest excited $S=1/2$",
    )
    axes[1, 1].plot(
        alphas,
        [row["lowest_quartet"] for row in representative_rows],
        "s-",
        color=colors[1.5],
        label=r"lowest $S=3/2$",
    )
    axes[1, 1].plot(
        alphas,
        [row["sextet_gap"] for row in representative_rows],
        "^-",
        color=colors[2.5],
        label=r"dark $S=5/2$",
    )
    axes[1, 1].set(
        xlabel=r"$\alpha$",
        ylabel=r"local gap$/J_1$",
        title="(d) Representative local gaps",
    )
    axes[1, 1].legend(frameon=False)
    for axis in axes.flat:
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.tick_params(direction="out", length=3)
    fig.savefig(output / "local_spectral_channels.png", dpi=300)
    fig.savefig(output / "local_spectral_channels.pdf")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    validation = analyze(args.output.resolve())
    print(json.dumps(validation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
