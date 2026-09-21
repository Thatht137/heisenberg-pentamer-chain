#!/usr/bin/env python3
"""10 自旋双五聚体固定 $S_z$ 的 NumPy 精确对角化 oracle。"""

from __future__ import annotations

import json
from itertools import combinations
from numbers import Integral, Real
from typing import Any, Sequence

import numpy as np


N_SITES = 10
DEFAULT_ALPHAS = (-0.1, -0.175)
DEFAULT_BETA = 0.25
TARGET_SZS = (0, 1)
SECTOR_DIMS = {0: 252, 1: 210}


def _real(value: Any, name: str) -> float:
    """检查有限实数且拒绝 bool。"""
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} 必须是有限实数且不能是 bool")
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"{name} 必须是有限实数")
    return result


def _integer(value: Any, name: str) -> int:
    """检查整数且拒绝 bool。"""
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral):
        raise ValueError(f"{name} 必须是整数且不能是 bool")
    return int(value)


def _validate_model_sites(n_sites: Any) -> int:
    n_sites = _integer(n_sites, "n_sites")
    if n_sites != N_SITES:
        raise ValueError(f"双五聚体 oracle 要求 n_sites={N_SITES}")
    return n_sites


def pentamer_bonds(alpha: Any, beta: Any) -> list[tuple[int, int, float]]:
    """返回 OBC 链的九条键，顺序为两个完整五聚体。"""
    alpha = _real(alpha, "alpha")
    beta = _real(beta, "beta")
    return [
        (0, 1, alpha),
        (1, 2, 1.0),
        (2, 3, 1.0),
        (3, 4, alpha),
        (4, 5, beta),
        (5, 6, alpha),
        (6, 7, 1.0),
        (7, 8, 1.0),
        (8, 9, alpha),
    ]


def bonds(alpha: Any, beta: Any) -> list[tuple[int, int, float]]:
    """兼容简短调用名。"""
    return pentamer_bonds(alpha, beta)


def sector_basis(n_sites: Any = N_SITES, n_up: Any | None = None) -> tuple[list[int], dict[int, int]]:
    """按 site 0 为最低 bit 构造固定上自旋数的 bit 基。"""
    n_sites = _integer(n_sites, "n_sites")
    if n_sites < 0:
        raise ValueError("n_sites 不能为负")
    if n_up is None:
        n_up = n_sites // 2
    n_up = _integer(n_up, "n_up")
    if not 0 <= n_up <= n_sites:
        raise ValueError("n_up 必须位于 [0, n_sites]")
    states = [
        sum(1 << site for site in occupied)
        for occupied in combinations(range(n_sites), n_up)
    ]
    return states, {state: index for index, state in enumerate(states)}


def bit_to_kron_index(state: Any, n_sites: Any = N_SITES) -> int:
    """将 site 0 为最低 bit 映射到 np.kron 的 site 0 最左顺序。"""
    n_sites = _integer(n_sites, "n_sites")
    if n_sites < 0:
        raise ValueError("n_sites 不能为负")
    state = _integer(state, "state")
    if not 0 <= state < (1 << n_sites):
        raise ValueError("state 超出 bit 基范围")
    index = 0
    for site in range(n_sites):
        index = (index << 1) | ((state >> site) & 1)
    return index


def kron_index_to_bit(index: Any, n_sites: Any = N_SITES) -> int:
    """将 np.kron 顺序索引反变换为 site 0 为最低 bit 的状态。"""
    n_sites = _integer(n_sites, "n_sites")
    if n_sites < 0:
        raise ValueError("n_sites 不能为负")
    index = _integer(index, "index")
    if not 0 <= index < (1 << n_sites):
        raise ValueError("index 超出 Kronecker 基范围")
    state = 0
    for site in range(n_sites):
        state |= ((index >> (n_sites - 1 - site)) & 1) << site
    return state


def build_sector_hamiltonian(
    alpha: Any,
    beta: Any,
    n_up: Any,
    *,
    n_sites: Any = N_SITES,
) -> tuple[list[int], np.ndarray]:
    """直接在固定 n_up bit 扇区构造实对称 Heisenberg 矩阵。"""
    n_sites = _validate_model_sites(n_sites)
    alpha = _real(alpha, "alpha")
    beta = _real(beta, "beta")
    states, state_index = sector_basis(n_sites, n_up)
    matrix = np.zeros((len(states), len(states)), dtype=np.float64)
    for column, state in enumerate(states):
        for left, right, coupling in pentamer_bonds(alpha, beta):
            left_up = (state >> left) & 1
            right_up = (state >> right) & 1
            matrix[column, column] += coupling * (0.25 if left_up == right_up else -0.25)
            if left_up != right_up:
                flipped = state ^ (1 << left) ^ (1 << right)
                matrix[state_index[flipped], column] += 0.5 * coupling
    return states, matrix


def sector_hamiltonian(alpha: Any, beta: Any, target_sz: Any) -> np.ndarray:
    """按 target_sz=0/1 返回 n_up=5/6 扇区矩阵。"""
    target_sz = _integer(target_sz, "target_sz")
    if target_sz not in TARGET_SZS:
        raise ValueError("target_sz 只能是 0 或 1")
    _, matrix = build_sector_hamiltonian(alpha, beta, 5 + target_sz)
    return matrix


def sector_matrix(alpha: Any, beta: Any, target_sz: Any) -> np.ndarray:
    """兼容 sector_hamiltonian 的简短调用名。"""
    return sector_hamiltonian(alpha, beta, target_sz)


_SX = np.array([[0.0, 0.5], [0.5, 0.0]], dtype=np.float64)
_SY = np.array([[0.0, -0.5j], [0.5j, 0.0]], dtype=np.complex128)
_SZ = np.array([[0.5, 0.0], [0.0, -0.5]], dtype=np.float64)
_LOCAL_BOND = np.real_if_close(
    np.kron(_SX, _SX) + np.kron(_SY, _SY) + np.kron(_SZ, _SZ),
    tol=1000,
).astype(np.float64)


def two_spin_hamiltonian(coupling: Any = 1.0) -> np.ndarray:
    """返回两个 spin=Pauli/2 的 J S_i·S_j 矩阵。"""
    coupling = _real(coupling, "coupling")
    return coupling * _LOCAL_BOND


def two_spin_spectrum(coupling: Any = 1.0) -> np.ndarray:
    """返回两个自旋的升序谱。"""
    return np.linalg.eigvalsh(two_spin_hamiltonian(coupling))


def _embed_adjacent(local: np.ndarray, left: int, n_sites: int) -> np.ndarray:
    prefix = np.eye(1 << left, dtype=np.float64)
    suffix = np.eye(1 << (n_sites - left - 2), dtype=np.float64)
    return np.kron(prefix, np.kron(local, suffix))


def build_full_hamiltonian(
    alpha: Any,
    beta: Any,
    *,
    n_sites: Any = N_SITES,
) -> np.ndarray:
    """以独立 Kronecker 构造完整 2**10 维矩阵。"""
    n_sites = _validate_model_sites(n_sites)
    alpha = _real(alpha, "alpha")
    beta = _real(beta, "beta")
    matrix = np.zeros((1 << n_sites, 1 << n_sites), dtype=np.float64)
    for left, right, coupling in pentamer_bonds(alpha, beta):
        if right != left + 1:
            raise ValueError("当前 Kronecker 构造只支持相邻键")
        matrix += _embed_adjacent(coupling * _LOCAL_BOND, left, n_sites)
    return matrix


def full_hamiltonian(alpha: Any, beta: Any) -> np.ndarray:
    """兼容 build_full_hamiltonian 的简短调用名。"""
    return build_full_hamiltonian(alpha, beta)


def project_full_hamiltonian(
    full_matrix: np.ndarray,
    basis: Sequence[Any],
    *,
    n_sites: Any = N_SITES,
) -> np.ndarray:
    """按 bit 到 kron 的显式映射投影完整矩阵。"""
    n_sites = _validate_model_sites(n_sites)
    full_matrix = np.asarray(full_matrix)
    expected_shape = (1 << n_sites, 1 << n_sites)
    if full_matrix.shape != expected_shape:
        raise ValueError(f"full_matrix 必须是 {expected_shape} 方阵")
    if not np.isfinite(full_matrix).all():
        raise ValueError("full_matrix 必须有限")
    indices = [bit_to_kron_index(state, n_sites) for state in basis]
    if len(set(indices)) != len(indices):
        raise ValueError("basis 含重复状态")
    return np.array(full_matrix[np.ix_(indices, indices)], copy=True)


def build_projected_full_hamiltonian(
    alpha: Any,
    beta: Any,
    n_up: Any,
) -> tuple[list[int], np.ndarray]:
    """构造完整矩阵后投影到固定 n_up 扇区。"""
    basis, _ = sector_basis(N_SITES, n_up)
    full = build_full_hamiltonian(alpha, beta)
    return basis, project_full_hamiltonian(full, basis)


def matrix_error(left: np.ndarray, right: np.ndarray) -> float:
    """返回两矩阵的最大绝对差。"""
    left = np.asarray(left)
    right = np.asarray(right)
    if left.shape != right.shape:
        raise ValueError("矩阵形状不一致")
    return float(np.max(np.abs(left - right))) if left.size else 0.0


def lowest_state(matrix: np.ndarray) -> tuple[float, np.ndarray, float]:
    """返回最低能量、本征矢和残差范数。"""
    matrix = np.asarray(matrix)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] or matrix.shape[0] == 0:
        raise ValueError("matrix 必须是非空方阵")
    if not np.isfinite(matrix).all():
        raise ValueError("matrix 必须有限")
    if not np.allclose(matrix, matrix.conj().T, atol=1e-12, rtol=1e-12):
        raise ValueError("matrix 必须 Hermitian")
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    energy = float(np.real(eigenvalues[0]))
    vector = np.asarray(eigenvectors[:, 0])
    residual = float(np.linalg.norm(matrix @ vector - energy * vector))
    return energy, vector, residual


def total_sz_for_n_up(n_up: Any, n_sites: Any = N_SITES) -> float:
    """返回 n_up 扇区的总 Sz。"""
    n_sites = _integer(n_sites, "n_sites")
    n_up = _integer(n_up, "n_up")
    if n_sites < 0 or not 0 <= n_up <= n_sites:
        raise ValueError("n_up 必须位于 [0, n_sites]")
    return float(n_up - n_sites / 2)


def expectation_total_sz(
    vector: np.ndarray,
    basis: Sequence[Any],
    *,
    n_sites: Any = N_SITES,
) -> float:
    """计算向量的归一化总 Sz 期望值。"""
    n_sites = _integer(n_sites, "n_sites")
    vector = np.asarray(vector)
    if vector.ndim != 1 or vector.size != len(basis):
        raise ValueError("vector 与 basis 维度不匹配")
    norm_squared = float(np.vdot(vector, vector).real)
    if not np.isfinite(norm_squared) or norm_squared <= 0.0:
        raise ValueError("vector 必须有正的有限范数")
    sz_values = np.array(
        [2 * _integer(state, "state").bit_count() - n_sites for state in basis],
        dtype=np.float64,
    ) / 2.0
    return float(np.vdot(vector, sz_values * vector).real / norm_squared)


def solve_sector(alpha: Any, beta: Any, target_sz: Any) -> dict[str, Any]:
    """求 target_sz=0/1 扇区最低态并返回诊断量。"""
    target_sz = _integer(target_sz, "target_sz")
    if target_sz not in TARGET_SZS:
        raise ValueError("target_sz 只能是 0 或 1")
    n_up = 5 + target_sz
    basis, matrix = build_sector_hamiltonian(alpha, beta, n_up)
    energy, vector, residual = lowest_state(matrix)
    norm = float(np.linalg.norm(vector))
    total_sz = expectation_total_sz(vector, basis)
    return {
        "alpha": _real(alpha, "alpha"),
        "beta": _real(beta, "beta"),
        "target_sz": target_sz,
        "n_up": n_up,
        "dimension": len(basis),
        "energy": energy,
        "vector": vector,
        "basis": basis,
        "hamiltonian": matrix,
        "residual_norm": residual,
        "residual": residual,
        "norm": norm,
        "vector_norm": norm,
        "total_sz": total_sz,
        "total_Sz": total_sz,
    }


def ground_state(alpha: Any, beta: Any, target_sz: Any) -> dict[str, Any]:
    """兼容 solve_sector 的命名。"""
    return solve_sector(alpha, beta, target_sz)


def reference_rows(
    alphas: Sequence[Any] = DEFAULT_ALPHAS,
    beta: Any = DEFAULT_BETA,
) -> list[dict[str, float | int]]:
    """返回两个 alpha、两个 Sz 扇区的四条 reference 记录。"""
    beta = _real(beta, "beta")
    rows: list[dict[str, float | int]] = []
    for alpha in alphas:
        alpha = _real(alpha, "alpha")
        for target_sz in TARGET_SZS:
            result = solve_sector(alpha, beta, target_sz)
            rows.append(
                {
                    "alpha": alpha,
                    "beta": beta,
                    "target_sz": target_sz,
                    "n_up": result["n_up"],
                    "dimension": result["dimension"],
                    "energy": result["energy"],
                    "residual_norm": result["residual_norm"],
                    "total_sz": result["total_sz"],
                }
            )
    return rows


def main() -> None:
    """打印四个固定参数点的 reference 能量。"""
    print(json.dumps(reference_rows(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
