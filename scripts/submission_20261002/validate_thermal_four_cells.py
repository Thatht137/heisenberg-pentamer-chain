"""用总自旋升降恢复完整低能带，检验四胞热激活。"""

import os
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"

import hashlib
import itertools
import json
import time
from pathlib import Path

import numpy as np
from scipy.linalg import eigh
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import LinearOperator, eigsh

import check_thermal_compensation as thermal
import validate_thermal_two_cells as oracle

ROOT, reference, micro = thermal.ROOT, thermal.reference, oracle.micro
OUT = ROOT / "results/novelty_20261008/thermal_microscopic_four_cells"


def states(n, up):
    return np.array([sum(1 << i for i in inds)
                     for inds in itertools.combinations(range(n), up)], dtype=np.int64)


def raising(n, source, target):
    lookup = np.full(2**n, -1, dtype=np.int32)
    lookup[target] = np.arange(len(target))
    rows, cols = [], []
    for site in range(n):
        col = np.flatnonzero((source & (1 << site)) == 0)
        cols.append(col)
        rows.append(lookup[source[col] | (1 << site)])
    rows, cols = np.concatenate(rows), np.concatenate(cols)
    assert np.min(rows) >= 0
    return coo_matrix((np.ones(len(rows)), (rows, cols)),
                      shape=(len(target), len(source))).tocsr()


def spectrum(n, alpha, beta, gap, deadline, dense=False):
    cells = n // 5
    multiplicities = [1, 1, 1, 1] if cells == 2 else [4, 9, 11, 10, 6, 3, 1]
    count = sum(multiplicities)
    bonds = micro.bonds(n, alpha, beta) + [(n-1, 0, beta)]
    source = states(n, n//2)
    h = micro.sector_matrix(n, n//2, bonds)
    def matvec(x):
        if time.perf_counter() > deadline:
            raise TimeoutError("达到四胞热谱验证时间边界")
        return h @ x
    if dense:
        e, v = eigh(h.toarray())
    else:
        rng = np.random.default_rng(20261008)
        e, v = eigsh(LinearOperator(h.shape, matvec=matvec, dtype=np.float64),
                     k=count+4, which="SA", ncv=180, tol=1e-13,
                     maxiter=5000, v0=rng.normal(size=len(source)))
        order = np.argsort(e)
        e, v = e[order], v[:, order]
    low = e-e[0] < gap/2
    assert int(low.sum()) == count
    next_state = float(e[count]-e[0])
    e, v = e[:count], v[:, :count]
    target = states(n, n//2+1)
    raised = raising(n, source, target) @ v
    s2, u = eigh(raised.T @ raised)
    spins = np.rint((np.sqrt(1+4*s2)-1)/2).astype(int)
    s2_error = float(np.max(abs(s2-spins*(spins+1))))
    assert s2_error < 1e-7
    assert np.array_equal(np.bincount(spins), multiplicities)
    projected = u.T @ np.diag(e) @ u
    rotation = np.zeros_like(u)
    energies = np.empty(count)
    for j in range(len(multiplicities)):
        ids = np.flatnonzero(spins == j)
        ej, rj = eigh(projected[np.ix_(ids, ids)])
        rotation[np.ix_(ids, ids)] = rj
        energies[ids] = ej
    v = v @ u @ rotation
    blocks, checks = [], []
    for m in range(len(multiplicities)):
        assert time.perf_counter() < deadline
        if m:
            target = states(n, n//2+m)
            keep = spins >= m
            denom = np.sqrt(spins[keep]*(spins[keep]+1)-m*(m-1))
            v = (raising(n, source, target) @ v[:, keep]) / denom[None, :]
            energies, spins = energies[keep], spins[keep]
            source = target
            h = micro.sector_matrix(n, n//2+m, bonds)
        errors = np.linalg.norm(h @ v-v*energies, axis=0)
        orthog = np.linalg.norm(v.T @ v-np.eye(v.shape[1]))
        diagonal = sum((((source >> i) & 1)-.5)*(-1)**i for i in range(n))/np.sqrt(n)
        op = v.T @ (diagonal[:, None]*v)
        blocks.append((energies.copy(), op, spins.copy(), 1 if m == 0 else 2))
        checks.append({"M": m, "states": len(energies),
                       "max_residual": float(errors.max()), "orthogonality": float(orthog)})
    assert sum(len(e)*mult for e, op, spin, mult in blocks) == 4**cells
    assert max(r["max_residual"] for r in checks) < 1e-9
    assert max(r["orthogonality"] for r in checks) < 1e-8
    return blocks, {"sectors": checks, "spin_quantization_error": s2_error,
                    "retained_states": 4**cells, "next_state_M0": next_state}


def weight(blocks, temperature, threshold=1e-10):
    e0 = min(e.min() for e, op, spin, mult in blocks)
    partition = sum(mult*np.exp(-(e-e0)/temperature).sum() for e, op, spin, mult in blocks)
    total = ground = excited = balance = 0.
    for e, op, spin, mult in blocks:
        population = np.exp(-(e-e0)/temperature)/partition
        delta = e[:, None]-e[None, :]
        intens = abs(op)**2
        plus = delta > threshold
        weighted = mult*plus*population[None, :]*intens
        ground_initial = abs(e-e0) < threshold
        total += float(weighted.sum())
        ground += float(weighted[:, ground_initial].sum())
        excited += float(weighted[:, ~ground_initial].sum())
        reverse = float(np.sum(mult*(delta < -threshold)*population[None, :]*intens))
        expected = float(np.sum(weighted*np.exp(-np.maximum(delta, 0)/temperature)))
        balance = max(balance, abs(reverse-expected))
    return {"W_positive_low": total, "W_ground_initial": ground,
            "W_excited_initial": excited, "partition_low": float(partition),
            "detailed_balance_error": balance}


def activation_lines(blocks, jeff, beta, b):
    e0 = min(e.min() for e, op, spin, mult in blocks)
    sums = {3: 0., 8: 0.}
    moments = {3: 0., 8: 0.}
    initial_count = 0
    initial_gap = []
    for e, op, spin, mult in blocks:
        scaled = (e-e0)/jeff
        initial = (spin == 1) & (abs(scaled-1) < .3)
        initial_count += int(initial.sum())*mult
        initial_gap.extend(scaled[initial].tolist())
        for final_gap in (3, 8):
            final = (spin == 2) & (abs(scaled-final_gap) < .3)
            strength = mult*abs(op[np.ix_(final, initial)])**2
            frequency = scaled[final, None]-scaled[None, initial]
            sums[final_gap] += float(strength.sum())/beta**2/b**2
            moments[final_gap] += float((strength*frequency).sum())/beta**2/b**2
    assert initial_count == 3
    return {"initial_multiplicity": initial_count,
            "first_gap_over_Jeff": float(np.mean(initial_gap)),
            "strength_omega2_over_beta2_b2": sums[3],
            "strength_omega7_over_beta2_b2": sums[8],
            "centroid_omega2_over_Jeff": moments[3]/sums[3],
            "centroid_omega7_over_Jeff": moments[8]/sums[8],
            "ratio_omega2_to_omega7": sums[3]/sums[8]}


def save_spectrum(path, blocks):
    arrays = {}
    for m, (e, op, spin, mult) in enumerate(blocks):
        arrays.update({f"e_{m}": e, f"op_{m}": op,
                       f"spin_{m}": spin, f"multiplicity_{m}": np.array(mult)})
    np.savez_compressed(path, **arrays)


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    deadline = started+900
    protocol = {"L": 20, "cells": 4, "boundary": "PBC", "q_over_pi": 1,
        "g_values": [.000625, .00125, .0025], "T_over_Jeff_values": [.1, .2, .4, 1.6],
        "retuning": "fixed leading N=4 zero-T optimum; not reoptimized at each T",
        "temperature": "T=tau*beta*c1(alpha_root)^2",
        "solver": "existing scipy sparse sector Hamiltonian; M0 eigenpairs plus exact SU2 raising",
        "M0_dimension": 184756, "M0_eigenpairs": 48, "ncv": 180,
        "M0_low_states": 44, "all_M_low_states": 256,
        "numerical_gates": {"residual": 1e-9, "orthogonality": 1e-8, "S2": 1e-7},
        "physical_gates_at_weakest_g": {"total_C_tau_at_least_0p2_relative": .05,
                                        "two_line_strength_relative": .05, "two_line_frequency_relative": .05},
        "tau0p1": "diagnostic including finite-beta ground-state background; not an agreement gate",
        "positive_frequency_threshold": 1e-10,
        "threshold_checks": [1e-11, 1e-9],
        "benchmark": "L10 reconstructed band vs all-sector full-spectrum oracle",
        "tail_bound": "Zoutside/Zlow <= (2^L-4^N)*exp[-(Delta-2*vnorm)/T]/Zlow",
        "vnorm": "(3/4)*(N*abs(beta)+2*N*abs(alpha-alpha_root))",
        "threads": 1, "wall_limit_seconds": 900, "thermodynamic_limit_claim": False}
    reference.write_json(OUT/"protocol.json", protocol)
    alpha = -(2+np.sqrt(7))/6
    t, quad, c1, lc, rc, gap, error = thermal.local.local_probe(alpha, np.pi)
    data, _ = thermal.blocks(4, 4, t, quad, c1, lc, rc, np.pi)
    zero = thermal.weight(data, 0.)
    derivative = (thermal.local.amplitude(alpha+1e-5, np.pi)-thermal.local.amplitude(alpha-1e-5, np.pi))/2e-5
    kappa = -zero["lambda"]/derivative
    b = float(lc[1].real)
    assert abs(abs(b)/.1236117648014558-1) < 1e-8
    beta = .005*gap
    small, checks = spectrum(10, alpha+kappa*beta, beta, gap, deadline, dense=True)
    temperature = .4*beta*c1*c1
    restored = weight(small, temperature)
    full = oracle.microscopic(alpha+kappa*beta, beta, np.pi, temperature, gap, deadline)
    benchmark = {"restored": restored, "full": full, "checks": checks,
                 "relative_weight_error": abs(restored["W_positive_low"]/full["W_positive_low"]-1)}
    assert benchmark["relative_weight_error"] < 1e-7
    reference.write_json(OUT/"benchmark_L10.json", benchmark)
    print("L10 benchmark passed", flush=True)
    rows, line_rows, all_checks = [], [], []
    for g in protocol["g_values"]:
        beta = g*gap
        shifted = alpha+kappa*beta
        jeff = beta*c1*c1
        print(f"START L20 g={g}", flush=True)
        blocks, checks = spectrum(20, shifted, beta, gap, deadline)
        save_spectrum(OUT/f"low_band_g{g:.7f}.npz", blocks)
        all_checks.append({"g": g, **checks})
        reference.write_json(OUT/"numerical_checks.json", all_checks)
        lines = {"g": g, **activation_lines(blocks, jeff, beta, b)}
        line_rows.append(lines)
        reference.write_csv(OUT/"activation_lines.csv", line_rows)
        vnorm = .75*(4*abs(beta)+8*abs(shifted-alpha))
        assert 4*vnorm < gap
        for tau in protocol["T_over_Jeff_values"]:
            temperature = tau*jeff
            result = weight(blocks, temperature)
            predicted = thermal.weight(data, tau, zero["lambda"])["C_fixed_zeroT_retuning"]
            thresholds = [weight(blocks, temperature, eps)["W_positive_low"] for eps in (1e-11, 1e-9)]
            row = {"g": g, "tau": tau, "alpha_root": alpha, "alpha_retuned": shifted,
                "kappa": kappa, "beta": beta, "T": temperature, "local_gap": gap,
                "vnorm_upper": vnorm, "outside_gap_lower": gap-2*vnorm,
                "log_outside_population_upper": float(np.log(2**20-256)-(gap-2*vnorm)/temperature-np.log(result["partition_low"])),
                **result, "C_predicted": predicted, "W_over_beta2": result["W_positive_low"]/beta**2,
                "coefficient_relative_error": abs(result["W_positive_low"]/beta**2/predicted-1),
                "threshold_relative_spread": max(abs(x/result["W_positive_low"]-1) for x in thresholds),
                "elapsed_seconds": time.perf_counter()-started}
            rows.append(row)
            reference.write_csv(OUT/"comparisons.csv", rows)
            print(json.dumps(row), flush=True)
        print(json.dumps(lines), flush=True)
    weakest = line_rows[0]
    physical_pass = all(r["coefficient_relative_error"] < .05 for r in rows
                        if r["g"] == protocol["g_values"][0] and r["tau"] >= .2)
    physical_pass &= all(abs(weakest[key]/expected-1) < .05 for key, expected in (
        ("strength_omega2_over_beta2_b2", 27/50), ("strength_omega7_over_beta2_b2", 12/25),
        ("centroid_omega2_over_Jeff", 2), ("centroid_omega7_over_Jeff", 7)))
    summary = {"numerical_gates_pass": True, "physical_agreement_gates_pass": bool(physical_pass),
        "elapsed_seconds": time.perf_counter()-started, "kappa": kappa,
        "b": b, "scope": "finite N4 microscopic low-band thermal response at fixed zero-T retuning",
        "outside_band_is_bounded_not_computed": True, "partition_function": "complete retained band plus rigorous tail bound"}
    reference.write_json(OUT/"summary.json", summary)
    files = [Path(__file__), Path(thermal.__file__), Path(micro.__file__), Path(oracle.__file__),
             ROOT/"scripts/autoresearch_v5/analyze_negative_phase_independent_observables.py", *sorted(OUT.iterdir())]
    reference.write_json(OUT/"sha256.json", {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                           for p in files if p.is_file()})
    print(json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
