"""检查均匀低带迹的谱矩不等式与有限频率权重界。"""

from fractions import Fraction as F
from pathlib import Path
import hashlib
import json
import time
import os

for name in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ[name] = "1"

import numpy as np
from scipy import sparse
from scipy.linalg import eigh

import check_general_spin_full_chain as chain

ROOT = chain.ROOT
OUT = ROOT / "results/novelty_20261008/uniform_trace_weight_bound"


def operators(twice_spin, n):
    d = twice_spin + 1
    s = twice_spin / 2
    c = s * (s + 1)
    t = chain.local_spins(twice_spin)
    q = [(t[2] @ t[a] + t[a] @ t[2]) / 2
         - (c / 3 * sparse.eye(d, format="csr") if a == 2 else 0) for a in range(3)]
    h = sparse.csr_matrix((d**n, d**n), dtype=complex)
    dipole, y = h.copy(), h.copy()
    for i in range(n):
        j = (i + 1) % n
        dipole += (-1)**i * chain.embed({i: t[2]}, n, d)
        for a in range(3):
            h += chain.embed({i: t[a], j: t[a]}, n, d)
            y += (-1)**i * (chain.embed({i: q[a], j: t[a]}, n, d)
                            - chain.embed({i: t[a], j: q[a]}, n, d))
    return h, dipole, y


def algebra_checks():
    # M2-(3c/2)M0 的广义归一化矩阵主子式。
    for c in (F(2), F(15, 4), F(6), F(35, 4), F(12)):
        bb, uu = (61*c - 42)/30, 7*c/6
        cross_square = F(4, 9)*c*(4*c - 3)
        determinant = bb*uu - cross_square
        assert determinant == c*(107*c - 54)/180 > 0
    degrees = {}
    for n in range(4, 66, 2):
        supports = [set((i+k) % n for k in range(-1, 4)) for i in range(n)]
        degree = max(sum(bool(a & b) for b in supports) for a in supports)
        assert degree <= 9
        degrees[str(n)] = degree
    quartet_total = F(197, 259200)
    quartet_window = F(197, 1036800)
    assert quartet_total / 4 == quartet_window
    return {"determinant": "c*(107*c-54)/180; positive for c>=2",
            "sampled_support_overlap_degrees": degrees,
            "quartet_total_bound_over_b2": str(quartet_total),
            "quartet_window_bound_over_b2": str(quartet_window)}


def run_case(twice_spin, n):
    h, dipole, y = operators(twice_spin, n)
    s = twice_spin / 2
    c, d = s*(s+1), twice_spin + 1
    ell, b = 5., 1.
    threshold = np.sqrt(3*c/4)
    floor = b*b*(4*c-3)*(86*c-27)/(3732480*ell)
    spectral = None
    if n == 4:
        energy, vectors = eigh(h.toarray(), check_finite=False)
        delta = energy[:, None] - energy[None, :]
        dy = vectors.conj().T @ (y @ vectors) / np.sqrt(ell*n)
        dd = vectors.conj().T @ (dipole @ vectors) / np.sqrt(ell*n)
        spectral = (delta, dy, dd)
    rows = []
    for u in (-10., -1., 0., 3., 10.):
        r = (b*y + u*dipole) / np.sqrt(ell*n)
        comm = h @ r - r @ h
        second = h @ comm - comm @ h
        m0, m2, m4 = [chain.inner(a, a)/d**n for a in (r, comm, second)]
        m0_expected = (c*u*u/3 + b*b*c*c*(4*c-3)/27)/ell
        m2_expected = (b*b*c*c*(4*c-3)*(86*c-27)/810
                       + 8*c*c/9*(u+b*(4*c-3)/12)**2)/ell
        assert abs(m0-m0_expected) < 1e-10 * max(1, m0_expected)
        assert abs(m2-m2_expected) < 1e-10 * max(1, m2_expected)
        assert m2 >= 1.5*c*m0 - 1e-10
        assert m4 <= 576*c*c*m2 + 1e-9
        row = {"u_over_b": u, "M0": m0, "M2": m2, "M4": m4,
               "M4_over_M2": m4/m2, "locality_ratio_bound": 576*c*c,
               "positive_window_floor": floor}
        if spectral is not None:
            delta, dy, dd = spectral
            weights = abs(b*dy + u*dd)**2 / d**n
            window = float(weights[delta > threshold].sum())
            total = float(weights[delta > 1e-9].sum())
            assert abs(float((delta**2*weights).sum())-m2) < 1e-9*max(1, m2)
            assert abs(float((delta**4*weights).sum())-m4) < 1e-9*max(1, m4)
            assert window >= (m2-threshold**2*m0)**2/(2*m4) - 1e-10
            assert window >= floor and total >= 4*floor
            row.update({"positive_weight": total, "positive_window_weight": window,
                        "direct_moment_bound": (m2-threshold**2*m0)**2/(2*m4)})
        rows.append(row)
    optimal_window = None
    if spectral is not None:
        delta, dy, dd = spectral
        mask = delta > threshold
        a = float((abs(dd[mask])**2).sum()) / d**n
        cross = float((dy[mask].conj()*dd[mask]).sum().real) / d**n
        u = -cross/a
        optimum = float((abs((dy+u*dd)[mask])**2).sum()) / d**n
        assert optimum >= floor
        optimal_window = {"u_over_b": u, "minimum": optimum, "floor": floor,
                          "minimum_over_floor": optimum/floor}
    return {"spin": s, "N": n, "dimension": d**n, "ell": ell, "b": b,
            "window_threshold": threshold, "rows": rows, "window_optimum": optimal_window}


def main():
    started = time.perf_counter()
    OUT.mkdir(exist_ok=False)
    protocol = {"scope": "uniform low-energy effective trace; even PBC N>=4; specified dipole-composite probe",
        "cases": [[2, 4], [2, 6], [3, 4], [3, 6]], "spin_encoding": "twice spin",
        "wall_limit_seconds": 120, "largest_dimension": 4096, "eigensolves": "N=4 only, at most 256 states",
        "test_type": "bounded checks of independently derived inequalities; not a finite-size fit",
        "window": "epsilon_f-epsilon_i > sqrt(3*s*(s+1)/4)",
        "formula": "C_window >= b^2*(4c-3)*(86c-27)/(3732480*ell)",
        "not_claimed": ["arbitrary finite-temperature floor", "uniform microscopic weak-coupling expansion with N", "experimental detectability"]}
    (OUT/"protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    exact = algebra_checks()
    cases = []
    for twice_spin, n in protocol["cases"]:
        assert time.perf_counter()-started < 120
        cases.append(run_case(twice_spin, n))
    summary = {"passed": True, "algebra": exact, "cases": cases,
               "elapsed_seconds": time.perf_counter()-started,
               "proof_basis": "local norm inequality plus at most nine overlapping five-site supports; analytic for all finite even N>=4"}
    (OUT/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    paths = [Path(__file__), Path(chain.__file__), *sorted(OUT.iterdir())]
    (OUT/"sha256.json").write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                             for p in paths}, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "elapsed_seconds": summary["elapsed_seconds"],
                      "algebra": exact, "window_optima": [r["window_optimum"] for r in cases if r["window_optimum"]]}, indent=2))


if __name__ == "__main__":
    main()
