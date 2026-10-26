"""以20自旋微观ED验证暗点有效探针，保留完整低能带。"""

from __future__ import annotations

import hashlib
import itertools
import os
import sys
import time
from pathlib import Path

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"

import numpy as np
from scipy.linalg import eigh
from scipy.sparse.linalg import LinearOperator, eigsh

import dark_operator_expansion as dark
import local_projection_checks as reference

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/autoresearch_v5"))
from analyze_negative_phase_independent_observables import sector_matrix

OUT = ROOT / "results/novelty_20261004/microscopic_four_cells"


def bonds(n, alpha, beta):
    return [(i, i+1, (alpha, 1.0, 1.0, alpha, beta)[i % 5]) for i in range(n-1)]


def sources(states, vectors, n):
    states = np.asarray(states, dtype=np.int64)
    sz = np.column_stack([((states >> i) & 1)-0.5 for i in range(n)])
    q = np.array([np.pi, 0.6*np.pi])
    op = sz @ np.exp(1j*np.outer(np.arange(n), q)) / np.sqrt(n)
    result = op*vectors[:, 0, None]
    result -= vectors[:, 0, None]*(vectors[:, 0]@result)[None, :]
    return result


def main():
    started = time.perf_counter()
    deadline = started + 1200
    OUT.mkdir(parents=True, exist_ok=False)
    reference.write_json(OUT / "protocol.json", {
        "L": 20, "cells": 4, "boundary": "OBC", "Sz": 0,
        "sector_dim": 184756, "eigenpairs": 45, "alpha": float(dark.ALPHA),
        "g_values": [0.01, 0.02], "low_band": "0<omega<Delta_local/2",
        "expected_band_states_including_ground": 44,
        "ed_residual_max": 1e-9, "operator_weight_relative_error_max": 0.05,
        "threads": 1, "wall_limit_seconds": 1200,
        "scope": "finite microscopic 4-cell cross-check, not bulk result",
    })
    cell, _, _ = reference.local_projection(dark.ALPHA, np.linspace(0, 2*np.pi, 41))
    small = sector_matrix(10, 5, bonds(10, dark.ALPHA, 0.01)).toarray()
    _, oracle = reference.build_sector_hamiltonian(dark.ALPHA, 0.01, 5)
    assert np.max(abs(small-oracle)) < 1e-14
    t, quad, c1, coeff, *_ = dark.effective_probe()
    prediction, predicted_spectra = dark.chain(4, False, t, quad, c1, coeff)
    reference.write_csv(OUT / "predicted_spectra.csv", predicted_spectra)
    h0 = sector_matrix(20, 10, bonds(20, dark.ALPHA, 0))
    hb = sector_matrix(20, 10, [(4, 5, 1.0), (9, 10, 1.0), (14, 15, 1.0)])
    states = [sum(1 << i for i in inds) for inds in itertools.combinations(range(20), 10)]
    assert len(states) == 184756
    rows, records = [], []
    rng = np.random.default_rng(20261004)
    initial = rng.normal(size=len(states))
    for g in (0.01, 0.02):
        beta = g*cell["local_gap"]
        h = h0 + beta*hb
        def matvec(x):
            if time.perf_counter() > deadline:
                raise TimeoutError("达到20自旋独立验证时间边界")
            return h@x
        print(f"START g={g} dimension={len(states)}", flush=True)
        operator = LinearOperator(h.shape, matvec=matvec, dtype=np.float64)
        e, v = eigsh(operator, k=45, which="SA", tol=1e-12, ncv=110, maxiter=5000, v0=initial)
        order = np.argsort(e)
        e, v = e[order], v[:, order]
        initial = v[:, 0] + 0.05*rng.normal(size=len(states))/np.sqrt(len(states))
        errors = np.linalg.norm(h@v-v*e, axis=0)
        gaps = e-e[0]
        low = (gaps > 1e-9) & (gaps < cell["local_gap"]/2)
        source = sources(states, v, 20)
        weights = abs(v.T@source)**2
        dark_weight = float(weights[low, 0].sum())
        row = {"g": g, "beta": beta, "e0": float(e[0]), "low_states": int(low.sum()),
               "gap": float(gaps[1]), "band_top": float(gaps[43]), "next_state": float(gaps[44]),
               "max_residual": float(errors.max()), "W_pi": dark_weight,
               "W_pi_over_beta2": dark_weight/beta**2,
               "predicted_W_pi_over_beta2": prediction["W_dark_over_beta2"],
               "relative_error": abs(dark_weight/(beta**2*prediction["W_dark_over_beta2"])-1),
               "W_06pi": float(weights[low, 1].sum()),
               "orthogonality_error": float(np.linalg.norm(v.T@v-np.eye(45))),
               "elapsed_seconds": time.perf_counter()-started}
        row["pass"] = bool(row["low_states"] == 43 and row["max_residual"] < 1e-9
                           and row["orthogonality_error"] < 1e-8 and row["relative_error"] < 0.05)
        rows.append(row)
        records.extend({"g": g, "level": i, "omega": float(gaps[i]),
                        "W_pi": float(weights[i, 0]), "W_06pi": float(weights[i, 1]),
                        "residual": float(errors[i])} for i in range(45))
        reference.write_csv(OUT / "comparisons.csv", rows)
        reference.write_csv(OUT / "spectral_lines.csv", records)
        print(row, flush=True)
    reference.write_json(OUT / "summary.json", {"all_pass": all(r["pass"] for r in rows),
                         "cases": rows, "elapsed_seconds": time.perf_counter()-started,
                         "full_frequency_sum_rule_tested": False, "bulk_claim": False})
    reference.write_json(OUT / "sha256.json", {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__), Path(dark.__file__).resolve(), Path(reference.__file__).resolve(),
                  ROOT / "scripts/autoresearch_v5/analyze_negative_phase_independent_observables.py"]
        + sorted(OUT.iterdir()) if p.is_file()})
    if not all(r["pass"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
