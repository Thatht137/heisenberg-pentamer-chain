"""保留首轮失败，以更弱耦合验证四胞残余信号。"""

from __future__ import annotations

import hashlib
import itertools
import time
from pathlib import Path

import validate_dark_multicell as original
import numpy as np
from scipy.sparse.linalg import LinearOperator, eigsh

dark, reference = original.dark, original.reference
ROOT = original.ROOT
OUT = ROOT / "results/novelty_20261004/microscopic_retuning_v2"


def amplitude(alpha):
    cell, _, _ = reference.local_projection(alpha, np.linspace(0, 2*np.pi, 41))
    return np.dot(cell["c"], [1, -1, 1, -1, 1])


def main():
    start = time.perf_counter()
    deadline = start + 1200
    OUT.mkdir(parents=True, exist_ok=False)
    t, quad, c1, coeff, *_ = dark.effective_probe()
    pred, _ = dark.chain(4, False, t, quad, c1, coeff)
    derivative = (amplitude(dark.ALPHA+1e-5)-amplitude(dark.ALPHA-1e-5))/2e-5
    derivative_check = (amplitude(dark.ALPHA+5e-6)-amplitude(dark.ALPHA-5e-6))/1e-5
    assert abs(derivative-derivative_check) < 1e-8
    kappa = -pred["best_linear_amplitude"]/derivative
    cell, _, _ = reference.local_projection(dark.ALPHA, np.linspace(0, 2*np.pi, 41))
    cases = [(g, mode) for g in (0.0025, 0.005) for mode in ("fixed", "retuned")]
    reference.write_json(OUT / "protocol.json", {
        "reason": "v1 at g=.01,.02 failed the unchanged 5% leading-order gate; test convergence, retain failures",
        "L": 20, "cells": 4, "boundary": "OBC", "Sz": 0, "eigenpairs": 45,
        "cases": cases, "g_definition": "beta/Delta(alpha_star), fixed reference gap",
        "alpha_fixed": float(dark.ALPHA), "alpha_retuned": "alpha_star+kappa*beta",
        "amplitude_derivative": float(derivative), "kappa": float(kappa),
        "predicted_fixed_coefficient": pred["W_dark_over_beta2"],
        "predicted_retuned_coefficient": pred["W_dark_over_beta2"]*pred["unremovable_fraction"],
        "low_band": "0<omega<Delta(alpha_star)/2", "relative_weight_gate": 0.05,
        "residual_gate": 1e-9, "orthogonality_gate": 1e-8,
        "threads": 1, "wall_limit_seconds": 1200, "bulk_claim": False,
    })
    h0 = original.sector_matrix(20, 10, original.bonds(20, dark.ALPHA, 0))
    hb = original.sector_matrix(20, 10, [(i, i+1, 1.0) for i in (4, 9, 14)])
    ha = original.sector_matrix(20, 10, [(i, i+1, 1.0) for i in range(19) if i % 5 in (0, 3)])
    states = [sum(1 << i for i in inds) for inds in itertools.combinations(range(20), 10)]
    rows, lines = [], []
    rng = np.random.default_rng(20261004)
    initial = rng.normal(size=len(states))
    for g, mode in cases:
        beta = g*cell["local_gap"]
        shift = kappa*beta if mode == "retuned" else 0.0
        h = h0 + beta*hb + shift*ha
        def matvec(x):
            if time.perf_counter() > deadline:
                raise TimeoutError("达到四胞重调验证时间边界")
            return h@x
        print(f"START g={g} mode={mode}", flush=True)
        e, v = eigsh(LinearOperator(h.shape, matvec=matvec, dtype=np.float64),
                     k=45, which="SA", tol=1e-12, ncv=110, maxiter=5000, v0=initial)
        order = np.argsort(e)
        e, v = e[order], v[:, order]
        initial = v[:, 0] + 0.05*rng.normal(size=len(states))/np.sqrt(len(states))
        errors = np.linalg.norm(h@v-v*e, axis=0)
        gaps = e-e[0]
        low = (gaps > 1e-9) & (gaps < cell["local_gap"]/2)
        weights = abs(v.T@original.sources(states, v, 20))**2
        observed = float(weights[low, 0].sum())/beta**2
        predicted = pred["W_dark_over_beta2"]*(pred["unremovable_fraction"] if mode == "retuned" else 1)
        row = {"g": g, "mode": mode, "alpha": float(dark.ALPHA+shift), "beta": beta,
               "W_pi_over_beta2": observed, "prediction": predicted,
               "relative_error": abs(observed/predicted-1), "low_states": int(low.sum()),
               "gap": float(gaps[1]), "next_state": float(gaps[44]),
               "max_residual": float(errors.max()),
               "orthogonality_error": float(np.linalg.norm(v.T@v-np.eye(45))),
               "elapsed_seconds": time.perf_counter()-start}
        row["pass"] = bool(row["relative_error"] < .05 and row["low_states"] == 43
                           and row["max_residual"] < 1e-9 and row["orthogonality_error"] < 1e-8)
        rows.append(row)
        lines.extend({"g": g, "mode": mode, "level": i, "omega": float(gaps[i]),
                      "W_pi": float(weights[i, 0]), "W_06pi": float(weights[i, 1]),
                      "residual": float(errors[i])} for i in range(45))
        reference.write_csv(OUT / "comparisons.csv", rows)
        reference.write_csv(OUT / "spectral_lines.csv", lines)
        print(row, flush=True)
    reference.write_json(OUT / "summary.json", {"all_pass": all(r["pass"] for r in rows),
                         "cases": rows, "bulk_claim": False, "elapsed_seconds": time.perf_counter()-start})
    reference.write_json(OUT / "sha256.json", {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__), Path(original.__file__), Path(dark.__file__), Path(reference.__file__)]
        + sorted(OUT.iterdir()) if p.is_file()})
    if not all(r["pass"] for r in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
