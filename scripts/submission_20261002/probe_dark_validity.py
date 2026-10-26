"""检查暗点逐线收敛、独立重复和较强耦合的失准。"""

from __future__ import annotations

import hashlib
import itertools
import time
from pathlib import Path

import validate_dark_retuning as previous
import numpy as np
from scipy.sparse.linalg import LinearOperator, eigsh

original, dark, reference = previous.original, previous.dark, previous.reference
ROOT = previous.ROOT
OUT = ROOT / "results/novelty_20261004/microscopic_validity_v3"
CASES = [(0.00125, 20261005, 140), (0.000625, 20261005, 140),
         (0.000625, 987654, 180), (0.02, 20261005, 140), (0.04, 20261005, 140)]


def main():
    start = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=False)
    t, quad, c1, coeff, *_ = dark.effective_probe()
    pred, predicted_lines = dark.chain(4, False, t, quad, c1, coeff)
    dx = 5e-6
    derivative = (previous.amplitude(dark.ALPHA+dx)-previous.amplitude(dark.ALPHA-dx))/(2*dx)
    kappa = -pred["best_linear_amplitude"]/derivative
    cell, _, _ = reference.local_projection(dark.ALPHA, np.linspace(0, 2*np.pi, 41))
    target = np.array([r["perpendicular_weight"] for r in predicted_lines])
    target_energy = np.array([r["omega_over_beta"] for r in predicted_lines])
    reference.write_json(OUT / "protocol.json", {
        "L": 20, "boundary": "OBC", "cases_g_seed_ncv": CASES, "eigenpairs": 45,
        "alpha": "alpha_star+kappa*beta", "kappa": float(kappa),
        "g_definition": "beta/Delta(alpha_star)", "low_band": "0<omega<Delta(alpha_star)/2",
        "weak_line_error_gates": {"0.00125": 0.03, "0.000625": 0.02},
        "integrated_error_weak_gate": .02, "repeat_line_vector_relative_gate": .001,
        "numeric_eigen_residual_gate": 1e-9, "low_levels_including_ground": 44,
        "strong_g_points_are_diagnostic_only": True, "eigensolver_tolerance": 1e-13,
        "threads": 1, "wall_limit_seconds": 1200, "bulk_claim": False,
        "purpose": "prospective linewise convergence and independent random-start repeat",
    })
    h0 = original.sector_matrix(20, 10, original.bonds(20, dark.ALPHA, 0))
    hb = original.sector_matrix(20, 10, [(i, i+1, 1.) for i in (4, 9, 14)])
    ha = original.sector_matrix(20, 10, [(i, i+1, 1.) for i in range(19) if i % 5 in (0, 3)])
    states = [sum(1 << i for i in inds) for inds in itertools.combinations(range(20), 10)]
    rows, lines, repeats = [], [], []
    for g, seed, ncv in CASES:
        beta = g*cell["local_gap"]
        h = h0+beta*(hb+kappa*ha)
        def matvec(x):
            if time.perf_counter()-start > 1200:
                raise TimeoutError("达到微观收敛检验时间边界")
            return h@x
        print(f"START g={g} seed={seed} ncv={ncv}", flush=True)
        e, v = eigsh(LinearOperator(h.shape, matvec=matvec, dtype=np.float64),
                     k=45, which="SA", ncv=ncv, tol=1e-13, maxiter=5000,
                     v0=np.random.default_rng(seed).normal(size=len(states)))
        order = np.argsort(e)
        e, v = e[order], v[:, order]
        errors = np.linalg.norm(h@v-v*e, axis=0)
        gaps = e-e[0]
        low = (gaps > 1e-9) & (gaps < cell["local_gap"]/2)
        weights = abs(v.T@original.sources(states, v, 20))**2
        observed = weights[:44, 0]/beta**2
        relative_lines = float(np.linalg.norm(observed-target)/np.linalg.norm(target))
        relative_total = float(abs(observed.sum()/target.sum()-1))
        numeric = bool(low.sum() == 43 and errors.max() < 1e-9
                       and np.linalg.norm(v.T@v-np.eye(45)) < 1e-8)
        weak_gate = {0.00125: .03, 0.000625: .02}.get(g)
        row = {"g": g, "seed": seed, "ncv": ncv, "alpha": float(dark.ALPHA+kappa*beta),
               "beta": beta, "W_pi_over_beta2": float(observed.sum()),
               "line_vector_relative_error": relative_lines, "weight_relative_error": relative_total,
               "max_energy_error_over_beta": float(np.max(abs(gaps[:44]/beta-target_energy))),
               "ground_residual": float(errors[0]), "max_low_band_residual": float(errors[:44].max()),
               "max_residual": float(errors.max()), "gap": float(gaps[1]),
               "low_states": int(low.sum()), "numeric_pass": numeric,
               "weak_prediction_pass": bool(numeric and relative_lines < weak_gate and relative_total < .02)
                                          if weak_gate is not None else None,
               "elapsed_seconds": time.perf_counter()-start}
        rows.append(row)
        if g == .000625:
            repeats.append(observed)
        lines.extend({"g": g, "seed": seed, "level": i, "omega": float(gaps[i]),
                      "W_pi": float(weights[i, 0]), "W_06pi": float(weights[i, 1]),
                      "residual": float(errors[i])} for i in range(45))
        reference.write_csv(OUT / "comparisons.csv", rows)
        reference.write_csv(OUT / "spectral_lines.csv", lines)
        print(row, flush=True)
    repeat_error = float(np.linalg.norm(repeats[0]-repeats[1])/np.linalg.norm(repeats[0]))
    all_pass = all(r["numeric_pass"] for r in rows) and all(r["weak_prediction_pass"]
                for r in rows if r["weak_prediction_pass"] is not None) and repeat_error < .001
    reference.write_json(OUT / "summary.json", {
        "all_prespecified_gates_pass": all_pass, "repeat_relative_line_error": repeat_error,
        "cases": rows, "elapsed_seconds": time.perf_counter()-start, "bulk_claim": False,
    })
    reference.write_json(OUT / "sha256.json", {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__), Path(previous.__file__), Path(original.__file__), Path(dark.__file__),
                  Path(reference.__file__), ROOT / "scripts/autoresearch_v5/analyze_negative_phase_independent_observables.py"]
        + sorted(OUT.iterdir()) if p.is_file()})
    if not all_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
