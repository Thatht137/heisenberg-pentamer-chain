"""精确检验热消光阻碍的局域对易子与部分迹。"""

from fractions import Fraction as F
from itertools import product
from math import factorial
from pathlib import Path
import hashlib
import json
import time

import prove_thermal_activation_exact as exact

ROOT = exact.ROOT
OUT = ROOT / "results/novelty_20261008/thermal_operator_obstruction"
add, local, dot, qdot = exact.add, exact.local, exact.dot, exact.qdot


def dipole(v, i, j):
    return add((1, local(v, i, "z")), (-1, local(v, j, "z")))


def composite(v, i, j):
    return add((1, qdot(v, i, j)), (-1, qdot(v, j, i)))


def matrix(n, operator):
    states = list(product(range(4), repeat=n))
    return {key: operator({key: F(1)}) for key in states}


def metric(key):
    result = 1
    for k in key:
        result *= factorial(k)*factorial(3)//factorial(3-k)
    return result


def inner(a, b):
    return sum((x*b[col].get(row, 0)*F(metric(row), metric(col))
                for col, entries in a.items() for row, x in entries.items()), F(0))


def partial_trace(a, keep):
    result = {}
    for col, entries in a.items():
        col_keep = tuple(col[i] for i in keep)
        out = result.setdefault(col_keep, {})
        for row, value in entries.items():
            if any(row[i] != col[i] for i in range(len(col)) if i not in keep):
                continue
            row_keep = tuple(row[i] for i in keep)
            out[row_keep] = out.get(row_keep, F(0))+value
    return {col: {row: x for row, x in entries.items() if x} for col, entries in result.items()}


def scaled_equal(a, b, scale):
    return all(a[col] == {r: scale*v for r, v in entries.items() if scale*v}
               for col, entries in b.items())


def commutator(v, h, op):
    return add((1, h(op(v))), (-1, op(h(v))))


def main():
    started = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=False)
    h = lambda v: dot(v, 0, 1)
    d = lambda v: dipole(v, 0, 1)
    x = lambda v: composite(v, 0, 1)
    cd = matrix(2, lambda v: commutator(v, h, d))
    cx = matrix(2, lambda v: commutator(v, h, x))
    gram = {"dd": inner(cd, cd), "dx": inner(cd, cx), "xx": inner(cx, cx)}
    minimum = gram["xx"]-gram["dx"]**2/gram["dd"]
    assert gram == {"dd": F(200), "dx": F(200), "xx": F(560)}
    assert minimum == 360
    for op in (cd, cx):
        assert all(not v for v in partial_trace(op, (0,)).values())
        assert all(not v for v in partial_trace(op, (1,)).values())
    # 三点交叉项不能留下两点支撑。
    cross = matrix(3, lambda v: commutator(v, lambda u: dot(u, 0, 1),
                                          lambda u: composite(u, 1, 2)))
    for keep in ((0, 1), (1, 2), (0, 2)):
        assert all(not v for v in partial_trace(cross, keep).values())
    n = 4
    hn = lambda v: add(*[(1, dot(v, i, (i+1) % n)) for i in range(n)])
    dn = lambda v: add(*[((-1)**i, local(v, i, "z")) for i in range(n)])
    yn = lambda v: add(*[((-1)**i, composite(v, i, (i+1) % n)) for i in range(n)])
    cdn = matrix(n, lambda v: commutator(v, hn, dn))
    cyn = matrix(n, lambda v: commutator(v, hn, yn))
    assert scaled_equal(partial_trace(cdn, (0, 1)), cd, 4**(n-2))
    assert scaled_equal(partial_trace(cyn, (0, 1)), cx, 4**(n-2))
    gn = {"dd": inner(cdn, cdn), "dy": inner(cdn, cyn), "yy": inner(cyn, cyn)}
    norm_min = (gn["yy"]-gn["dy"]**2/gn["dd"])/(5*n*4**n)
    lower_bound = minimum/(5*16)
    assert norm_min >= lower_bound
    summary = {"all_gates_pass": True, "exact_arithmetic": True,
               "bond_Gram": {k: str(v) for k, v in gram.items()},
               "bond_minimum": str(minimum), "bond_commutators_have_zero_partial_traces": True,
               "adjacent_cross_commutator_has_zero_all_two_site_partial_traces": True,
               "N4_chain_Gram": {k: str(v) for k, v in gn.items()},
               "N4_min_second_moment_over_b_squared": str(norm_min),
               "all_even_N_ge4_lower_bound_over_b_squared": str(lower_bound),
               "theorem_scope": "leading effective spin-3/2 nearest-neighbor even PBC chain; Q=pi; b!=0",
               "finite_T_conclusion": "for each finite even N>=4 and T/Jeff>0, no real retuning removes all positive-frequency weight",
               "not_claimed": ["uniform finite-T lower bound as N tends to infinity", "finite-beta exact extinction", "all momenta"],
               "elapsed_seconds": time.perf_counter()-started}
    (OUT/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    paths = [Path(__file__), Path(exact.__file__), *sorted(OUT.iterdir())]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    (OUT/"sha256.json").write_text(json.dumps(hashes, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
