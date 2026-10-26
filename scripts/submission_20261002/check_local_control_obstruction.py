"""检验逐胞局域微调能否降低均匀链的复合谱响应。"""

import os
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"

from itertools import combinations
from pathlib import Path
import hashlib
import json
import time

import numpy as np
from scipy.linalg import eigh

import check_uniform_trace_weight_bound as bound

ROOT = bound.ROOT
OUT = ROOT / "results/novelty_20261008/local_control_obstruction"


def microscopic_tangents():
    t = bound.chain.local_spins(1)
    sz = [bound.chain.embed({i: t[2]}, 5, 2).toarray() for i in range(5)]
    pairs = {(i, j): sum(bound.chain.embed({i: a, j: a}, 5, 2) for a in t).toarray()
             for i, j in combinations(range(5), 2)}
    alpha = -(2 + np.sqrt(7))/6
    h = alpha*(pairs[0, 1]+pairs[3, 4])+pairs[1, 2]+pairs[2, 3]
    probe, total_z = sum((-1)**i*z for i, z in enumerate(sz)), sum(sz)
    energy, vectors = eigh(h)
    assert np.count_nonzero(abs(energy-energy[0]) < 1e-10) == 4
    u = vectors[:, :4]
    tz = u.conj().T @ total_z @ u
    denominator = float(np.trace(tz @ tz).real)
    gap = float(energy[4]-energy[0])
    resolvent = (vectors[:, 4:] / (energy[4:]-energy[0])) @ vectors[:, 4:].conj().T
    assert np.linalg.norm(u.conj().T @ probe @ u) < 1e-11

    def amplitude(matrix):
        e, v = eigh(matrix)
        assert np.count_nonzero(abs(e-e[0]) < 1e-10) == 4
        v = v[:, :4]
        z = v.conj().T @ total_z @ v
        return float(np.trace((v.conj().T @ probe @ v) @ z).real / np.trace(z @ z).real)

    rows = []
    for pair, w in pairs.items():
        projected = u.conj().T @ w @ u
        scalar_error = float(np.linalg.norm(projected-np.trace(projected)*np.eye(4)/4))
        derivative = -u.conj().T @ (w @ resolvent @ probe + probe @ resolvent @ w) @ u
        coefficient = float(np.trace(tz @ derivative).real/denominator)
        vector_error = float(np.linalg.norm(derivative-coefficient*tz))
        checks = []
        for step in (1e-4, 5e-5):
            finite = (amplitude(h+step*w)-amplitude(h-step*w))/(2*step)
            checks.append({"step": step, "derivative": finite, "absolute_error": abs(finite-coefficient)})
        assert scalar_error < 1e-10 and vector_error < 1e-10
        assert checks[-1]["absolute_error"] < 2e-6
        rows.append({"pair_one_based": [i+1 for i in pair], "derivative": coefficient,
                     "projected_exchange_nonscalar_norm": scalar_error,
                     "probe_derivative_nondipole_norm": vector_error, "finite_differences": checks})
    return {"alpha": alpha, "local_gap": gap, "pairwise_controls": rows,
            "meaning": "infinitesimal tangent directions, not a finite change to the reference microscopic model"}


def spectral_case(twice_spin, n, seed):
    h, dipole, y = bound.operators(twice_spin, n)
    s, d, ell = twice_spin/2, twice_spin+1, 5.
    z = bound.chain.local_spins(twice_spin)[2]
    controls = [(-1)**i*bound.chain.embed({i: z}, n, d)/np.sqrt(ell*n) for i in range(n)]
    energy, v = eigh(h.toarray())
    operators = [v.conj().T @ (y @ v)/np.sqrt(ell*n)]
    operators += [v.conj().T @ (a @ v) for a in controls]
    delta = energy[:, None]-energy[None, :]
    rng = np.random.default_rng(seed)
    rows = []
    for temperature in (.2, 1.6, None):
        p = np.ones(d**n) if temperature is None else np.exp(-(energy-energy[0])/temperature)
        p /= p.sum()
        for threshold in (1e-9, np.sqrt(3*s*(s+1)/4)):
            weights = (delta > threshold)*p[None, :]
            sources = np.array([(a*np.sqrt(weights)).ravel() for a in operators])
            gram = (sources.conj() @ sources.T).real
            g, cross = gram[1:, 1:], gram[0, 1:]
            eigen, modes = eigh(g)
            selected = eigen > max(eigen.max(), 1.)*1e-12
            optimum = -modes[:, selected] @ ((modes[:, selected].T @ cross)/eigen[selected])
            uniform = -cross.sum()/g.sum()
            min_all = float(np.linalg.norm(sources[0]+optimum @ sources[1:])**2)
            min_uniform = float(np.linalg.norm(sources[0]+uniform*sources[1:].sum(axis=0))**2)
            assert abs(min_all-min_uniform) < 1e-10*max(1, min_uniform)
            errors, excesses = [], []
            for _ in range(12):
                u = rng.normal(size=n)*3
                mean = u.mean()
                uniform_source = sources[0]+mean*sources[1:].sum(axis=0)
                remainder = (u-mean) @ sources[1:]
                actual = float(np.linalg.norm(uniform_source+remainder)**2)
                uniform_weight = float(np.linalg.norm(uniform_source)**2)
                error = abs(actual-uniform_weight-float(np.linalg.norm(remainder)**2))
                assert error < 1e-10*max(1, actual)
                errors.append(error)
                excesses.append(actual-uniform_weight)
            rows.append({"T_over_Jeff": "uniform_trace" if temperature is None else temperature,
                         "threshold": threshold, "control_gram_rank": int(selected.sum()),
                         "uniform_optimum_u_over_b": uniform, "all_control_optimum": optimum.tolist(),
                         "minimum_all_controls_over_b2": min_all, "minimum_uniform_over_b2": min_uniform,
                         "maximum_projection_identity_error": max(errors),
                         "minimum_sampled_excess": min(excesses)})
    return {"spin": s, "N": n, "rows": rows}


def moment_case(twice_spin, n, seed):
    h, dipole, y = bound.operators(twice_spin, n)
    s, d, ell = twice_spin/2, twice_spin+1, 5.
    c = s*(s+1)
    z = bound.chain.local_spins(twice_spin)[2]
    controls = [(-1)**i*bound.chain.embed({i: z}, n, d) for i in range(n)]
    rng = np.random.default_rng(seed)
    minimum = c*c*(4*c-3)*(86*c-27)/(810*ell)
    errors = []
    for _ in range(12):
        u = rng.normal(size=n)*3
        r = (y+sum(a*op for a, op in zip(u, controls)))/np.sqrt(ell*n)
        comm = h @ r-r @ h
        actual = bound.chain.inner(comm, comm)/d**n
        prediction = minimum+(d*d-1)**2/(18*ell)*np.mean(((u+np.roll(u, -1))/2+(d*d-4)/12)**2)
        errors.append(abs(actual-prediction))
        assert abs(actual-prediction) < 1e-10*max(1, prediction)
    return {"spin": s, "N": n, "maximum_moment_identity_error": max(errors)}


def main():
    started = time.perf_counter()
    OUT.mkdir(exist_ok=False)
    protocol = {"question": "Do arbitrary cellwise one-spin controls outperform the uniform control at the Q=pi composite source?",
        "scope": "leading uniform effective Hamiltonian; translation-invariant Gibbs state; cell-local SU(2) perturbations of order beta",
        "cases": [[2, 4], [3, 4]], "extra_moment_cases": [[2, 6], [3, 6]],
        "microscopic_tangents": "all ten pairwise Heisenberg bonds within one pentamer at the quartet root",
        "control_samples_per_observable": 12, "seed": 20261008, "wall_limit_seconds": 120,
        "acceptance": "spectral projection identity and optimized equality 1e-10; tangent nondipole norm 1e-10; finite-difference derivative error 2e-6",
        "not_claimed": ["anisotropic controls", "order-one changes along the local root manifold", "nonuniform leading intercell exchange", "finite-beta exact protection"]}
    (OUT/"protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    tangent = microscopic_tangents()
    spectra, moments = [], []
    for twice_spin, n in protocol["cases"]:
        assert time.perf_counter()-started < 120
        spectra.append(spectral_case(twice_spin, n, protocol["seed"]))
        moments.append(moment_case(twice_spin, n, protocol["seed"]))
    for twice_spin, n in protocol["extra_moment_cases"]:
        assert time.perf_counter()-started < 120
        moments.append(moment_case(twice_spin, n, protocol["seed"]))
    summary = {"passed": True, "microscopic_tangents": tangent, "spectra": spectra,
               "moments": moments, "elapsed_seconds": time.perf_counter()-started}
    (OUT/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    paths = [Path(__file__), Path(bound.__file__), Path(bound.chain.__file__), *sorted(OUT.iterdir())]
    (OUT/"sha256.json").write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                             for p in paths}, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "elapsed_seconds": summary["elapsed_seconds"],
        "largest_tangent_nondipole_norm": max(r["probe_derivative_nondipole_norm"] for r in tangent["pairwise_controls"]),
        "largest_finite_difference_error": max(r["finite_differences"][-1]["absolute_error"] for r in tangent["pairwise_controls"]),
        "largest_optimum_difference": max(abs(r["minimum_all_controls_over_b2"]-r["minimum_uniform_over_b2"]) for case in spectra for r in case["rows"]),
        "moments": moments}, indent=2))


if __name__ == "__main__":
    main()
