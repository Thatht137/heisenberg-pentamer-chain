"""用双五聚体ED检验低能折叠谱权的绝对归一化。"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path

for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[variable] = "1"

import numpy as np
from scipy.linalg import eigh

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/submission_20261002/local_projection"
sys.path.insert(0, str(ROOT / "scripts/autoresearch_v5"))
sys.path.insert(0, str(ROOT / "scripts/autoresearch_v3"))
from static_krylov_ed_reference import build_sector_hamiltonian
from project_doublet import site_operator

PROTOCOL = {
    "model": "two complete pentamers, J2-J1-J1-J2-J3-J2-J1-J1-J2, J1=1",
    "L": 10, "boundary": "OBC", "alphas": [0.5, -0.5],
    "g_values": [0.0025, 0.005, 0.01, 0.02, 0.04],
    "g_definition": "beta / isolated-cell multiplet gap",
    "outside_domain_beta": 0.5, "q_points": 41,
    "normalization": "Oq=sum_j exp(i*q*j) Sz_j / sqrt(10), connected",
    "prediction": "Wlow=F(q)*s*(s+1)*(1-cos(5q))/15, gap=beta*c1*c5",
    "low_band": "0 < excitation energy < Delta_local/2; boundary fixed before solve",
    "weak_domain_g_max": 0.01,
    "tolerances": {"algebra": 1e-10, "ed_residual": 1e-11,
                   "sum_rule": 1e-11, "inversion_relative": 1e-10,
                   "weak_gap_relative": 0.02, "weak_weight_relative": 0.03},
    "resource_limit": "1 CPU; L<=10; complete run <=300 seconds",
    "claims_excluded": ["bulk limit", "unique high-energy branch assignment", "L40 convergence"],
}


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def local_projection(alpha, q):
    local = {
        "x": np.array([[0, 1], [1, 0]], dtype=complex) / 2,
        "y": np.array([[0, -1j], [1j, 0]], dtype=complex) / 2,
        "z": np.diag([0.5, -0.5]),
    }
    spins = {axis: [site_operator(matrix, site) for site in range(5)]
             for axis, matrix in local.items()}
    h = sum(coupling * spins[axis][i] @ spins[axis][i + 1]
            for i, coupling in enumerate((alpha, 1, 1, alpha)) for axis in spins)
    energy, vectors = eigh(h)
    count = int(np.count_nonzero(abs(energy - energy[0]) < 1e-10))
    p = vectors[:, :count]
    t = {axis: p.conj().T @ sum(ops) @ p for axis, ops in spins.items()}
    values, rotation = eigh(t["z"])
    s = float(values[-1])
    highest = p @ rotation[:, -1]
    c = np.array([np.real(highest.conj() @ op @ highest) / s for op in spins["z"]])
    residual = max(np.linalg.norm(p.conj().T @ op @ p - c[i] * t[axis])
                   for axis, ops in spins.items() for i, op in enumerate(ops))
    shape = abs(np.exp(1j * np.outer(q, np.arange(1, 6))) @ c) ** 2
    prediction = shape * s * (s + 1) * (1 - np.cos(5 * q)) / 15
    identity = np.eye(count)
    projected_link = sum(np.kron(p.conj().T @ ops[4] @ p, p.conj().T @ ops[0] @ p)
                         for ops in spins.values())
    effective_link = c[0] * c[-1] * sum(np.kron(op, op) for op in t.values())
    _, states = eigh(effective_link)
    ground = states[:, 0]
    projected_weight = []
    for momentum in q:
        f = np.exp(1j * momentum * np.arange(1, 6)) @ c
        source_operator = f / np.sqrt(10) * (
            np.kron(t["z"], identity) + np.exp(5j * momentum) * np.kron(identity, t["z"]))
        source = source_operator @ ground
        source -= ground * np.vdot(ground, source)
        projected_weight.append(float(np.vdot(source, source).real))
    checks = {
        "local_projection_error": float(residual),
        "endpoint_reflection_error": float(abs(c[0] - c[-1])),
        "coefficient_sum_error": float(abs(c.sum() - 1)),
        "link_projection_error": float(np.linalg.norm(projected_link - effective_link)),
        "absolute_weight_formula_error": float(np.max(abs(np.array(projected_weight) - prediction))),
        "spin_casimir_error": float(np.linalg.norm(sum(op @ op for op in t.values()) - s * (s + 1) * identity)),
    }
    record = {"alpha": alpha, "s": s, "cell_energy": float(energy[0]),
              "local_gap": float(energy[count] - energy[0]), "c": c.tolist(),
              "jeff_over_beta": float(c[0] * c[-1]), "checks": checks}
    return record, shape, prediction


def full_chain(alpha, beta, cell, prediction, q):
    basis, h = build_sector_hamiltonian(alpha, beta, 5)
    basis1, h1 = build_sector_hamiltonian(alpha, beta, 6)
    assert len(basis) == 252 and len(basis1) == 210
    energy, vectors = eigh(h)
    e1, v1 = eigh(h1, subset_by_index=(0, 0))
    ground = vectors[:, 0]
    sz = np.array([[(state >> site & 1) - 0.5 for site in range(10)] for state in basis])
    source = (sz @ np.exp(1j * np.outer(np.arange(1, 11), q))) * ground[:, None] / np.sqrt(10)
    source -= ground[:, None] * (ground @ source)[None, :]
    weights = abs(vectors.T @ source) ** 2
    gaps = energy - energy[0]
    low = (gaps > 1e-10) & (gaps < cell["local_gap"] / 2)
    low_weight = weights[low].sum(axis=0)
    total = weights.sum(axis=0)
    expected_count = int(round(2 * cell["s"]))
    static = np.sum(abs(source) ** 2, axis=0)
    residual = max(np.linalg.norm(h @ vectors - vectors * energy, axis=0).max(),
                   np.linalg.norm(h1 @ v1[:, 0] - e1[0] * v1[:, 0]))
    gap = float(e1[0] - energy[0])
    gap_prediction = beta * cell["jeff_over_beta"]
    row = {
        "alpha": alpha, "beta": beta, "g": beta / cell["local_gap"],
        "local_spin": cell["s"], "local_gap": cell["local_gap"],
        "gap_ed": gap, "gap_prediction": gap_prediction,
        "gap_relative_error": abs(gap / gap_prediction - 1),
        "low_band_weight_relative_error": float(np.linalg.norm(low_weight - prediction) / np.linalg.norm(prediction)),
        "low_band_sz0_levels": int(low.sum()), "expected_sz0_levels": expected_count,
        "band_separated": bool(low.sum() == expected_count),
        "ed_max_residual": float(residual),
        "spectral_sum_rule_error": float(np.max(abs(total - static))),
        "local_moment_sum_rule_error": float(abs(total[np.arange(0, 40, 4)].mean() - 0.25)),
        "inversion_relative_error": float(np.linalg.norm(low_weight - low_weight[::-1]) / max(np.linalg.norm(low_weight), 1e-30)),
    }
    numerical = (row["ed_max_residual"] <= 1e-11 and row["spectral_sum_rule_error"] <= 1e-11
                 and row["local_moment_sum_rule_error"] <= 1e-11 and row["inversion_relative_error"] <= 1e-10)
    in_domain = row["g"] <= 0.01 + 1e-12
    row["numerical_pass"] = bool(numerical)
    row["weak_domain"] = bool(in_domain)
    row["weak_prediction_pass"] = bool(numerical and row["band_separated"] and
                                       row["gap_relative_error"] <= 0.02 and
                                       row["low_band_weight_relative_error"] <= 0.03) if in_domain else None
    qrows = [{"alpha": alpha, "beta": beta, "g": row["g"], "q_over_pi": float(momentum / np.pi),
              "low_weight_ed": float(low_weight[i]), "low_weight_prediction": float(prediction[i]),
              "total_weight_ed": float(total[i])} for i, momentum in enumerate(q)]
    return row, qrows


def main():
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=False)
    write_json(OUT / "protocol.json", PROTOCOL)
    q = np.linspace(0, 2 * np.pi, 41)
    cells, rows, qrows, folded = [], [], [], []
    for alpha in PROTOCOL["alphas"]:
        cell, shape, prediction = local_projection(alpha, q)
        cells.append(cell)
        for i in (4, 12, 20, 28, 36):
            folded.append({"alpha": alpha, "s": cell["s"], "q_over_pi": float(q[i] / np.pi),
                           "shape_factor": float(shape[i]), "two_cell_low_weight": float(prediction[i])})
        for beta in [g * cell["local_gap"] for g in PROTOCOL["g_values"]] + [0.5]:
            if time.perf_counter() - started > 280:
                raise TimeoutError("达到预设时间边界")
            row, qdata = full_chain(alpha, beta, cell, prediction, q)
            rows.append(row)
            qrows.extend(qdata)
            print(json.dumps(row), flush=True)
    algebra_pass = all(max(cell["checks"].values()) <= 1e-10 for cell in cells)
    summary = {
        "scope": "two-cell weak-coupling absolute low-energy spectral-weight prediction",
        "cells": cells, "runs": len(rows), "cpu_threads": 1,
        "elapsed_seconds": time.perf_counter() - started,
        "algebra_pass": algebra_pass,
        "all_numerical_checks_pass": all(row["numerical_pass"] for row in rows),
        "all_predefined_weak_predictions_pass": all(row["weak_prediction_pass"] for row in rows if row["weak_domain"]),
        "outside_domain_results_are_diagnostic_only": True,
        "protocol": PROTOCOL,
    }
    write_csv(OUT / "coupling_checks.csv", rows)
    write_csv(OUT / "q_resolved_weights.csv", qrows)
    write_csv(OUT / "folded_prediction.csv", folded)
    write_json(OUT / "summary.json", summary)
    dependencies = [Path(__file__), ROOT / "scripts/autoresearch_v5/static_krylov_ed_reference.py",
                    ROOT / "scripts/autoresearch_v3/project_doublet.py"]
    hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in dependencies + sorted(OUT.iterdir()) if path.is_file()}
    write_json(OUT / "sha256.json", hashes)
    print(json.dumps(summary, indent=2), flush=True)
    if not (algebra_pass and summary["all_numerical_checks_pass"] and summary["all_predefined_weak_predictions_pass"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
