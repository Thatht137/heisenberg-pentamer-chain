"""检验有限动量窗口的交换重调，不修改原谱图。"""

import os
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"

import hashlib
import json
import time
from pathlib import Path

import numpy as np
from scipy.optimize import brentq, minimize_scalar

import check_momentum_acceptance as acceptance

validation = acceptance.validation
thermal, reference, ROOT = validation.thermal, validation.reference, validation.ROOT
OUT = ROOT / "results/novelty_20261008/momentum_window_retuning"


def main():
    started = time.perf_counter()
    deadline = started + 180
    OUT.mkdir(parents=True, exist_ok=False)
    protocol = {
        "question": "Can optimizing exchange for a finite q window remove its background?",
        "L": 10, "cells": 2, "boundary": "PBC; two distinct intercell bonds",
        "all_Sz_sectors": True, "full_dimension": 1024, "largest_block": 252,
        "g_values": [.00125, .0025, .005, .01], "T_over_Jeff": 1.6,
        "quartet_widths": "delta = rho * sqrt(beta), rho = 0, 0.25, 0.5, 1",
        "doublet_widths": "delta = rho * beta^2, rho = 0, 1, 2, 4",
        "temperature": "Fixed tau*beta*c1(root)^2 while alpha is optimized",
        "window": "Normalized uniform average over q0 +/- delta, no smoothing",
        "band_and_partition": "Both states below E0+Delta_root/2; full 1024-state partition",
        "optimizer": "Nine-point local bracket then Brent; no global optimum claim",
        "quartet_control": "alpha = root + x*beta; bracket kappa_prediction +/- 2",
        "doublet_control": "alpha = root + kappa0*beta + x*beta^2; bracket -32 to 32",
        "quadrature": "16 nodes; 32-node final check",
        "numerical_gates": {"eigen_residual": 1e-10, "quadrature_relative": 1e-7,
                            "band_count": "16 quartet or 4 doublet", "interior_minimum": True},
        "physics_prediction_not_a_numerical_gate": True,
        "threads": 1, "wall_limit_seconds": 180,
        "scope": "Fixed finite ring and shrinking-window weak-coupling limit, not instrument resolution",
    }
    reference.write_json(OUT / "protocol.json", protocol)
    rows, cases = [], []
    for spin, q, bracket in ((1.5, np.pi, (-1., -.5)), (.5, 3*np.pi/5, (.5, 2.))):
        root = brentq(lambda a: thermal.local.amplitude(a, q), *bracket, xtol=1e-13)
        t, quad, c1, lc, rc, gap, error = thermal.local.local_probe(root, q)
        data, checks = thermal.blocks(2, int(2*spin+1), t, quad, c1, lc, rc, q)
        predicted = thermal.weight(data, 1.6)
        derivative = (thermal.local.amplitude(root+1e-5, q)
                      - thermal.local.amplitude(root-1e-5, q))/2e-5
        kappa0 = -predicted["lambda"]/derivative
        cell, _, _ = reference.local_projection(root, np.linspace(0, 2*np.pi, 41))
        sites = np.arange(5)-2
        aq = float(np.dot(cell["c"], -sites*np.sin(q*sites)))
        aqq = float(np.dot(cell["c"], -sites**2*np.cos(q*sites)))
        dd = predicted["D_positive_weight"]
        case = {"spin": spin, "root": root, "gap": gap, "c1_squared": c1*c1,
                "A_alpha": derivative, "A_q": aq, "A_qq": aqq,
                "kappa0": kappa0, "D_positive_weight": dd,
                "C_min": predicted["C_min"], "effective_checks": checks}
        cases.append(case)
        for g in protocol["g_values"]:
            beta, temperature = g*gap, 1.6*g*gap*c1*c1
            rhos = (0., .25, .5, 1.) if spin == 1.5 else (0., 1., 2., 4.)
            for rho in rhos:
                assert time.perf_counter() < deadline
                delta = rho*(np.sqrt(beta) if spin == 1.5 else beta**2)
                kpred = kappa0-aqq*rho**2/(6*derivative) if spin == 1.5 else kappa0
                lower, upper = (kpred-2, kpred+2) if spin == 1.5 else (-32., 32.)
                scale = beta**(2 if spin == 1.5 else 4)
                cache = {}

                def alpha_of(x):
                    return root+x*beta if spin == 1.5 else root+kappa0*beta+x*beta**2

                def evaluate(x):
                    assert time.perf_counter() < deadline
                    x = float(x)
                    if x not in cache:
                        factor, count = acceptance.gram(alpha_of(x), beta, temperature, gap)
                        assert count == int(2*spin+1)**2
                        cache[x] = acceptance.weight(factor, q, delta)/scale
                    return cache[x]

                grid = np.linspace(lower, upper, 9)
                values = [evaluate(x) for x in grid]
                best = int(np.argmin(values))
                assert 0 < best < len(grid)-1, (spin, g, rho, values)
                result = minimize_scalar(evaluate, bracket=tuple(grid[best-1:best+2]),
                                         method="brent", options={"xtol": 1e-10, "maxiter": 80})
                assert result.success and lower < result.x < upper
                factor, count = acceptance.gram(alpha_of(result.x), beta, temperature, gap)
                fine = acceptance.weight(factor, q, delta, order=32)/scale
                quadrature_error = abs(fine-result.fun)/max(abs(fine), 1e-15)
                assert quadrature_error < 1e-7
                fixed_x = kappa0 if spin == 1.5 else 0.
                fixed = evaluate(fixed_x)
                assert fine <= fixed+1e-10*max(1., fixed)
                limit = (predicted["C_min"]+aqq*aqq*dd*rho**4/45 if spin == 1.5
                         else aq*aq*dd*rho*rho/3)
                row = {"spin": spin, "g": g, "beta": beta, "rho": rho,
                       "delta_over_pi": delta/np.pi, "alpha_opt": alpha_of(result.x),
                       "optimizer_coordinate": float(result.x), "kappa_predicted": kpred,
                       "W_min": fine*scale, "W_fixed_central_leading": fixed*scale,
                       "normalized_min": fine, "predicted_limit": limit,
                       "relative_to_limit": fine/limit if limit > 1e-20 else None,
                       "quadrature_error": quadrature_error, "evaluations": len(cache),
                       "optimizer_success": bool(result.success)}
                rows.append(row)
                reference.write_csv(OUT / "comparisons.csv", rows)
                print(json.dumps(row), flush=True)
    slopes = []
    for spin in (1.5, .5):
        for rho in sorted({r["rho"] for r in rows if r["spin"] == spin}):
            selected = [r for r in rows if r["spin"] == spin and r["rho"] == rho]
            slope = None if spin == .5 and rho == 0 else float(np.polyfit(
                np.log([r["beta"] for r in selected]), np.log([r["W_min"] for r in selected]), 1)[0])
            slopes.append({"spin": spin, "rho": rho, "slope": slope})
    reference.write_json(OUT / "summary.json", {
        "numerical_checks_pass": True, "cases": cases, "slopes": slopes,
        "elapsed_seconds": time.perf_counter()-started,
        "interpretation": "Window reoptimization removes the mean form-factor shift, not its variance.",
        "general_second_order_doublet_theorem": False,
        "finite_size_instrument_claim": False})
    files = [Path(__file__), Path(acceptance.__file__), Path(validation.__file__),
             Path(thermal.__file__), Path(thermal.local.__file__), Path(reference.__file__),
             Path(validation.micro.__file__), *sorted(OUT.iterdir())]
    reference.write_json(OUT / "sha256.json", {str(p.relative_to(ROOT)):
        hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()})


if __name__ == "__main__":
    main()
