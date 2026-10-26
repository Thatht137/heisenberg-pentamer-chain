"""精确验证一般自旋的键通道方差及热消光阻碍。"""

from fractions import Fraction as F
from itertools import product
from math import comb, factorial
from pathlib import Path
import hashlib
import json
import time

import prove_thermal_operator_obstruction as old

ROOT = old.ROOT
OUT = ROOT/"results/novelty_20261008/general_spin_obstruction"
add = old.add


def clean(p):
    while len(p) > 1 and p[-1] == 0:
        p.pop()
    return p


def plus(*terms):
    p = [F(0)]*max(len(poly) for coefficient, poly in terms)
    for coefficient, poly in terms:
        for i, value in enumerate(poly):
            p[i] += coefficient*value
    return clean(p)


def times(a, b):
    p = [F(0)]*(len(a)+len(b)-1)
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            p[i+j] += x*y
    return clean(p)


def power_sum(k):
    # 逐系数验证 P(d+1)-P(d)=d^k，并固定 P(1)=0。
    p = [F(0)]*(k+2)
    for r in range(k, -1, -1):
        known = sum(comb(j, r)*p[j] for j in range(r+2, k+2))
        p[r+1] = (F(int(r == k))-known)/(r+1)
    p[0] = -sum(p[1:])
    difference = [sum(F(comb(j, r))*p[j] for j in range(r+1, len(p)))
                  for r in range(len(p)-1)]
    assert difference == [F(int(r == k)) for r in range(k+1)]
    assert sum(p) == 0
    return clean(p)


def symbolic_gram():
    d2 = [F(0), F(0), F(1)]
    dm1, dm4 = plus((1, d2), (-1, [F(1)])), plus((1, d2), (-4, [F(1)]))
    powers = {k: power_sum(k) for k in (3, 5, 7, 9)}
    moments = [plus((F(2, 3), times(d2, powers[k])), (-F(2, 3), powers[k+2])) for k in (3, 5, 7)]
    dd = moments[0]
    center = plus((F(1, 6), dm1))
    dx = plus((F(1, 2), moments[1]), (-1, times(center, dd)))
    xx = plus((F(1, 4), moments[2]), (-1, times(center, moments[1])), (1, times(times(center, center), dd)))
    expected_dd = plus((F(1, 18), times(d2, times(dm1, dm1))))
    expected_dx = plus((F(1, 12), times(dd, dm4)))
    expected_xx = plus((F(7, 360), times(dd, times(dm4, dm4))))
    minimum = plus((F(1, 80), times(dd, times(dm4, dm4))))
    assert dd == expected_dd and dx == expected_dx and xx == expected_xx
    assert plus((1, times(dd, xx)), (-1, times(dx, dx))) == times(dd, minimum)
    return {"dd": dd, "dx": dx, "xx": xx, "minimum": minimum}


class Spin:
    def __init__(self, twice_spin):
        self.twice_spin = twice_spin
        self.s = F(twice_spin, 2)
        self.d = twice_spin+1

    def local(self, vector, site, kind):
        result = {}
        for key, value in vector.items():
            k = key[site]
            target = list(key)
            if kind == "z":
                factor = self.s-k
            elif kind == "minus":
                if k == self.twice_spin:
                    continue
                target[site] += 1
                factor = 1
            elif kind == "plus":
                if k == 0:
                    continue
                target[site] -= 1
                factor = k*(self.d-k)
            else:
                raise ValueError(kind)
            target = tuple(target)
            result[target] = result.get(target, F(0))+value*factor
        return {key: value for key, value in result.items() if value}

    def dot(self, v, i, j):
        return add((1, self.local(self.local(v, j, "z"), i, "z")),
                   (F(1, 2), self.local(self.local(v, j, "minus"), i, "plus")),
                   (F(1, 2), self.local(self.local(v, j, "plus"), i, "minus")))

    def quadrupole(self, v, i, kind):
        if kind == "z":
            return add((1, self.local(self.local(v, i, "z"), i, "z")),
                       (-self.s*(self.s+1)/3, v))
        return add((F(1, 2), self.local(self.local(v, i, kind), i, "z")),
                   (F(1, 2), self.local(self.local(v, i, "z"), i, kind)))

    def qdot(self, v, i, j):
        return add((1, self.quadrupole(self.local(v, j, "z"), i, "z")),
                   (F(1, 2), self.quadrupole(self.local(v, j, "minus"), i, "plus")),
                   (F(1, 2), self.quadrupole(self.local(v, j, "plus"), i, "minus")))

    def x(self, v, i, j):
        return add((1, self.qdot(v, i, j)), (-1, self.qdot(v, j, i)))

    def dipole(self, v, i, j):
        return add((1, self.local(v, i, "z")), (-1, self.local(v, j, "z")))

    def matrix(self, n, op):
        return {key: op({key: F(1)}) for key in product(range(self.d), repeat=n)}

    def metric(self, key):
        result = 1
        for k in key:
            result *= factorial(k)*factorial(self.twice_spin)//factorial(self.twice_spin-k)
        return result

    def inner(self, a, b):
        return sum((value*b[col].get(row, 0)*F(self.metric(row), self.metric(col))
                    for col, entries in a.items() for row, value in entries.items()), F(0))


def main():
    started = time.perf_counter()
    OUT.mkdir(exist_ok=False)
    protocol = {"scope": "h=sum T_i dot T_(i+1), R=(bY+uD)/sqrt(ell*N), finite even PBC N>=4",
        "conditions": "one local spin-s irrep, b nonzero, only dipole-amplitude retuning",
        "arithmetic": "Fraction polynomial identities plus direct unnormalized-basis matrices",
        "symbolic_proof": "finite-difference identity for power sums, not polynomial fitting",
        "direct_spin_checks": ["1/2", "1", "3/2", "2", "5/2", "3"],
        "wall_limit_seconds": 60, "new_microscopic_models_computed": False}
    (OUT/"protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    polys = symbolic_gram()
    rows = []
    for two_s in range(1, 7):
        assert time.perf_counter()-started < 60
        spin = Spin(two_s)
        h = lambda v: spin.dot(v, 0, 1)
        dipole = lambda v: spin.dipole(v, 0, 1)
        x = lambda v: spin.x(v, 0, 1)
        identity = spin.matrix(2, lambda v: add((1, x(v)),
            (-F(1, 2), h(dipole(v))), (-F(1, 2), dipole(h(v))), (-spin.s*(spin.s+1)/3, dipole(v))))
        assert all(not entries for entries in identity.values())
        cd = spin.matrix(2, lambda v: old.commutator(v, h, dipole))
        cx = spin.matrix(2, lambda v: old.commutator(v, h, x))
        dd, dx, xx = spin.inner(cd, cd), spin.inner(cd, cx), spin.inner(cx, cx)
        minimum = xx-dx*dx/dd
        for name, actual in (("dd", dd), ("dx", dx), ("xx", xx), ("minimum", minimum)):
            assert actual == sum(coefficient*spin.d**k for k, coefficient in enumerate(polys[name]))
        for op in (cd, cx):
            for keep in ((0,), (1,)):
                assert all(not entries for entries in old.partial_trace(op, keep).values())
        cross = spin.matrix(3, lambda v: old.commutator(v, lambda w: spin.dot(w, 0, 1),
                                                       lambda w: spin.x(w, 1, 2)))
        for keep in ((0, 1), (0, 2), (1, 2)):
            assert all(not entries for entries in old.partial_trace(cross, keep).values())
        rows.append({"spin": str(spin.s), "d": spin.d, "dd": str(dd), "dx": str(dx), "xx": str(xx),
                     "minimum": str(minimum), "bound_times_ell_over_b2": str(minimum/spin.d**2),
                     "bond_identity_exact": True, "partial_traces_exact": True})
    summary = {"passed": True, "symbolic_polynomial_proof": True, "direct_matrix_checks": rows,
        "Gdd": "d^2*(d^2-1)^2/18", "Gdx_over_Gdd": "(d^2-4)/12",
        "Gxx_over_Gdd": "7*(d^2-4)^2/360",
        "bond_minimum": "d^2*(d^2-1)^2*(d^2-4)^2/1440",
        "chain_lower_bound": "b^2*(d^2-1)^2*(d^2-4)^2/(1440*ell)",
        "doublet_bound": "0", "quartet_ell5_bound_over_b2": "9/2",
        "meaning": "positive for s>=1 conditional on b!=0 and stated probe form; not a universal bound for arbitrary spin chains",
        "not_claimed": ["arbitrary momentum", "thermodynamic finite-T intensity floor", "all higher-spin clusters have nonzero b"],
        "elapsed_seconds": time.perf_counter()-started}
    (OUT/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT/"polynomial_coefficients.json").write_text(json.dumps({k: [str(v) for v in p] for k, p in polys.items()}, indent=2), encoding="utf-8")
    paths = [Path(__file__), Path(old.__file__), Path(old.exact.__file__), *sorted(OUT.iterdir())]
    (OUT/"sha256.json").write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                              for p in paths}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
