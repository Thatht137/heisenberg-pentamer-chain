"""用精确五聚体约化预解式核验非零复合系数。"""

import hashlib
import json
import os
from pathlib import Path
import time

for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"

import sympy as sp
from sympy.polys.matrices import DomainMatrix

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "results/novelty_20261008/exact_pentamer_coefficients_v3"
R = sp.sqrt(7)
FIELD = sp.QQ.algebraic_field(R)


def exact(value):
    return FIELD.to_sympy(FIELD.from_sympy(value))


def reduce_matrix(matrix):
    return matrix.applyfunc(exact)


def zero(matrix):
    assert all(exact(v) == 0 for v in matrix)


def positive(value):
    value = exact(value)
    a, b = value.expand().coeff(R, 0), value.expand().coeff(R, 1)
    assert a.is_Rational and b.is_Rational
    bound = sp.Rational(2645 if b >= 0 else 2646, 1000)
    lower = a + b * bound
    assert lower > 0, value
    return str(exact(lower))


def cell():
    alpha = -(2 + R) / 6
    z, plus, minus = [], [], []
    for site in range(5):
        zz, pp = sp.zeros(32), sp.zeros(32)
        for state in range(32):
            zz[state, state] = sp.Rational(1, 2) - ((state >> site) & 1)
            if state & (1 << site):
                pp[state ^ (1 << site), state] = 1
        z.append(zz)
        plus.append(pp)
        minus.append(pp.T)
    h = sp.zeros(32)
    for i, coupling in enumerate((alpha, sp.S.One, sp.S.One, alpha)):
        h += coupling * (z[i] * z[i+1] + (plus[i]*minus[i+1] + minus[i]*plus[i+1])/2)
    return reduce_matrix(h), z, plus, minus


def main():
    start = time.perf_counter()
    OUT.mkdir(exist_ok=False)
    protocol = {
        "question": "Are the microscopic quartet coefficients exactly nonzero, rather than a floating-point tensor-fit residual?",
        "model": "Five spin-1/2 sites with bonds (alpha,1,1,alpha); alpha=-(2+sqrt(7))/6; q=pi.",
        "arithmetic": "Exact QQ(sqrt(7)); no reconstruction from floating-point coefficients.",
        "method": "Magnetization-block reduced resolvent; unnormalized SU(2) descendants and their exact dual basis.",
        "gates": ["rank-four eigenprojector", "strict local gap > 1/8 by exact LDL pivots",
                  "P B P = 0", "full projected tensor identities", "comparison to existing two-cell floating-point construction"],
        "limits": "One isolated cell only; this check does not establish literature priority or higher-order/thermodynamic claims.",
        "wall_limit_seconds": 180,
        "sympy_version": sp.__version__,
    }
    (OUT/"protocol.json").write_text(json.dumps(protocol, indent=2), encoding="utf-8")
    h, z, plus, minus = cell()
    energy = -(5 + 4*R)/12
    sectors = [[state for state in range(32) if bin(state).count("1") == n] for n in range(6)]
    top = (h.extract(sectors[1], sectors[1])-energy*sp.eye(5)).nullspace()
    assert len(top) == 1
    v = sp.zeros(32, 1)
    for row, state in enumerate(sectors[1]):
        v[state] = exact(top[0][row])
    lower = sum(minus, sp.zeros(32))
    vectors = [v]
    for _ in range(3):
        vectors.append(reduce_matrix(lower*vectors[-1]))
    basis = sp.Matrix.hstack(*vectors)
    norms = [exact((v.T*v)[0]) for v in vectors]
    dual = sp.diag(*[1/n for n in norms])*basis.T
    dual = reduce_matrix(dual)
    zero(dual*basis-sp.eye(4))
    projector = reduce_matrix(basis*dual)
    zero(projector*projector-projector)
    zero(h*projector-energy*projector)
    assert sp.trace(projector) == 4
    print("Exact quartet projector verified.", flush=True)

    resolvent = sp.zeros(32)
    gap_checks = []
    for states in sectors:
        hp = h.extract(states, states)
        pp = projector.extract(states, states)
        identity = sp.eye(len(states))
        shifted = reduce_matrix(hp-energy*identity+pp)
        inverse = DomainMatrix.from_Matrix(shifted).convert_to(FIELD).inv().to_Matrix()
        gg = reduce_matrix(inverse-pp)
        zero((hp-energy*identity)*gg-(identity-pp))
        zero(gg*pp)
        for i, row in enumerate(states):
            for j, col in enumerate(states):
                resolvent[row, col] = gg[i, j]
        certified = reduce_matrix(shifted-sp.Rational(1, 8)*(identity-pp))
        ll, uu, swaps = DomainMatrix.from_Matrix(certified).convert_to(FIELD).lu()
        assert not swaps
        ll, uu = ll.to_Matrix(), uu.to_Matrix()
        dd = sp.diag(*[uu[i, i] for i in range(len(states))])
        zero(uu-dd*ll.T)
        zero(ll*dd*ll.T-certified)
        bounds = [positive(dd[i, i]) for i in range(len(states))]
        gap_checks.append({"down_spins": bin(states[0]).count("1"), "dimension": len(states),
                           "ldl_positive_lower_bounds": bounds})
        print("Exact gap certificate: dimension", len(states), flush=True)
        assert time.perf_counter()-start < 180
    print("Exact resolvent and gap > 1/8 verified.", flush=True)

    probe = sum(((-1)**i*zz for i, zz in enumerate(z)), sp.zeros(32))
    zero(dual*probe*basis)
    tz = reduce_matrix(dual*sum(z, sp.zeros(32))*basis)
    tp = reduce_matrix(dual*sum(plus, sp.zeros(32))*basis)
    tm = reduce_matrix(dual*lower*basis)
    c = exact((dual*z[0]*basis)[0, 0]/tz[0, 0])
    zero(dual*z[0]*basis-c*tz)
    expected_c = (25+4*R)/108
    assert exact(c-expected_c) == 0

    tensor_z = reduce_matrix(dual*(probe*resolvent*z[4]+z[4]*resolvent*probe)*basis)
    scalar = exact((tensor_z[0, 0]+tensor_z[1, 1])/2)
    quadrupole = exact((tensor_z[0, 0]-tensor_z[1, 1])/2)
    for endpoint in (0, 4):
        for name, op, total in (("z", z[endpoint], tz), ("plus", plus[endpoint], tp), ("minus", minus[endpoint], tm)):
            tensor = reduce_matrix(dual*(probe*resolvent*op+op*resolvent*probe)*basis)
            q = (tz*total+total*tz)/2
            prediction = quadrupole*q
            if name == "z":
                prediction += (scalar-sp.Rational(5, 4)*quadrupole)*sp.eye(4)
            zero(tensor-prediction)
    a, b = exact(-c*scalar), exact(-c*quadrupole)
    positive_b = positive(b)
    print("Exact coefficients:", a, b, flush=True)

    # 仅在精确恒等式通过后比较旧数值实现。
    import dark_operator_expansion as numerical
    _, _, _, coefficients, _, _, diagnostics = numerical.effective_probe()
    errors = [abs(float(v)-float(expected)) for v, expected in zip(coefficients, (a, b))]
    assert max(errors) < 1e-12
    summary = {
        "passed": True, "energy_exact": str(energy),
        "highest_weight_basis_one_down_sites_0_to_4": [str(exact(vectors[0][1 << i])) for i in range(5)],
        "highest_weight_norm": str(norms[0]),
        "c1_exact": str(c),
        "scalar_local_tensor": str(scalar), "quadrupole_local_tensor": str(quadrupole),
        "a_exact": str(a), "b_exact": str(b),
        "a_float": float(a), "b_float": float(b),
        "strict_b_positive_lower_bound": positive_b,
        "strict_local_gap_lower_bound": "1/8",
        "gap_certificate": gap_checks,
        "full_tensor_identities": "Both endpoints; z, plus, minus components, full four-dimensional irrep.",
        "numeric_comparison_max_absolute_error": max(errors),
        "existing_two_cell_tensor_fit_error": diagnostics["fit_relative_error"],
        "independence_scope": "Exact bit-basis one-cell construction vs existing floating-point two-cell resolvent; same perturbative formula, not a different physical approximation.",
        "elapsed_seconds": time.perf_counter()-start,
    }
    (OUT/"summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    files = [Path(__file__), OUT/"protocol.json", OUT/"summary.json"]
    (OUT/"sha256.json").write_text(json.dumps({p.relative_to(ROOT).as_posix():
        hashlib.sha256(p.read_bytes()).hexdigest() for p in files}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
