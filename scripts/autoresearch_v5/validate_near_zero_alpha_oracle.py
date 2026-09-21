#!/usr/bin/env python3
"""8 自旋 near-alpha0 受控极限 ED oracle。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import platform
import sys
import time
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np


N_SITES = 8
FULL_DIM = 1 << N_SITES
ALPHA_MAGNITUDES = (0.000625, 0.00125, 0.0025, 0.005, 0.01, 0.02, 0.04)
BETA_VALUES = (0.1, 0.25, 0.5)
CONTROL_POINTS = ((-0.10, 0.25), (-0.175, 0.25))
SECTOR_NUPS = (3, 4, 5)
EXPECTED_DIMS = {3: 56, 4: 70, 5: 56}
EXPECTED_ALPHA0_SECTOR_DEGENERACY = {3: 1, 4: 2, 5: 1}
GATE_RELATIVE_ERROR = 0.02
GATE_IMPROVEMENT_FACTOR = 0.75
NUMERIC_TOL = 1e-9


_I2 = np.eye(2, dtype=np.complex128)
_SX = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=np.complex128) / 2.0
_SY = np.array([[0.0, -1.0j], [1.0j, 0.0]], dtype=np.complex128) / 2.0
_SZ = np.array([[0.5, 0.0], [0.0, -0.5]], dtype=np.complex128)
_LOCAL_SPINS = (_SX, _SY, _SZ)


def _kron_site_operator(nsites: int, op: np.ndarray, site: int) -> np.ndarray:
    """把单点算符放入 Kronecker 空间。"""
    if not 0 <= site < nsites:
        raise ValueError("site 超出范围")
    result = np.array([[1.0 + 0.0j]])
    for pos in range(nsites):
        result = np.kron(result, op if pos == site else np.eye(2))
    return result


_FULL_SITE_SPINS = tuple(
    tuple(_kron_site_operator(N_SITES, op, site) for site in range(N_SITES))
    for op in _LOCAL_SPINS
)
_FULL_BOND_OPERATORS = tuple(
    sum(
        (_FULL_SITE_SPINS[axis][left] @ _FULL_SITE_SPINS[axis][right]
         for axis in range(3)),
        np.zeros((FULL_DIM, FULL_DIM), dtype=np.complex128),
    )
    for left, right in zip(range(N_SITES - 1), range(1, N_SITES))
)
_FULL_TOTAL_SPINS = tuple(
    sum(
        (_FULL_SITE_SPINS[axis][site] for site in range(N_SITES)),
        np.zeros((FULL_DIM, FULL_DIM), dtype=np.complex128),
    )
    for axis in range(3)
)
_FULL_S2 = sum(
    (operator @ operator for operator in _FULL_TOTAL_SPINS),
    np.zeros((FULL_DIM, FULL_DIM), dtype=np.complex128),
)


def _site_bit(site: int) -> int:
    """site=0 对应 Kronecker 空间的最高位。"""
    if not 0 <= site < N_SITES:
        raise ValueError("site 超出范围")
    return 1 << (N_SITES - 1 - site)


def _finite_float(value: object, field: str) -> float:
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{field} 不能是布尔值")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 不是数值") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} 不是有限数")
    return number


def _exact_nup(value: object) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise ValueError("nup 必须是整数")
    nup = int(value)
    if not 0 <= nup <= N_SITES:
        raise ValueError("nup 超出范围")
    return nup


def _couplings(alpha: object, beta: object) -> tuple[float, ...]:
    alpha_value = _finite_float(alpha, "alpha")
    beta_value = _finite_float(beta, "beta")
    if beta_value <= 0.0:
        raise ValueError("beta 必须为正")
    return (1.0, 1.0, alpha_value, beta_value, alpha_value, 1.0, 1.0)


def sector_basis(nup: object) -> list[int]:
    """生成固定上自旋数的 bit basis，1 表示 up。"""
    nup_value = _exact_nup(nup)
    return [state for state in range(FULL_DIM) if state.bit_count() == nup_value]


def build_sector_hamiltonian(alpha: object, beta: object, nup: object) -> tuple[list[int], np.ndarray]:
    """用 bit basis 构造固定 nup 的 Heisenberg 矩阵。"""
    couplings = _couplings(alpha, beta)
    basis = sector_basis(nup)
    index = {state: pos for pos, state in enumerate(basis)}
    matrix = np.zeros((len(basis), len(basis)), dtype=np.float64)
    for column, state in enumerate(basis):
        for bond, coupling in enumerate(couplings):
            left_bit = _site_bit(bond)
            right_bit = _site_bit(bond + 1)
            left_up = 1 if state & left_bit else 0
            right_up = 1 if state & right_bit else 0
            left_sz = 0.5 if left_up else -0.5
            right_sz = 0.5 if right_up else -0.5
            matrix[column, column] += coupling * left_sz * right_sz
            if left_up != right_up:
                flipped = state ^ left_bit ^ right_bit
                matrix[index[flipped], column] += 0.5 * coupling
    return basis, matrix


def build_full_hamiltonian(alpha: object, beta: object) -> np.ndarray:
    """用独立 Kronecker bond 算符构造完整矩阵。"""
    couplings = _couplings(alpha, beta)
    matrix = np.zeros((FULL_DIM, FULL_DIM), dtype=np.complex128)
    for coupling, bond_operator in zip(couplings, _FULL_BOND_OPERATORS):
        matrix += coupling * bond_operator
    return matrix


def build_kron_hamiltonian(nsites: int, bonds: Sequence[tuple[int, int, float]]) -> np.ndarray:
    """构造小系统独立 Kronecker Hamiltonian。"""
    if nsites <= 0:
        raise ValueError("nsites 必须为正")
    matrix = np.zeros((2 ** nsites, 2 ** nsites), dtype=np.complex128)
    for left, right, coupling in bonds:
        coupling_value = _finite_float(coupling, "coupling")
        for op in _LOCAL_SPINS:
            left_op = _kron_site_operator(nsites, op, left)
            right_op = _kron_site_operator(nsites, op, right)
            matrix += coupling_value * (left_op @ right_op)
    return matrix


def _matrix_error(matrix: np.ndarray) -> float:
    if matrix.size == 0:
        return 0.0
    return float(np.max(np.abs(matrix)))


def _eigen_checks(
    matrix: np.ndarray,
    eigenvalues: np.ndarray,
    eigenvectors: np.ndarray,
) -> dict[str, float | int]:
    residuals = np.linalg.norm(
        matrix @ eigenvectors - eigenvectors * eigenvalues[np.newaxis, :],
        axis=0,
    )
    norms = np.sum(np.abs(eigenvectors) ** 2, axis=0)
    orthogonality = eigenvectors.conj().T @ eigenvectors - np.eye(len(eigenvalues))
    reported = min(4, len(eigenvalues))
    return {
        "dimension": int(len(eigenvalues)),
        "reported_states": int(reported),
        "max_reported_residual": float(np.max(residuals[:reported])),
        "max_reported_norm_error": float(np.max(np.abs(norms[:reported] - 1.0))),
        "max_reported_orthogonality_error": float(
            np.max(np.abs(orthogonality[:reported, :reported]))
        ),
        "max_all_residual": float(np.max(residuals)),
        "max_all_norm_error": float(np.max(np.abs(norms - 1.0))),
        "max_all_orthogonality_error": float(np.max(np.abs(orthogonality))),
    }


def _s2_expectations(s2_matrix: np.ndarray, eigenvectors: np.ndarray) -> np.ndarray:
    return np.real_if_close(
        np.sum(eigenvectors.conj() * (s2_matrix @ eigenvectors), axis=0)
    ).real


def _expectations(operator: np.ndarray, eigenvectors: np.ndarray) -> np.ndarray:
    return np.real_if_close(
        np.sum(eigenvectors.conj() * (operator @ eigenvectors), axis=0)
    ).real


def _projection_eigenvalues(
    operator: np.ndarray,
    eigenvectors: np.ndarray,
    eigenvalues: np.ndarray,
    target_energy: float,
    tolerance: float = NUMERIC_TOL,
) -> np.ndarray:
    selected = np.flatnonzero(np.abs(eigenvalues - target_energy) <= tolerance)
    if len(selected) == 0:
        raise AssertionError("未找到目标简并子空间")
    projected = eigenvectors[:, selected].conj().T @ operator @ eigenvectors[:, selected]
    return np.linalg.eigvalsh(projected)


def two_spin_benchmark() -> dict[str, object]:
    matrix = build_kron_hamiltonian(2, ((0, 1, 1.0),))
    eigenvalues = np.linalg.eigvalsh(matrix)
    expected = np.array([-0.75, 0.25, 0.25, 0.25])
    return {
        "eigenvalues": [float(x) for x in eigenvalues],
        "expected": [float(x) for x in expected],
        "max_abs_error": float(np.max(np.abs(eigenvalues - expected))),
        "hermiticity_error": _matrix_error(matrix - matrix.conj().T),
    }


def three_spin_projection_validation() -> dict[str, object]:
    matrix = build_kron_hamiltonian(3, ((0, 1, 1.0), (1, 2, 1.0)))
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    ground = np.flatnonzero(np.abs(eigenvalues - eigenvalues[0]) <= NUMERIC_TOL)
    subspace = eigenvectors[:, ground]
    total_spins = tuple(
        sum(
            (_kron_site_operator(3, op, site) for site in range(3)),
            np.zeros((8, 8), dtype=np.complex128),
        )
        for op in _LOCAL_SPINS
    )
    effective_spins = tuple(subspace.conj().T @ operator @ subspace for operator in total_spins)
    coefficients: list[float] = []
    coefficient_matrices: list[list[list[float]]] = []
    projection_residuals: list[float] = []
    for site in range(3):
        local_projected = tuple(
            subspace.conj().T
            @ _kron_site_operator(3, op, site)
            @ subspace
            for op in _LOCAL_SPINS
        )
        denominator = sum(
            np.trace(operator.conj().T @ operator).real for operator in effective_spins
        )
        numerator = sum(
            np.trace(effective_spins[axis].conj().T @ local_projected[axis]).real
            for axis in range(3)
        )
        scalar = float(numerator / denominator)
        coefficients.append(scalar)
        component_matrix = np.zeros((3, 3), dtype=np.float64)
        for row in range(3):
            for column in range(3):
                denom = np.trace(effective_spins[column].conj().T @ effective_spins[column]).real
                component_matrix[row, column] = float(
                    np.trace(effective_spins[column].conj().T @ local_projected[row]).real
                    / denom
                )
        coefficient_matrices.append(component_matrix.tolist())
        projection_residuals.append(
            max(
                float(np.linalg.norm(local_projected[axis] - scalar * effective_spins[axis]))
                for axis in range(3)
            )
        )
    expected = np.array([2.0 / 3.0, -1.0 / 3.0, 2.0 / 3.0])
    return {
        "ground_energy": float(eigenvalues[0]),
        "ground_degeneracy": int(len(ground)),
        "coefficients_from_projection": coefficients,
        "expected_coefficients": [float(x) for x in expected],
        "max_coefficient_error": float(np.max(np.abs(np.array(coefficients) - expected))),
        "component_coefficient_matrices": coefficient_matrices,
        "max_projection_matrix_residual": float(max(projection_residuals)),
        "phase_gauge": "同一简并子空间基底同时投影，不固定任一本征向量相位",
    }


def _alpha_zero_checks(
    beta: float,
    full_matrix: np.ndarray,
    sector_eigenvalues: dict[int, np.ndarray],
) -> dict[str, object]:
    expected_energy = -2.0 - 0.75 * beta
    full_eigenvalues, full_eigenvectors = np.linalg.eigh(full_matrix)
    selected = np.flatnonzero(np.abs(full_eigenvalues - expected_energy) <= NUMERIC_TOL)
    ground_vectors = full_eigenvectors[:, selected]
    s2_values = np.linalg.eigvalsh(ground_vectors.conj().T @ _FULL_S2 @ ground_vectors)
    sector_degeneracies = {
        str(nup): int(np.count_nonzero(np.abs(values - expected_energy) <= NUMERIC_TOL))
        for nup, values in sector_eigenvalues.items()
    }
    expected_s2 = np.array([0.0, 2.0, 2.0, 2.0])
    return {
        "expected_energy": expected_energy,
        "energy_error": float(abs(full_eigenvalues[0] - expected_energy)),
        "full_ground_degeneracy": int(len(selected)),
        "sector_ground_degeneracies": sector_degeneracies,
        "expected_sector_ground_degeneracies": {
            str(nup): int(value) for nup, value in EXPECTED_ALPHA0_SECTOR_DEGENERACY.items()
        },
        "ground_subspace_s2": [float(x) for x in s2_values],
        "s2_multiplet_error": float(
            np.max(np.abs(np.sort(s2_values) - expected_s2))
        ) if len(s2_values) == 4 else float("inf"),
        "pass": bool(
            abs(full_eigenvalues[0] - expected_energy) <= NUMERIC_TOL
            and len(selected) == 4
            and sector_degeneracies == {
                str(nup): int(value) for nup, value in EXPECTED_ALPHA0_SECTOR_DEGENERACY.items()
            }
            and len(s2_values) == 4
            and np.max(np.abs(np.sort(s2_values) - expected_s2)) <= 10 * NUMERIC_TOL
        ),
    }


def _compare_point_constructions(
    full_matrix: np.ndarray,
    basis: Sequence[int],
    sector_matrix: np.ndarray,
) -> float:
    # bit=1 表示 up，而 Kronecker 的局域索引 0 表示 up。
    mapped_basis = [FULL_DIM - 1 - state for state in basis]
    projected = full_matrix[np.ix_(mapped_basis, mapped_basis)]
    return _matrix_error(projected - sector_matrix)


def evaluate_point(alpha: object, beta: object, point_role: str = "grid") -> dict[str, object]:
    alpha_value = _finite_float(alpha, "alpha")
    beta_value = _finite_float(beta, "beta")
    _couplings(alpha_value, beta_value)
    full_matrix = build_full_hamiltonian(alpha_value, beta_value)
    sector_data: dict[int, dict[str, object]] = {}
    construction_errors: list[float] = []
    for nup in SECTOR_NUPS:
        basis, sector_matrix = build_sector_hamiltonian(alpha_value, beta_value, nup)
        construction_errors.append(
            _compare_point_constructions(full_matrix, basis, sector_matrix)
        )
        eigenvalues, eigenvectors = np.linalg.eigh(sector_matrix)
        mapped_basis = [FULL_DIM - 1 - state for state in basis]
        s2_sector = _FULL_S2[np.ix_(mapped_basis, mapped_basis)]
        sz_sector = _FULL_TOTAL_SPINS[2][np.ix_(mapped_basis, mapped_basis)]
        checks = _eigen_checks(sector_matrix, eigenvalues, eigenvectors)
        checks["hermiticity_error"] = _matrix_error(
            sector_matrix - sector_matrix.conj().T
        )
        checks["target_sz"] = float(nup - N_SITES / 2.0)
        sz_values = _expectations(sz_sector, eigenvectors)
        checks["max_total_sz_error"] = float(
            np.max(np.abs(sz_values - checks["target_sz"]))
        )
        sector_data[nup] = {
            "basis": basis,
            "matrix": sector_matrix,
            "eigenvalues": eigenvalues,
            "eigenvectors": eigenvectors,
            "s2": _s2_expectations(s2_sector, eigenvectors),
            "sz": sz_values,
            "checks": checks,
        }
    e_sz0 = sector_data[4]["eigenvalues"]
    e_sz1 = sector_data[5]["eigenvalues"]
    e_sz_minus1 = sector_data[3]["eigenvalues"]
    gap = float(e_sz1[0] - e_sz0[0])
    row: dict[str, object] = {
        "point_role": point_role,
        "alpha": alpha_value,
        "beta": beta_value,
        "alpha_abs": abs(alpha_value),
        "nup4_dimension": int(len(sector_data[4]["basis"])),
        "nup5_dimension": int(len(sector_data[5]["basis"])),
        "nup3_dimension": int(len(sector_data[3]["basis"])),
        "E_sz0": float(e_sz0[0]),
        "E_sz1": float(e_sz1[0]),
        "E_sz_minus1": float(e_sz_minus1[0]),
        "gap_sz1_minus_sz0": gap,
        "gap_over_alpha2": None if alpha_value == 0.0 else float(gap / alpha_value**2),
        "predicted_gap_over_alpha2": None if alpha_value == 0.0 else float(2.0 / (9.0 * beta_value)),
        "prediction_relative_error": (
            None
            if alpha_value == 0.0
            else float((gap / alpha_value**2) / (2.0 / (9.0 * beta_value)) - 1.0)
        ),
        "asymptotic_gate_applicable": bool(
            point_role == "grid" and alpha_value != 0.0
        ),
        "s2_sz0_ground": None,
        "s2_sz1_ground": None,
        "s2_sz_minus1_ground": None,
        "s2_sz0_triplet_match": None,
        "sz0_triplet_energy_match_error": None,
        "total_sz_sz0_ground": float(sector_data[4]["sz"][0]),
        "total_sz_sz1_ground": float(sector_data[5]["sz"][0]),
        "total_sz_sz_minus1_ground": float(sector_data[3]["sz"][0]),
        "max_total_sz_error": float(
            max(sector_data[nup]["checks"]["max_total_sz_error"] for nup in SECTOR_NUPS)
        ),
        "dimension_match": bool(
            all(
                int(sector_data[nup]["checks"]["dimension"]) == EXPECTED_DIMS[nup]
                for nup in SECTOR_NUPS
            )
        ),
        "full_hermiticity_error": _matrix_error(full_matrix - full_matrix.conj().T),
        "construction_max_abs_error": float(max(construction_errors)),
        "max_reported_residual": float(
            max(sector_data[nup]["checks"]["max_reported_residual"] for nup in SECTOR_NUPS)
        ),
        "max_reported_norm_error": float(
            max(sector_data[nup]["checks"]["max_reported_norm_error"] for nup in SECTOR_NUPS)
        ),
        "max_reported_orthogonality_error": float(
            max(
                sector_data[nup]["checks"]["max_reported_orthogonality_error"]
                for nup in SECTOR_NUPS
            )
        ),
        "max_all_residual": float(
            max(sector_data[nup]["checks"]["max_all_residual"] for nup in SECTOR_NUPS)
        ),
        "max_all_norm_error": float(
            max(sector_data[nup]["checks"]["max_all_norm_error"] for nup in SECTOR_NUPS)
        ),
        "max_all_orthogonality_error": float(
            max(
                sector_data[nup]["checks"]["max_all_orthogonality_error"]
                for nup in SECTOR_NUPS
            )
        ),
    }
    if alpha_value != 0.0:
        row["s2_sz0_ground"] = float(sector_data[4]["s2"][0])
        row["s2_sz1_ground"] = float(sector_data[5]["s2"][0])
        row["s2_sz_minus1_ground"] = float(sector_data[3]["s2"][0])
        triplet_index = int(np.argmin(np.abs(e_sz0 - e_sz1[0])))
        row["s2_sz0_triplet_match"] = float(sector_data[4]["s2"][triplet_index])
        row["sz0_triplet_energy_match_error"] = float(
            abs(e_sz0[triplet_index] - e_sz1[0])
        )
    else:
        row["alpha0_checks"] = _alpha_zero_checks(
            beta_value,
            full_matrix,
            {nup: sector_data[nup]["eigenvalues"] for nup in SECTOR_NUPS},
        )
    return row


def _grid_points() -> list[tuple[float, float, str]]:
    points: list[tuple[float, float, str]] = []
    for beta in BETA_VALUES:
        points.append((0.0, beta, "grid"))
        for magnitude in ALPHA_MAGNITUDES:
            points.append((-magnitude, beta, "grid"))
            points.append((magnitude, beta, "grid"))
    return points


def _asymptotic_gate(rows: Iterable[dict[str, object]]) -> dict[str, object]:
    grid_rows = [
        row
        for row in rows
        if row["point_role"] == "grid" and float(row["alpha"]) != 0.0
    ]
    groups: list[dict[str, object]] = []
    for beta in BETA_VALUES:
        for sign, label in ((-1, "negative"), (1, "positive")):
            selected = sorted(
                (
                    row
                    for row in grid_rows
                    if abs(float(row["beta"]) - beta) < 1e-15
                    and math.copysign(1.0, float(row["alpha"])) == sign
                ),
                key=lambda row: float(row["alpha_abs"]),
            )
            small_error = abs(float(selected[0]["prediction_relative_error"]))
            next_error = abs(float(selected[1]["prediction_relative_error"]))
            improves = (
                small_error == 0.0
                if next_error == 0.0
                else small_error <= GATE_IMPROVEMENT_FACTOR * next_error
            )
            groups.append(
                {
                    "beta": beta,
                    "sign": label,
                    "smallest_alpha": float(selected[0]["alpha"]),
                    "smallest_abs_relative_error": small_error,
                    "second_abs_relative_error": next_error,
                    "smallest_error_below_2pct": bool(
                        small_error < GATE_RELATIVE_ERROR
                    ),
                    "small_alpha_improves_by_25pct": bool(improves),
                    "pass": bool(
                        small_error < GATE_RELATIVE_ERROR and improves
                    ),
                }
            )
    return {
        "criteria": {
            "smallest_abs_relative_error_lt": GATE_RELATIVE_ERROR,
            "smallest_vs_second_abs_error_factor_le": GATE_IMPROVEMENT_FACTOR,
            "applies_only_to": "42 nonzero grid points, not finite_alpha_control rows",
        },
        "groups": groups,
        "all_pass": bool(all(group["pass"] for group in groups)),
    }


def _validation_gates(
    rows: Sequence[dict[str, object]],
    benchmark: dict[str, object],
    trimer: dict[str, object],
    alpha0_checks: dict[str, dict[str, object]],
) -> dict[str, bool]:
    nonzero = [
        row
        for row in rows
        if float(row["alpha"]) != 0.0
    ]
    return {
        "dimensions": bool(all(bool(row["dimension_match"]) for row in rows)),
        "hermiticity": bool(
            all(float(row["full_hermiticity_error"]) <= 1e-10 for row in rows)
        ),
        "bit_vs_full_construction": bool(
            all(float(row["construction_max_abs_error"]) <= 1e-10 for row in rows)
        ),
        "eigen_residuals": bool(
            all(float(row["max_all_residual"]) <= 1e-10 for row in rows)
        ),
        "eigen_normalization": bool(
            all(float(row["max_all_norm_error"]) <= 1e-10 for row in rows)
        ),
        "eigen_orthogonality": bool(
            all(float(row["max_all_orthogonality_error"]) <= 1e-10 for row in rows)
        ),
        "total_sz": bool(
            all(float(row["max_total_sz_error"]) <= 1e-10 for row in rows)
        ),
        "two_spin_benchmark": bool(
            float(benchmark["max_abs_error"]) <= 1e-12
            and float(benchmark["hermiticity_error"]) <= 1e-12
        ),
        "three_spin_projection": bool(
            int(trimer["ground_degeneracy"]) == 2
            and float(trimer["max_coefficient_error"]) <= 1e-10
            and float(trimer["max_projection_matrix_residual"]) <= 1e-10
        ),
        "alpha0_multiplets": bool(
            all(bool(check["pass"]) for check in alpha0_checks.values())
        ),
        "nonzero_su2_multiplets": bool(
            all(
                abs(float(row["s2_sz0_ground"])) <= 1e-8
                and abs(float(row["s2_sz1_ground"]) - 2.0) <= 1e-8
                and abs(float(row["s2_sz_minus1_ground"]) - 2.0) <= 1e-8
                and abs(float(row["s2_sz0_triplet_match"]) - 2.0) <= 1e-8
                and float(row["sz0_triplet_energy_match_error"]) <= 1e-10
                and float(row["gap_sz1_minus_sz0"]) > 0.0
                for row in nonzero
            )
        ),
    }


def _status_from_gates(validation_pass: bool, asymptotic_pass: bool) -> str:
    if validation_pass and asymptotic_pass:
        return "pass"
    if not validation_pass and not asymptotic_pass:
        return "validation_and_asymptotic_gate_failed"
    if not validation_pass:
        return "validation_gate_failed"
    return "asymptotic_gate_failed"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    fields = [
        "point_role",
        "alpha",
        "beta",
        "alpha_abs",
        "nup3_dimension",
        "nup4_dimension",
        "nup5_dimension",
        "E_sz0",
        "E_sz1",
        "E_sz_minus1",
        "gap_sz1_minus_sz0",
        "gap_over_alpha2",
        "predicted_gap_over_alpha2",
        "prediction_relative_error",
        "asymptotic_gate_applicable",
        "s2_sz0_ground",
        "s2_sz1_ground",
        "s2_sz_minus1_ground",
        "s2_sz0_triplet_match",
        "sz0_triplet_energy_match_error",
        "full_hermiticity_error",
        "construction_max_abs_error",
        "max_reported_residual",
        "max_reported_norm_error",
        "max_reported_orthogonality_error",
        "max_all_residual",
        "max_all_norm_error",
        "max_all_orthogonality_error",
        "alpha0_checks",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            output = {field: row.get(field) for field in fields}
            if isinstance(output.get("alpha0_checks"), dict):
                output["alpha0_checks"] = json.dumps(
                    output["alpha0_checks"], ensure_ascii=False, sort_keys=True
                )
            writer.writerow(output)


def _prepare_output_dir(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise FileExistsError(f"输出路径不是目录：{path}")
        if any(path.iterdir()):
            raise FileExistsError(f"拒绝覆盖非空输出目录：{path}")
    else:
        path.mkdir(parents=True, exist_ok=False)


def _runtime_metadata(script_path: Path, test_path: Path) -> dict[str, object]:
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "backend": "NumPy custom bit-sector + independent full Kronecker matrix",
        "xdiag_used": False,
        "quspin_used": False,
        "dependency_note": "本机无可用 XDiag/QuSpin；未调用 Julia，未安装依赖",
        "script_sha256": _sha256(script_path),
        "test_sha256": _sha256(test_path),
    }


def run_oracle(out_dir: Path) -> dict[str, object]:
    _prepare_output_dir(out_dir)
    script_path = Path(__file__).resolve()
    test_path = script_path.with_name("test_near_zero_alpha_oracle.py")
    if not test_path.is_file():
        raise FileNotFoundError(f"测试文件不存在：{test_path}")
    started = time.perf_counter()
    benchmark = two_spin_benchmark()
    trimer = three_spin_projection_validation()

    probe_started = time.perf_counter()
    probe_row = evaluate_point(-ALPHA_MAGNITUDES[0], BETA_VALUES[0], "grid")
    probe_elapsed = time.perf_counter() - probe_started

    rows: list[dict[str, object]] = [probe_row]
    probe_key = (float(probe_row["alpha"]), float(probe_row["beta"]))
    for alpha, beta, role in _grid_points():
        if (alpha, beta) == probe_key:
            continue
        rows.append(evaluate_point(alpha, beta, role))
    for alpha, beta in CONTROL_POINTS:
        rows.append(evaluate_point(alpha, beta, "finite_alpha_control"))
    rows.sort(
        key=lambda row: (
            float(row["beta"]),
            float(row["alpha"]),
            0 if row["point_role"] == "grid" else 1,
        )
    )
    gate = _asymptotic_gate(rows)
    grid_rows = [row for row in rows if row["point_role"] == "grid"]
    controls = [row for row in rows if row["point_role"] == "finite_alpha_control"]
    alpha0_checks = {
        str(beta): next(
            row["alpha0_checks"]
            for row in rows
            if row["point_role"] == "grid"
            and float(row["alpha"]) == 0.0
            and abs(float(row["beta"]) - beta) < 1e-15
        )
        for beta in BETA_VALUES
    }
    summary_checks = {
        "max_construction_error": float(
            max(float(row["construction_max_abs_error"]) for row in rows)
        ),
        "max_full_hermiticity_error": float(
            max(float(row["full_hermiticity_error"]) for row in rows)
        ),
        "max_reported_residual": float(
            max(float(row["max_reported_residual"]) for row in rows)
        ),
        "max_reported_norm_error": float(
            max(float(row["max_reported_norm_error"]) for row in rows)
        ),
        "max_reported_orthogonality_error": float(
            max(float(row["max_reported_orthogonality_error"]) for row in rows)
        ),
        "max_all_residual": float(max(float(row["max_all_residual"]) for row in rows)),
        "max_all_norm_error": float(max(float(row["max_all_norm_error"]) for row in rows)),
        "max_all_orthogonality_error": float(
            max(float(row["max_all_orthogonality_error"]) for row in rows)
        ),
        "max_total_sz_error": float(
            max(float(row["max_total_sz_error"]) for row in rows)
        ),
    }
    validation_gates = _validation_gates(
        rows,
        benchmark,
        trimer,
        alpha0_checks,
    )
    spec = {
        "schema": "near_zero_alpha_oracle/v2",
        "model": {
            "sites": 8,
            "boundary": "OBC",
            "spin_convention": "S=Pauli/2",
            "bond_pattern": "[1,1,alpha,beta,alpha,1,1]",
            "gap_definition": "lowest Sz=1 energy minus lowest Sz=0 energy",
        },
        "basis": {
            "bit_sector": "bit=1 is up; site 0 is the Kronecker-space high bit",
            "full_index_mapping": "full_index=FULL_DIM-1-bit_state",
            "sectors": {"nup=3": 56, "nup=4": 70, "nup=5": 56},
            "full_dimension": 256,
        },
        "independent_construction": {
            "bit_sector_vs_full_kron": True,
            "interpretation": "independent Hamiltonian-construction check, not a second many-body method",
        },
        "grid": {
            "beta": list(BETA_VALUES),
            "alpha_magnitudes": list(ALPHA_MAGNITUDES),
            "nonzero_points": 42,
            "zero_points": 3,
        },
        "finite_alpha_controls": [
            {"alpha": alpha, "beta": beta, "point_role": "finite_alpha_control"}
            for alpha, beta in CONTROL_POINTS
        ],
        "prediction": {
            "gap_over_alpha2": "2/(9*beta)",
            "asymptotic_gate": {
                "smallest_abs_relative_error_lt": GATE_RELATIVE_ERROR,
                "smallest_vs_second_abs_error_factor_le": GATE_IMPROVEMENT_FACTOR,
                "controls_excluded": True,
            },
        },
        "validation": {
            "two_spin_benchmark": "[-0.75,0.25,0.25,0.25]",
            "alpha0_energy": "-2-3*beta/4",
            "alpha0_full_ground_degeneracy": 4,
            "alpha0_sector_ground_degeneracy": {"Sz=-1": 1, "Sz=0": 2, "Sz=1": 1},
            "trimer_projection": "[2/3,-1/3,2/3] from projected spin matrices",
            "phase_gauge": "same degenerate subspace basis for all projected spin components",
        },
        "source_note": "docs/near_zero_alpha_mechanism_note_20260919.md",
    }
    _write_json(out_dir / "spec.json", spec)
    _write_csv(out_dir / "oracle_points.csv", rows)
    elapsed = time.perf_counter() - started
    summary: dict[str, object] = {
        "schema": "near_zero_alpha_oracle/v2",
        "status": _status_from_gates(
            all(validation_gates.values()),
            bool(gate["all_pass"]),
        ),
        "backend": _runtime_metadata(script_path, test_path),
        "elapsed_s": float(elapsed),
        "timing_probe": {
            "alpha": -ALPHA_MAGNITUDES[0],
            "beta": BETA_VALUES[0],
            "elapsed_s": float(probe_elapsed),
        },
        "point_counts": {
            "grid_total": len(grid_rows),
            "grid_nonzero": sum(
                1 for row in grid_rows if float(row["alpha"]) != 0.0
            ),
            "grid_zero": sum(
                1 for row in grid_rows if float(row["alpha"]) == 0.0
            ),
            "finite_alpha_controls": len(controls),
            "total": len(rows),
        },
        "prediction": {
            "definition": "gap=E0(Sz=1)-E0(Sz=0) in this 8-spin oracle only",
            "not_full_chain_gap": True,
            "asymptotic_gate": gate,
            "finite_alpha_controls": [
                {
                    "alpha": row["alpha"],
                    "beta": row["beta"],
                    "prediction_relative_error": row["prediction_relative_error"],
                    "asymptotic_gate_applicable": False,
                }
                for row in controls
            ],
        },
        "benchmarks": {
            "two_spin": benchmark,
            "three_spin_projection": trimer,
        },
        "alpha0_checks": alpha0_checks,
        "matrix_and_eigen_checks": summary_checks,
        "validation_gates": validation_gates,
        "validation_gate_pass": bool(all(validation_gates.values())),
        "limitations": [
            "8-spin finite-cluster oracle，不是完整 OBC 链的 Sz gap 或热力学相判断",
            "full Kronecker 仅为独立 Hamiltonian 构造核对，不是独立多体方法",
            "仅对预注册非零网格应用 2% 渐近门；finite_alpha_control 不套该门",
            "NumPy 自定义实现，未使用 XDiag 或 QuSpin",
            "若渐近门失败，保留全部原始点并如实标记，不删点或用拟合替代原始表格",
        ],
        "artifacts": {
            "spec": "spec.json",
            "points": "oracle_points.csv",
            "summary": "summary.json",
            "checksums": "checksums.sha256",
        },
    }
    artifact_hashes = {
        name: _sha256(out_dir / name)
        for name in ("spec.json", "oracle_points.csv")
    }
    summary["artifact_hashes"] = artifact_hashes
    _write_json(out_dir / "summary.json", summary)
    checksum_paths = [
        out_dir / "spec.json",
        out_dir / "oracle_points.csv",
        out_dir / "summary.json",
    ]
    checksum_lines = []
    for path in checksum_paths:
        label = path.name
        checksum_lines.append(f"{_sha256(path)}  {label}")
    (out_dir / "checksums.sha256").write_text(
        "\n".join(checksum_lines) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    summary = run_oracle(args.out_dir.resolve())
    print(
        json.dumps(
            {
                "status": summary["status"],
                "points": summary["point_counts"]["total"],
                "elapsed_s": summary["elapsed_s"],
                "asymptotic_gate": summary["prediction"]["asymptotic_gate"]["all_pass"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
