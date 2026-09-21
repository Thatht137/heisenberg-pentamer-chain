#!/usr/bin/env python3
"""构造两胞与三胞二阶 Schrieffer-Wolff 有效 Hamiltonian。"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PROJECTION = ROOT / "results" / "autoresearch_v3_20260729" / "round1_doublet_projection" / "projection_scan.csv"
FINITE_BETA = ROOT / "results" / "autoresearch_v5_20260731" / "round13_second_order_scan" / "second_order_summary.csv"
OUTDIR = ROOT / "results" / "autoresearch_v5_20260731" / "round14_schrieffer_wolff"
sys.path.insert(0, str(ROOT / "scripts" / "autoresearch_v4"))
from analyze_positive_local_spectral_channels import build_operators, hamiltonian  # noqa: E402


mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 7,
        "axes.linewidth": 0.8,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    }
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def spin_matrices() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    sx = np.array([[0, 1], [1, 0]], dtype=complex) / 2
    sy = np.array([[0, -1j], [1j, 0]], dtype=complex) / 2
    sz = np.array([[1, 0], [0, -1]], dtype=complex) / 2
    return sx, sy, sz, np.eye(2, dtype=complex)


def heisenberg_operators() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sx, sy, sz, identity = spin_matrices()
    spins = (sx, sy, sz)
    t12 = sum(np.kron(spin, spin) for spin in spins)
    op3 = lambda a, b, c: np.kron(np.kron(a, b), c)
    t12_3 = sum(op3(spin, spin, identity) for spin in spins)
    t23_3 = sum(op3(identity, spin, spin) for spin in spins)
    t13_3 = sum(op3(spin, identity, spin) for spin in spins)
    return t12, t12_3 + t23_3, t13_3


def fit_operators(matrix: np.ndarray, operators: list[np.ndarray]) -> tuple[np.ndarray, float]:
    design = np.stack([operator.reshape(-1) for operator in operators], axis=1)
    coefficients = np.linalg.lstsq(design, matrix.reshape(-1), rcond=None)[0]
    fitted = (design @ coefficients).reshape(matrix.shape)
    relative = np.linalg.norm(matrix - fitted) / max(np.linalg.norm(matrix), np.finfo(float).eps)
    return coefficients.real, float(relative)


def endpoint_matrices(alpha: float, operators: dict[str, list[np.ndarray]]) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, np.ndarray]]:
    energies, vectors = np.linalg.eigh(hamiltonian(alpha, operators))
    left = {axis: vectors.conj().T @ operators[axis][4] @ vectors for axis in "xyz"}
    right = {axis: vectors.conj().T @ operators[axis][0] @ vectors for axis in "xyz"}
    return energies, left, right


def sw_two(energies: np.ndarray, left: dict[str, np.ndarray], right: dict[str, np.ndarray], t12: np.ndarray) -> dict[str, float]:
    low = (0, 1)
    tuples = [(i, j) for i in low for j in low]
    action = np.zeros((32**2, 4), dtype=complex)
    for column, (i, j) in enumerate(tuples):
        action[:, column] = sum(np.outer(left[axis][:, i], right[axis][:, j]) for axis in "xyz").reshape(-1)
    low_indices = [(i * 32) + j for i, j in tuples]
    first = action[low_indices, :]
    denominators = (2 * energies[0] - (energies[:, None] + energies[None, :])).reshape(-1)
    mask = np.ones(32**2, dtype=bool)
    mask[low_indices] = False
    second = action[mask].conj().T @ ((1.0 / denominators[mask])[:, None] * action[mask])
    first_coefficients, first_fit = fit_operators(first, [np.eye(4), t12])
    second_coefficients, second_fit = fit_operators(second, [np.eye(4), t12])
    return {
        "first_constant": first_coefficients[0],
        "first_J1": first_coefficients[1],
        "second_constant_per_bond": second_coefficients[0],
        "second_J1_per_bond": second_coefficients[1],
        "second_singlet_C2": second_coefficients[0] - 0.75 * second_coefficients[1],
        "second_triplet_C2": second_coefficients[0] + 0.25 * second_coefficients[1],
        "first_fit_relative_residual": first_fit,
        "second_fit_relative_residual": second_fit,
        "second_hermiticity_error": float(np.linalg.norm(second - second.conj().T)),
    }


def sw_three(energies: np.ndarray, left: dict[str, np.ndarray], right: dict[str, np.ndarray], tnn: np.ndarray, t13: np.ndarray) -> dict[str, float]:
    low = (0, 1)
    tuples = [(i, j, k) for i in low for j in low for k in low]
    basis = np.eye(32, dtype=complex)
    action = np.zeros((32**3, 8), dtype=complex)
    for column, (i, j, k) in enumerate(tuples):
        tensor = np.zeros((32, 32, 32), dtype=complex)
        for axis in "xyz":
            tensor += np.einsum("p,q,r->pqr", left[axis][:, i], right[axis][:, j], basis[:, k])
            tensor += np.einsum("p,q,r->pqr", basis[:, i], left[axis][:, j], right[axis][:, k])
        action[:, column] = tensor.reshape(-1)
    low_indices = [(i * 32 + j) * 32 + k for i, j, k in tuples]
    first = action[low_indices, :]
    denominators = (
        3 * energies[0]
        - (energies[:, None, None] + energies[None, :, None] + energies[None, None, :])
    ).reshape(-1)
    mask = np.ones(32**3, dtype=bool)
    mask[low_indices] = False
    second = action[mask].conj().T @ ((1.0 / denominators[mask])[:, None] * action[mask])
    first_coefficients, first_fit = fit_operators(first, [np.eye(8), tnn, t13])
    second_coefficients, second_fit = fit_operators(second, [np.eye(8), tnn, t13])
    return {
        "first_constant_three": first_coefficients[0],
        "first_J1_three": first_coefficients[1],
        "first_J2_three": first_coefficients[2],
        "second_constant_three": second_coefficients[0],
        "second_J1_three": second_coefficients[1],
        "second_J2_induced": second_coefficients[2],
        "first_three_fit_relative_residual": first_fit,
        "second_three_fit_relative_residual": second_fit,
        "second_three_hermiticity_error": float(np.linalg.norm(second - second.conj().T)),
    }


def calculate() -> list[dict[str, object]]:
    projection = [{key: float(value) for key, value in row.items()} for row in read_csv(PROJECTION)]
    finite = {round(float(row["alpha"]), 12): row for row in read_csv(FINITE_BETA)}
    operators, _, _ = build_operators()
    t12, tnn, t13 = heisenberg_operators()
    rows = []
    for index, local in enumerate(projection, start=1):
        alpha = local["alpha"]
        energies, left, right = endpoint_matrices(alpha, operators)
        two = sw_two(energies, left, right, t12)
        three = sw_three(energies, left, right, tnn, t13)
        beta_edge = 0.65 * local["local_gap"]
        j1_edge = two["first_J1"] * beta_edge + two["second_J1_per_bond"] * beta_edge**2
        j2_edge = three["second_J2_induced"] * beta_edge**2
        finite_c2 = float(finite[round(alpha, 12)]["C2_intercept"])
        rows.append(
            {
                "alpha": alpha,
                "local_gap": local["local_gap"],
                "projection_J1_over_beta": local["jeff_over_beta"],
                **two,
                **three,
                "linked_constant_error": three["second_constant_three"] - 2 * two["second_constant_per_bond"],
                "linked_J1_error": three["second_J1_three"] - two["second_J1_per_bond"],
                "finite_beta_C2_intercept": finite_c2,
                "finite_beta_C2_relative_error": (finite_c2 - two["second_singlet_C2"]) / abs(two["second_singlet_C2"]),
                "J2_over_second_J1": three["second_J2_induced"] / two["second_J1_per_bond"],
                "controlled_edge_beta": beta_edge,
                "controlled_edge_J2_over_J1": j2_edge / j1_edge,
                "induced_frustration_slope": three["second_J2_induced"] / two["first_J1"],
                "min_excitation_denominator_abs": energies[2] - energies[0],
            }
        )
        if index % 10 == 0:
            print(f"已完成 alpha {index}/{len(projection)}", flush=True)
    return rows


def make_figure(rows: list[dict[str, object]]) -> None:
    alpha = np.asarray([float(row["alpha"]) for row in rows])
    gap = np.asarray([float(row["local_gap"]) for row in rows])
    c1 = np.asarray([float(row["first_J1"]) for row in rows])
    j1_2 = np.asarray([float(row["second_J1_per_bond"]) for row in rows])
    j2_2 = np.asarray([float(row["second_J2_induced"]) for row in rows])
    ratio = np.asarray([float(row["J2_over_second_J1"]) for row in rows])
    edge = np.asarray([float(row["controlled_edge_J2_over_J1"]) for row in rows])
    width = 183 / 25.4
    fig, axes = plt.subplots(1, 3, figsize=(width, 3.0), gridspec_kw={"width_ratios": [1.25, 1.05, 1.15]})
    axes[0].plot(alpha, j1_2 * gap / c1, color="#3B6FB6", lw=1.2, label=r"$\delta J_1^{(2)}\Delta/J_1^{(1)}$")
    axes[0].plot(alpha, j2_2 * gap / c1, color="#B85C5C", lw=1.2, label=r"$J_2^{(2)}\Delta/J_1^{(1)}$")
    axes[0].set(xlabel=r"$\alpha$", ylabel="scaled second-order coefficient")
    axes[0].legend(fontsize=5.5)
    axes[1].plot(alpha, ratio, color="#8064A2", lw=1.2)
    axes[1].axhline(0.0, color="black", lw=0.7)
    axes[1].set(xlabel=r"$\alpha$", ylabel=r"$J_2^{(2)}/\delta J_1^{(2)}$")
    for control, color in zip((0.10, 0.30, 0.65), ("#2A9D8F", "#D28E2C", "#B85C5C")):
        beta = control * gap
        value = j2_2 * beta**2 / (c1 * beta + j1_2 * beta**2)
        axes[2].plot(alpha, 100 * value, color=color, lw=1.1, label=rf"$\beta/\Delta={control:.2f}$")
    axes[2].plot(alpha, 100 * edge, color="#B85C5C", lw=0, alpha=0)
    axes[2].set(xlabel=r"$\alpha$", ylabel=r"induced $J_2/J_1$ (%)")
    axes[2].legend(fontsize=5.5)
    for index, axis in enumerate(axes):
        axis.text(-0.18, 1.04, chr(ord("a") + index), transform=axis.transAxes, fontweight="bold", fontsize=8)
    fig.tight_layout(w_pad=1.5)
    base = OUTDIR / "schrieffer_wolff_second_order"
    fig.savefig(base.with_suffix(".svg"), bbox_inches="tight")
    fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(base.with_suffix(".png"), dpi=300, bbox_inches="tight")
    fig.savefig(base.with_suffix(".tiff"), dpi=600, bbox_inches="tight", pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    rows = calculate()
    write_csv(OUTDIR / "schrieffer_wolff_scan.csv", rows)
    representatives = [row for row in rows if any(math.isclose(float(row["alpha"]), value) for value in (0.14, 0.23, 0.33, 1.0))]
    write_csv(OUTDIR / "representative_coefficients.csv", representatives)
    make_figure(rows)
    j2 = np.asarray([float(row["second_J2_induced"]) for row in rows])
    ratio = np.asarray([float(row["J2_over_second_J1"]) for row in rows])
    edge = np.asarray([float(row["controlled_edge_J2_over_J1"]) for row in rows])
    summary = {
        "status": "paper_direction_candidate",
        "claim": "二阶虚激发在全正 alpha 区域诱导反铁磁次近邻交换，形成受控但较弱的有效挫折。",
        "effective_hamiltonian": "H_eff = sum_n [E0 + beta*J1_1*Tn.Tn1 + beta^2*(C2 + J1_2*Tn.Tn1)] + beta^2*J2_2*sum_n Tn.Tn2 + O(beta^3)",
        "alpha_points": len(rows),
        "single_cell_dimension": 32,
        "two_cell_product_dimension": 1024,
        "three_cell_product_dimension": 32768,
        "low_energy_dimensions": [4, 8],
        "all_induced_J2_antiferromagnetic": bool(np.all(j2 > 0)),
        "J2_second_range": [float(np.min(j2)), float(np.max(j2))],
        "J2_over_second_J1_range": [float(np.min(ratio)), float(np.max(ratio))],
        "controlled_edge_J2_over_J1_range": [float(np.min(edge)), float(np.max(edge))],
        "max_two_fit_relative_residual": max(float(row["second_fit_relative_residual"]) for row in rows),
        "max_three_fit_relative_residual": max(float(row["second_three_fit_relative_residual"]) for row in rows),
        "max_linked_constant_error": max(abs(float(row["linked_constant_error"])) for row in rows),
        "max_linked_J1_error": max(abs(float(row["linked_J1_error"])) for row in rows),
        "max_finite_beta_C2_relative_error": max(abs(float(row["finite_beta_C2_relative_error"])) for row in rows),
        "max_hermiticity_error": max(max(float(row["second_hermiticity_error"]), float(row["second_three_hermiticity_error"])) for row in rows),
        "interpretation": "三胞连通项只产生正的 J2_2；在 beta/local_gap=0.65 的受控边缘，J2/J1 仍约为几个百分点。",
        "new_paper_assessment": "值得保留为独立文章候选：需要推广到一般奇数团簇，并用三胞以上数值或解析谱和验证系数的可迁移性。当前证据不足以单独投稿。",
        "figure_contract": {
            "core_conclusion": "虚激发诱导 AFM 次近邻交换，但在当前受控弱耦合区只形成弱挫折。",
            "evidence_chain": ["a: 二阶系数的正区扫描", "b: 诱导 J2 相对最近邻修正", "c: 固定控制比下的有效挫折比例"],
            "archetype": "quantitative grid",
            "backend": "Python/matplotlib",
            "export": "183 mm；SVG/PDF；PNG 300 dpi；LZW TIFF 600 dpi",
        },
    }
    (OUTDIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUTDIR / "run-command.txt").write_text(f"{sys.executable} {Path(__file__)}\n", encoding="utf-8")
    files = sorted(path for path in OUTDIR.iterdir() if path.name != "checksums.sha256")
    (OUTDIR / "checksums.sha256").write_text("".join(f"{sha256(path)}  {path.name}\n" for path in files if path.is_file()), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
