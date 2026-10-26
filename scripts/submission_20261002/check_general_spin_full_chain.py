"""用独立稀疏矩阵检验整链谱矩公式。"""

from pathlib import Path
import hashlib
import json
import time

import numpy as np
from scipy import sparse

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/novelty_20261008/general_spin_chain_check"


def local_spins(twice_spin):
    s = twice_spin / 2
    m = np.arange(s, -s - 1, -1)
    up = sparse.diags(np.sqrt(s * (s + 1) - m[1:] * (m[1:] + 1)), 1,
                      shape=(twice_spin + 1, twice_spin + 1), format="csr")
    return [(up + up.T) / 2, (up - up.T) / (2j), sparse.diags(m, format="csr")]


def embed(factors, n, d):
    result = sparse.csr_matrix([[1.]])
    identity = sparse.eye(d, format="csr")
    for i in range(n):
        result = sparse.kron(result, factors.get(i, identity), format="csr")
    return result


def inner(a, b):
    return float(a.conjugate().multiply(b).sum().real)


def check(twice_spin, n):
    d = twice_spin + 1
    s = twice_spin / 2
    c = s * (s + 1)
    t = local_spins(twice_spin)
    q = [(t[2] @ t[a] + t[a] @ t[2]) / 2
         - (c / 3 * sparse.eye(d, format="csr") if a == 2 else 0) for a in range(3)]
    h = sparse.csr_matrix((d**n, d**n), dtype=complex)
    dipole = h.copy()
    y = h.copy()
    for i in range(n):
        j = (i + 1) % n
        dipole += (-1)**i * embed({i: t[2]}, n, d)
        for a in range(3):
            h += embed({i: t[a], j: t[a]}, n, d)
            y += (-1)**i * (embed({i: q[a], j: t[a]}, n, d)
                            - embed({i: t[a], j: q[a]}, n, d))
    cd, cy = h @ dipole - dipole @ h, h @ y - y @ h
    dd, dy, yy = [v / (n * d**n) for v in (inner(cd, cd), inner(cd, cy), inner(cy, cy))]
    u = -dy / dd
    minimum = yy - dy * dy / dd
    expected = c*c*(4*c - 3)*(86*c - 27)/810
    target_dd = (d*d - 1)**2 / 18
    assert abs(dd - target_dd) < 1e-11 * max(1, target_dd)
    assert abs(u + (d*d - 4) / 12) < 1e-12
    assert abs(minimum - expected) < 1e-11 * max(1, expected)
    samples = []
    for offset in (-2., .5, 3.):
        actual = yy + 2 * offset * dy + offset * offset * dd
        prediction = expected + target_dd * (offset + (d*d - 4)/12)**2
        assert abs(actual - prediction) < 1e-11 * max(1, prediction)
        samples.append({"u_over_b": offset, "M2_times_ell_over_b2": actual, "prediction": prediction})
    return {"spin": s, "N": n, "dimension": d**n, "optimum_u_over_b": u,
            "minimum_M2_times_ell_over_b2": minimum, "prediction": expected,
            "absolute_error": abs(minimum - expected), "quadratic_checks": samples}


def main():
    start = time.perf_counter()
    OUT.mkdir(exist_ok=False)
    protocol = {"cases": [[s, n] for s in (1, 2, 3) for n in (4, 6)],
                "spin_encoding": "twice spin", "wall_limit_seconds": 60,
                "maximum_dimension": 4096, "eigensolves": 0,
                "assembly": "orthonormal Cartesian spin and quadrupole Kronecker products; no proof-module imports",
                "observable": "full-chain uniform-trace second moment, ell=b=1",
                "tolerance": "1e-11 absolute or relative, as specified in source"}
    (OUT / "protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    rows = []
    for two_s, n in protocol["cases"]:
        assert time.perf_counter() - start < 60
        rows.append(check(two_s, n))
    summary = {"passed": True, "results": rows, "elapsed_seconds": time.perf_counter() - start,
               "scope": "numerical assembly check, not a replacement for the all-spin algebraic proof"}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    paths = [Path(__file__), *sorted(OUT.iterdir())]
    (OUT / "sha256.json").write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                                  for p in paths}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
