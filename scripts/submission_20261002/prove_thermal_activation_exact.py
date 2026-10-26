"""用有理数自旋代数验证四胞热激活系数。"""

from collections import defaultdict
from fractions import Fraction as F
from math import factorial
import hashlib
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/novelty_20261008/thermal_activation_exact"


def add(*terms):
    result = defaultdict(F)
    for factor, vector in terms:
        for key, value in vector.items():
            result[key] += factor * value
    return {key: value for key, value in result.items() if value}


def local(vector, site, kind):
    result = defaultdict(F)
    for key, value in vector.items():
        k = key[site]
        target = list(key)
        if kind == "z":
            factor = F(3, 2) - k
        elif kind == "minus":
            if k == 3:
                continue
            target[site] += 1
            factor = 1
        elif kind == "plus":
            if k == 0:
                continue
            target[site] -= 1
            factor = k * (4-k)
        else:
            raise ValueError(kind)
        result[tuple(target)] += value * factor
    return {key: value for key, value in result.items() if value}


def total(vector, sites, kind):
    return add(*[(1, local(vector, i, kind)) for i in sites])


def dot(vector, i, j):
    return add((1, local(local(vector, j, "z"), i, "z")),
               (F(1, 2), local(local(vector, j, "minus"), i, "plus")),
               (F(1, 2), local(local(vector, j, "plus"), i, "minus")))


def hamiltonian(vector):
    return add(*[(1, dot(vector, i, (i+1) % 4)) for i in range(4)])


def quadrupole(vector, site, kind):
    if kind == "z":
        return add((1, local(local(vector, site, "z"), site, "z")),
                   (-F(5, 4), vector))
    return add((F(1, 2), local(local(vector, site, kind), site, "z")),
               (F(1, 2), local(local(vector, site, "z"), site, kind)))


def qdot(vector, i, j):
    return add((1, quadrupole(local(vector, j, "z"), i, "z")),
               (F(1, 2), quadrupole(local(vector, j, "minus"), i, "plus")),
               (F(1, 2), quadrupole(local(vector, j, "plus"), i, "minus")))


def residual(vector):
    dipole = add(*[((-1)**i, local(vector, i, "z")) for i in range(4)])
    composite = add(*[(sign, qdot(vector, i, j))
                      for a in (0, 2) for b in (1, 3)
                      for i, j, sign in ((a, b, 1), (b, a, -1))])
    return add((1, composite), (3, dipole))


def norm2(vector):
    # 非归一基 |k>=(S-)^k|s,s> 的精确度规。
    result = F(0)
    for key, value in vector.items():
        metric = 1
        for k in key:
            metric *= factorial(k) * factorial(3) // factorial(3-k)
        result += value * value * metric
    return result


def pair_maximum(k, sites):
    vector = {(0, 0, 0, 0): F(1)}
    for _ in range(k):
        vector = total(vector, sites, "minus")
    return vector


def highest(total_j):
    degree = 6-total_j
    coefficient = F(1)
    terms = []
    for ka in range(degree+1):
        vector = pair_maximum(ka, (0, 2))
        for _ in range(degree-ka):
            vector = total(vector, (1, 3), "minus")
        terms.append((coefficient, vector))
        if ka < degree:
            coefficient *= -F((degree-ka)*(7-degree+ka), (ka+1)*(6-ka))
    vector = add(*terms)
    assert not total(vector, range(4), "plus")
    return vector


def pair_square(vector, a, b):
    return add((F(15, 2), vector), (2, dot(vector, a, b)))


def main():
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=False)
    protocol = {"arithmetic": "Python Fraction, exact rational",
                "cells": 4, "spin": "3/2", "boundary": "PBC",
                "normalization_squared": 20,
                "probe_residual": "b*(Y+3*D_unnormalized)/sqrt(20)",
                "wall_limit_seconds": 120, "finite_beta_claim": False}
    (OUT/"protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    ground = highest(0)
    assert not add((1, hamiltonian(ground)), (12, ground))
    assert not residual(ground)
    initial = highest(1)
    totals = {"omega_2": F(0), "omega_7_A3_B1": F(0), "omega_7_A1_B3": F(0)}
    rows = []
    for m in (1, 0, -1):
        assert time.perf_counter()-started < 120
        assert not add((1, hamiltonian(initial)), (11, initial))
        r = residual(initial)
        hr = hamiltonian(r)
        low = add((-F(1, 5), hr), (-F(4, 5), r))
        high = add((F(1, 5), hr), (F(9, 5), r))
        assert not add((1, hamiltonian(low)), (9, low))
        assert not add((1, hamiltonian(high)), (4, high))
        a3 = add((F(1, 10), pair_square(high, 0, 2)), (-F(1, 5), high))
        a1 = add((1, high), (-1, a3))
        for source, ja, jb in ((low, 3, 3), (a3, 3, 1), (a1, 1, 3)):
            assert not add((1, pair_square(source, 0, 2)), (-ja*(ja+1), source))
            assert not add((1, pair_square(source, 1, 3)), (-jb*(jb+1), source))
        row = {"M": m}
        weights = []
        for name, source in zip(totals, (low, a3, a1)):
            value = norm2(source)/(20*norm2(initial))
            totals[name] += value
            row[name] = str(value)
            weights.append(value)
        assert sum(weights) == norm2(r)/(20*norm2(initial))
        rows.append(row)
        initial = total(initial, range(4), "minus")
    assert sum(totals.values()) == F(51, 50)
    audit = json.loads((ROOT/"results/novelty_20261008/thermal_activation_audit_v2/summary.json").read_text())
    b = .1236117648014558
    relative_error = abs(float(sum(totals.values()))*b*b/audit["activation_prefactor"]-1)
    assert relative_error < 1e-10
    summary = {"all_gates_pass": True, "exact_arithmetic": True,
               "ground_residual_exactly_zero": True, "first_triplet_energy": -11,
               "ground_energy": -12, "thermal_gap_over_Jeff": 1,
               "line_coefficients_divided_by_b_squared": {k: str(v) for k, v in totals.items()},
               "total_prefactor_divided_by_b_squared": str(sum(totals.values())),
               "M_resolved": rows, "float_ED_relative_error": relative_error,
               "law": "Cmin(tau) = (51/50)*b^2*exp(-1/tau) + o(exp(-1/tau))",
               "scope": "leading effective N=4 PBC quartet at Q=pi only",
               "elapsed_seconds": time.perf_counter()-started}
    (OUT/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    paths = [Path(__file__), *sorted(OUT.iterdir())]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (OUT/"sha256.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
