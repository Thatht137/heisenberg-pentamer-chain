"""精确计算一般自旋周期链的均匀热迹二阶谱矩。"""

from fractions import Fraction as F
from itertools import product
from math import comb
from pathlib import Path
import hashlib
import json
import time

import prove_general_spin_obstruction as general
import audit_four_cell_thermal_window as audit
import validate_thermal_four_cells as micro

ROOT = general.ROOT
OUT = ROOT/"results/novelty_20261008/general_spin_moment"
add, plus, times = general.add, general.plus, general.times


def epsilon(a, b, c):
    if len({a, b, c}) < 3:
        return 0
    return 1 if (a, b, c) in ((0, 1, 2), (1, 2, 0), (2, 0, 1)) else -1


def qmetric(a, b, c, d):
    return F(int(a == c and b == d)+int(a == d and b == c))-F(2, 3)*int(a == b and c == d)


def tensor_contractions():
    ends, middle = {}, {}
    z = 2
    for a, b, c in product(range(3), repeat=3):
        if epsilon(a, b, c):
            ends[(z, b, c, a)] = epsilon(a, b, c)
        for key, value in (((a, c, a, b), -epsilon(b, z, c)),
                           ((a, c, b, b), -epsilon(a, z, c))):
            middle[key] = middle.get(key, 0)+value
    ke = sum(F(v*w)*qmetric(a, b, ap, bp) for (a, b, c, d), v in ends.items()
             for (ap, bp, cp, dp), w in ends.items() if c == cp and d == dp)
    km = sum(F(v*w)*qmetric(b, c, bp, cp) for (a, b, c, d), v in middle.items()
             for (ap, bp, cp, dp), w in middle.items() if a == ap and d == dp)
    assert ke == F(20, 3) and km == 20
    return ke, km


def trace_polynomial_check():
    d = [F(0), F(1)]
    s = [F(-1, 2), F(1, 2)]
    p = times(s, plus((1, s), (1, [F(1)])))
    powers = [[F(1)]]
    for _ in range(4):
        powers.append(times(powers[-1], s))
    traces = {}
    for n in (2, 4):
        terms = []
        for k in range(n+1):
            summation = d if k == 0 else general.power_sum(k)
            terms.append((F(comb(n, k)*(-1)**k), times(powers[n-k], summation)))
        traces[n] = plus(*terms)
    assert traces[2] == plus((F(1, 3), times(d, p)))
    assert traces[4] == plus((F(1, 15), times(times(d, p), plus((3, p), (-1, [F(1)])))))
    return True


def main():
    started = time.perf_counter()
    OUT.mkdir(exist_ok=False)
    protocol = {"scope": "fixed finite even N>=4; uniform nearest-neighbor PBC; R=(bY+uD)/sqrt(ell*N)",
        "definition": "M2=d^(-N) Tr([h,R]^dagger [h,R]); two-sided dimensionless uniform-trace moment",
        "minimization": "real u only; b fixed and nonzero",
        "arithmetic": "Fraction tensor contractions and polynomial identities",
        "matrix_checks_twice_spin": [1, 2, 3, 4, 5, 6],
        "microscopic_check": "previous N4 fixed zero-T retuning only, not a microscopic moment-optimized trajectory",
        "wall_limit_seconds": 60, "new_eigensolves": False}
    (OUT/"protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    ke, km = tensor_contractions()
    assert trace_polynomial_check()
    rows = []
    for twice_spin in range(1, 7):
        assert time.perf_counter()-started < 60
        spin = general.Spin(twice_spin)
        c = spin.s*(spin.s+1)
        z = spin.matrix(3, lambda v: add(
            (1, general.old.commutator(v, lambda w: spin.dot(w, 1, 2), lambda w: spin.x(w, 0, 1))),
            (-1, general.old.commutator(v, lambda w: spin.dot(w, 0, 1), lambda w: spin.x(w, 1, 2)))))
        norm = spin.inner(z, z)
        trace_t = spin.d*c/3
        trace_q = spin.d*c*(4*c-3)/60
        formula = (2*ke+km)*trace_t**2*trace_q
        assert norm == formula == F(5, 81)*spin.d**3*c**3*(4*c-3)
        bond_min = F(spin.d**2*(spin.d**2-1)**2*(spin.d**2-4)**2, 1440)
        exact_moment = bond_min/spin.d**2+norm/spin.d**3
        assert exact_moment == c*c*(4*c-3)*(86*c-27)/810
        rows.append({"spin": str(spin.s), "three_site_norm": str(norm),
                     "minimum_M2_times_ell_over_b2": str(exact_moment)})
    # 既有微观矩阵直接求矩，不需要划分近零频率。
    raw = audit.read_rows(audit.SOURCE/"comparisons.csv")
    b = .1236117648014558
    predictions = F(837, 16)*b*b
    comparisons = []
    for g in (.000625, .00125, .0025):
        beta = g*float(raw[0]["local_gap"])
        jeff = beta*.10855197721304
        blocks = audit.load_blocks(g)
        moment = sum(mult*float((abs(op)**2*((e[:, None]-e[None, :])/jeff)**2).sum())
                     for e, op, spin, mult in blocks)/(256*beta**2)
        comparisons.append({"g": g, "M2_over_beta2": moment, "leading_prediction": float(predictions),
                            "relative_error": abs(moment/float(predictions)-1)})
    assert comparisons[0]["relative_error"] < .02
    assert comparisons[0]["relative_error"] < comparisons[1]["relative_error"] < comparisons[2]["relative_error"]
    summary = {"passed": True, "trace_polynomial_identities": True,
        "rank_pattern_contractions": {"QTT": str(ke), "TQT": str(km), "TTQ": str(ke)},
        "exact_spin_checks": rows, "minimum_u_over_b": "-(d^2-4)/12",
        "M2_min": "b^2*s^2*(s+1)^2*(4*s*(s+1)-3)*(86*s*(s+1)-27)/(810*ell)",
        "M2_full": "M2_min + (d^2-1)^2/(18*ell)*(u+b*(d^2-4)/12)^2",
        "quartet_ell5_M2_min_over_b2": "197/16",
        "quartet_zeroT_retuning_M2_over_b2": "837/16",
        "microscopic_fixed_zeroT_retuning": comparisons,
        "not_claimed": ["thermal integrated-weight floor", "arbitrary microscopic cluster", "finite momentum acceptance robustness"],
        "elapsed_seconds": time.perf_counter()-started}
    (OUT/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    files = [Path(__file__), Path(general.__file__), Path(audit.__file__),
             *sorted(audit.SOURCE.glob("*.npz")), *sorted(OUT.iterdir())]
    (OUT/"sha256.json").write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                              for p in files}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
