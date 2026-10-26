"""直接积分微观谱的有限动量窗口，不平滑图片。"""

import os
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"

import csv
import hashlib
import itertools
import json
import time
from pathlib import Path

import numpy as np
from scipy.linalg import eigh
from scipy.optimize import brentq

import validate_thermal_two_cells as validation

ROOT, reference, micro = validation.ROOT, validation.reference, validation.micro
OUT = ROOT / "results/novelty_20261008/momentum_acceptance_v2"


def gram(alpha, beta, temperature, gap):
    blocks = []
    for up in range(11):
        states = np.array([sum(1 << i for i in inds)
                           for inds in itertools.combinations(range(10), up)])
        h = micro.sector_matrix(10, up, micro.bonds(10, alpha, beta)+[(9, 0, beta)]).toarray()
        e, v = eigh(h)
        assert np.linalg.norm(h@v-v*e)/max(1., np.linalg.norm(h)) < 1e-10
        z = np.column_stack([((states >> i) & 1)-.5 for i in range(10)])
        blocks.append((e, v, z))
    e0 = min(e[0] for e, v, z in blocks)
    partition = sum(np.exp(-(e-e0)/temperature).sum() for e, v, z in blocks)
    factors = []
    count = 0
    for e, v, z in blocks:
        low = e-e0 < gap/2
        el, vl = e[low], v[:, low]
        count += len(el)
        operators = np.array([vl.T@(z[:, a, None]*vl) for a in range(10)])
        weights = ((el[:, None]-el[None, :]) > 1e-9)*np.exp(-(el[None, :]-e0)/temperature)/partition
        factors.append((operators*np.sqrt(weights)[None, :, :]).reshape(10, -1).T)
    factor = np.concatenate(factors)
    g = factor.T@factor
    assert np.linalg.norm(g-g.T) < 1e-12
    assert np.linalg.eigvalsh(g)[0] > -1e-12
    return factor, count


def weight(factor, q, half_width, order=16):
    # 先合成跃迁振幅，避免近暗点强度矩阵相减失精度。
    nodes, weights = np.polynomial.legendre.leggauss(order)
    phases = np.exp(1j*np.arange(10)[:, None]*(q+half_width*nodes))
    values = np.sum(abs(factor@phases)**2, axis=0)/10
    return float(np.dot(weights, values)/2)


def main():
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=False)
    reference.write_json(OUT/"protocol.json", {
        "L": 10, "cells": 2, "all_Sz_sectors": True,
        "acceptance": "uniform normalized physical q interval [q0-delta,q0+delta]",
        "integration": "16-node Gauss-Legendre uniform-window quadrature; 32-node check; positive transition amplitudes",
        "alpha_policy": "fixed at the ideal central-q one-parameter retuning for each tau",
        "half_widths_over_pi": [0, .000001, .00001, .0001, .001, .005, .01],
        "cutoff": "both initial and final energies below E0+Delta_root/2",
        "physical_instrument_claim": False, "image_smoothing": False,
        "numerical_center_relative_gate": 1e-7, "wall_limit_seconds": 60,
        "do_not_require_physics_to_match_desired_outcome": True})
    with (validation.OUT/"comparisons.csv").open(newline="") as handle:
        baseline = list(csv.DictReader(handle))
    rows, cases = [], []
    for base in baseline:
        assert time.perf_counter()-started < 60
        spin, beta, tau = float(base["spin"]), float(base["beta"]), float(base["T_over_Jeff"])
        q = np.pi if spin == 1.5 else 3*np.pi/5
        root = float(base["alpha_root"])
        gap = beta/float(base["g"])
        g, count = gram(float(base["alpha_retuned"]), beta, float(base["T"]), gap)
        assert count == int(2*spin+1)**2
        center = weight(g, q, 0.)
        discrepancy = abs(center/float(base["W_positive_low"])-1)
        assert discrepancy < 1e-7
        sample = []
        for width in (0., .000001, .00001, .0001, .001, .005, .01):
            value = weight(g, q, width*np.pi)
            fine = weight(g, q, width*np.pi, order=32)
            assert abs(value/fine-1) < 1e-7
            row = {"spin": spin, "g": float(base["g"]), "beta": beta,
                   "T_over_Jeff": tau, "q0_over_pi": q/np.pi,
                   "half_width_over_pi": width, "W_averaged": value,
                   "W_ideal": center, "ratio_to_ideal": value/center}
            rows.append(row)
            sample.append(row)
        widths = np.geomspace(1e-9, .03*np.pi, 121)
        crossing = None
        left = 0.
        for right in widths:
            if weight(g, q, right) > 2*center:
                crossing = brentq(lambda x: weight(g, q, x)-2*center, left, right, xtol=1e-14)/np.pi
                break
            left = right
        cell, _, _ = validation.thermal.local.reference.local_projection(root, np.linspace(0, 2*np.pi, 41))
        sites = np.arange(5)-2
        aq = float(np.dot(cell["c"], -sites*np.sin(q*sites)))
        aqq = float(np.dot(cell["c"], -sites**2*np.cos(q*sites)))
        cases.append({"spin": spin, "g": float(base["g"]), "T_over_Jeff": tau,
                      "center_relative_error": discrepancy,
                      "weight_doubles_at_half_width_over_pi": crossing,
                      "A_q_at_local_root": aq, "A_qq_at_local_root": aqq,
                      "ratio_at_half_width_0p001pi": sample[4]["ratio_to_ideal"]})
    slopes = []
    for spin in (.5, 1.5):
        for tau in (.4, 1.6):
            for width in (0., .0001, .001, .01):
                selected = [r for r in rows if r["spin"] == spin and r["T_over_Jeff"] == tau
                            and r["half_width_over_pi"] == width]
                slope = np.polyfit(np.log([r["beta"] for r in selected]),
                                   np.log([r["W_averaged"] for r in selected]), 1)[0]
                slopes.append({"spin": spin, "T_over_Jeff": tau,
                               "half_width_over_pi": width, "slope": float(slope)})
    reference.write_csv(OUT/"acceptance_weights.csv", rows)
    reference.write_json(OUT/"summary.json", {"numerical_checks_pass": True,
        "cases": cases, "finite_window_slopes": slopes,
        "scope": "finite two-cell microscopic illustration, not an instrument resolution forecast",
        "elapsed_seconds": time.perf_counter()-started})
    files = [Path(__file__), Path(validation.__file__), validation.OUT/"comparisons.csv", *sorted(OUT.iterdir())]
    reference.write_json(OUT/"sha256.json", {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                           for p in files if p.is_file()})
    print(json.dumps({"cases": cases, "slopes": slopes}, indent=2))


if __name__ == "__main__":
    main()
