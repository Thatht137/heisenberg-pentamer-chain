"""推导暗点的一阶有效探针，并检查多胞响应是否仅为幅度重标。"""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"

import numpy as np
from scipy.linalg import eigh
from scipy.sparse import csr_matrix, eye, kron

import local_projection_checks as reference

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/novelty_20261004/dark_operator"
ALPHA = -(2 + np.sqrt(7)) / 6


def local_data():
    half = {"x": np.array([[0, 1], [1, 0]]) / 2,
            "y": np.array([[0, -1j], [1j, 0]]) / 2,
            "z": np.diag([0.5, -0.5])}
    spins = {a: [reference.site_operator(op, i) for i in range(5)] for a, op in half.items()}
    h = sum(c * spins[a][i] @ spins[a][i + 1]
            for i, c in enumerate((ALPHA, 1, 1, ALPHA)) for a in half)
    e, u = eigh(h)
    p = u[:, :4]
    _, rotation = eigh(p.conj().T @ sum(spins["z"]) @ p)
    highest = p @ rotation[:, -1]
    lower = sum(spins["x"]) - 1j * sum(spins["y"])
    states = [highest]
    for m in (1.5, 0.5, -0.5):
        states.append(lower @ states[-1] / np.sqrt(3.75 - m * (m - 1)))
    p = np.column_stack(states)
    u = np.column_stack((p, u[:, 4:]))
    transformed = {a: [u.conj().T @ op @ u for op in ops] for a, ops in spins.items()}
    t = {a: sum(ops)[:4, :4] for a, ops in transformed.items()}
    b = sum((-1) ** i * op for i, op in enumerate(transformed["z"]))
    c1 = float(transformed["z"][0][0, 0].real / 1.5)
    return e, t, transformed, b, c1


def effective_probe():
    e, t, ops, b, c1 = local_data()
    unit = np.eye(32)[:, :4]
    v = sum(np.kron(ops[a][4][:, :4], ops[a][0][:, :4]) for a in t)
    left = np.kron(b[:, :4], unit)
    right = np.kron(unit, b[:, :4])
    gaps = (e[:, None] + e[None, :] - 2 * e[0]).ravel()
    r = np.zeros_like(gaps)
    high = gaps > 1e-10
    r[high] = 1 / gaps[high]
    rv = r[:, None] * v
    kl = -left.conj().T @ rv - rv.conj().T @ left
    kr = -right.conj().T @ rv - rv.conj().T @ right
    quadrupole = {a: (t["z"] @ t[a] + t[a] @ t["z"]) / 2
                  - (1.25 * np.eye(4) if a == "z" else 0) for a in t}
    linear = np.kron(np.eye(4), t["z"])
    composite = sum(np.kron(quadrupole[a], t[a]) for a in t)
    coeff, *_ = np.linalg.lstsq(np.column_stack([linear.ravel(), composite.ravel()]), kl.ravel(), rcond=None)
    fit = coeff[0] * linear + coeff[1] * composite
    swap = np.eye(16).reshape(4, 4, 16).transpose(1, 0, 2).reshape(16, 16)
    diagnostics = {
        "alpha_exact": float(ALPHA), "alpha_formula": "-(2+sqrt(7))/6",
        "local_gap": float(e[4] - e[0]), "jeff_over_beta": c1**2,
        "P_B_P_norm": float(np.linalg.norm(b[:4, :4])),
        "linear_coefficient": float(coeff[0].real),
        "quadrupole_coefficient": float(coeff[1].real),
        "fit_relative_error": float(np.linalg.norm(kl-fit)/np.linalg.norm(kl)),
        "left_right_reflection_error": float(np.linalg.norm(kr-swap@kl@swap)),
        "hermiticity_error": float(np.linalg.norm(kl-kl.conj().T)),
    }
    assert diagnostics["P_B_P_norm"] < 1e-11
    assert diagnostics["fit_relative_error"] < 1e-10
    assert diagnostics["left_right_reflection_error"] < 1e-10
    return t, quadrupole, c1, coeff.real, kl, kr, diagnostics


def embed(op, site, count):
    return kron(kron(eye(4**site, format="csr"), csr_matrix(op), format="csr"),
                eye(4**(count-site-1), format="csr"), format="csr")


def chain(count, periodic, t, quadrupole, c1, coefficients):
    a, b = coefficients
    spins = {axis: [embed(op, site, count) for site in range(count)] for axis, op in t.items()}
    quads = {axis: [embed(op, site, count) for site in range(count)] for axis, op in quadrupole.items()}
    dim = 4**count
    h = csr_matrix((dim, dim), dtype=complex)
    k = h.copy()
    d = sum((-1)**i * spins["z"][i] for i in range(count))
    bonds = [(i, i+1) for i in range(count-1)]
    if periodic:
        bonds.append((count-1, 0))
    for i, j in bonds:
        h += c1**2 * sum(spins[axis][i] @ spins[axis][j] for axis in t)
        k += a * ((-1)**i * spins["z"][j] + (-1)**j * spins["z"][i])
        k += b * sum((-1)**i * quads[axis][i] @ spins[axis][j]
                     + (-1)**j * spins[axis][i] @ quads[axis][j] for axis in t)
    digits = np.arange(dim)
    magnetization = sum(1.5 - (digits // 4**i) % 4 for i in range(count))
    sector = np.flatnonzero(magnetization == 0)
    h, k, d = [op[sector][:, sector].toarray() for op in (h, k, d)]
    e, v = eigh(h)
    ground = v[:, 0]
    source = k @ ground / np.sqrt(5*count)
    bright = d @ ground / np.sqrt(5*count)
    source -= ground * np.vdot(ground, source)
    bright -= ground * np.vdot(ground, bright)
    coefficient = np.vdot(bright, source) / np.vdot(bright, bright)
    residual = source - coefficient * bright
    weights = abs(v.conj().T @ source)**2
    linear_weights = abs(v.conj().T @ bright)**2
    perp_weights = abs(v.conj().T @ residual)**2
    row = {"cells": count, "boundary": "PBC" if periodic else "OBC", "sector_dim": len(sector),
           "W_dark_over_beta2": float(np.vdot(source, source).real),
           "W_linear": float(np.vdot(bright, bright).real),
           "best_linear_amplitude": float(coefficient.real),
           "unremovable_fraction": float(np.vdot(residual, residual).real/np.vdot(source, source).real),
           "residual_norm": float(np.max(np.linalg.norm(h@v-v*e, axis=0))),
           "source_sum_rule": float(abs(weights.sum()-np.vdot(source,source).real))}
    assert row["residual_norm"] < 1e-10 and row["source_sum_rule"] < 1e-11
    records = [{"cells": count, "boundary": row["boundary"], "level": i,
                "omega_over_beta": float(en-e[0]), "dark_weight_over_beta2": float(weights[i]),
                "linear_weight": float(linear_weights[i]), "perpendicular_weight": float(perp_weights[i])}
               for i, en in enumerate(e)]
    return row, records


def main():
    start = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=False)
    reference.write_json(OUT / "protocol.json", {
        "model": "unchanged pentamer chain", "alpha": float(ALPHA),
        "effective_cells": [2, 4, 6], "boundaries": "OBC all; PBC N=4,6",
        "operator": "-P O R V P - P V R O P, R=Q/(H0-E0)",
        "purpose": "test scalar renormalization versus composite probe, not bulk extrapolation",
        "threads": 1, "wall_limit_seconds": 300,
        "source_residual_gate": 1e-10, "exploratory": True,
    })
    t, quad, c1, coefficients, kl, kr, diagnostics = effective_probe()
    rows, records = [], []
    for n, periodic in ((2, False), (4, False), (6, False), (4, True), (6, True)):
        if time.perf_counter()-start > 250:
            raise TimeoutError("达到有效算符检验时间边界")
        row, spectra = chain(n, periodic, t, quad, c1, coefficients)
        rows.append(row)
        records.extend(spectra)
        print(row, flush=True)
    reference.write_csv(OUT / "effective_chains.csv", rows)
    reference.write_csv(OUT / "effective_spectra.csv", records)
    prior = ROOT / "results/novelty_20261004/interference_zero_probe/q_resolved_weights.csv"
    import csv
    with prior.open(newline="", encoding="utf-8") as handle:
        exact = [r for r in csv.DictReader(handle) if float(r["offset"]) == 0 and abs(float(r["q_over_pi"])-1)<1e-10]
    checks = [{"g": float(r["g"]), "ed_W_over_beta2": float(r["low_weight_ed"])/float(r["beta"])**2,
               "relative_error": abs(float(r["low_weight_ed"])/(float(r["beta"])**2*rows[0]["W_dark_over_beta2"])-1)} for r in exact]
    assert checks[0]["relative_error"] < 0.02
    reference.write_json(OUT / "summary.json", {"local": diagnostics, "two_cell_checks": checks,
                         "elapsed_seconds": time.perf_counter()-start,
                         "microscopic_multicell_validation": False, "publication_novelty_established": False})
    reference.write_json(OUT / "sha256.json", {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__), Path(reference.__file__).resolve(), prior] + sorted(OUT.iterdir()) if p.is_file()})
    print(diagnostics, flush=True)
    print(checks, flush=True)


if __name__ == "__main__":
    main()
