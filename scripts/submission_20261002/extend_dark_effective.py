"""在固定磁化扇区扩大有效链，检验边界与有限尺寸影响。"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import dark_operator_expansion as dark
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import LinearOperator, eigsh

reference, ROOT = dark.reference, dark.ROOT
OUT = ROOT / "results/novelty_20261004/effective_size_extension"


def sector(count):
    full = np.arange(4**count, dtype=np.int64)
    powers = 4**np.arange(count-1, -1, -1)
    total = np.zeros(len(full), dtype=np.int8)
    for p in powers:
        total += (full // p) % 4
    states = full[total == 3*count//2]
    lookup = np.full(len(full), -1, dtype=np.int32)
    lookup[states] = np.arange(len(states))
    digits = (states[:, None] // powers[None, :]) % 4
    return states, lookup, digits, powers


def bond_matrix(op, i, j, data):
    states, lookup, digits, powers = data
    rows, cols, vals = [], [], []
    local = 4*digits[:, i]+digits[:, j]
    for col in range(16):
        selected = np.flatnonzero(local == col)
        for row in np.flatnonzero(abs(op[:, col]) > 1e-13):
            target = states[selected]+(row//4-col//4)*powers[i]+(row%4-col%4)*powers[j]
            target_index = lookup[target]
            assert np.all(target_index >= 0)
            rows.append(target_index)
            cols.append(selected)
            vals.append(np.full(len(selected), op[row, col].real))
    return coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                      shape=(len(states), len(states))).tocsr()


def run(count, periodic, t, c1, kl, kr, deadline):
    data = sector(count)
    pairs = [(i, i+1) for i in range(count-1)] + ([(count-1, 0)] if periodic else [])
    link = c1**2 * sum(np.kron(op, op) for op in t.values())
    h = sum(bond_matrix(link, i, j, data) for i, j in pairs)
    k = sum((-1)**i*bond_matrix(kl-kr, i, j, data) for i, j in pairs)/np.sqrt(5*count)
    assert np.max(abs((h-h.T).data), initial=0) < 1e-11
    assert np.max(abs((k-k.T).data), initial=0) < 1e-11
    def matvec(x):
        if time.perf_counter() > deadline:
            raise TimeoutError("达到有效链尺寸检验时间边界")
        return h@x
    e, v = eigsh(LinearOperator(h.shape, matvec=matvec, dtype=np.float64),
                 k=2, which="SA", tol=1e-12, ncv=30,
                 v0=np.random.default_rng(20261004).normal(size=h.shape[0]))
    order = np.argsort(e)
    e, v = e[order], v[:, order]
    ground = v[:, 0]
    source = k@ground
    d = np.sum((1.5-data[2])*((-1.)**np.arange(count))[None, :], axis=1)/np.sqrt(5*count)
    bright = d*ground
    source -= ground*np.dot(ground, source)
    bright -= ground*np.dot(ground, bright)
    coefficient = np.dot(bright, source)/np.dot(bright, bright)
    residual = source-coefficient*bright
    result = {"cells": count, "boundary": "PBC" if periodic else "OBC",
              "sector_dim": len(ground), "energy_over_beta": float(e[0]),
              "gap_over_beta": float(e[1]-e[0]), "W_dark_over_beta2": float(source@source),
              "W_linear": float(bright@bright), "best_linear_amplitude": float(coefficient),
              "unremovable_fraction": float(residual@residual/(source@source)),
              "retuned_W_over_beta2": float(residual@residual),
              "residual_norm": float(np.max(np.linalg.norm(h@v-v*e, axis=0)))}
    assert result["residual_norm"] < 1e-10
    return result


def main():
    start = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=False)
    reference.write_json(OUT / "protocol.json", {
        "effective_spin": 1.5, "cells": [4, 6, 8, 10], "boundaries": ["OBC", "PBC"],
        "cross_check": "N4,N6 against full tensor-product embedding, before larger chains",
        "alpha": float(dark.ALPHA), "threads": 1, "wall_limit_seconds": 600,
        "cross_check_tolerance": 1e-9, "eigen_residual_gate": 1e-10,
        "microscopic_calculation": False, "thermodynamic_extrapolation": False,
    })
    t, quad, c1, coeff, kl, kr, _ = dark.effective_probe()
    rows = []
    for count in (4, 6, 8, 10):
        for periodic in (False, True):
            row = run(count, periodic, t, c1, kl, kr, start+600)
            if count <= 6:
                old, _ = dark.chain(count, periodic, t, quad, c1, coeff)
                row["small_cross_check_error"] = max(abs(row[key]-old[key]) for key in
                    ("W_dark_over_beta2", "W_linear", "best_linear_amplitude", "unremovable_fraction"))
                assert row["small_cross_check_error"] < 1e-9
            else:
                row["small_cross_check_error"] = None
            rows.append(row)
            reference.write_csv(OUT / "size_checks.csv", rows)
            print(row, flush=True)
    reference.write_json(OUT / "summary.json", {"all_numerical_checks_pass": True,
                         "elapsed_seconds": time.perf_counter()-start, "cases": rows,
                         "bulk_extrapolation": False, "microscopic_L50_validated": False})
    reference.write_json(OUT / "sha256.json", {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__), Path(dark.__file__), Path(reference.__file__)]
        + sorted(OUT.iterdir()) if p.is_file()})


if __name__ == "__main__":
    main()
