"""完整分块热迹检验算符抵消与基态偶然抵消。"""

import os
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"

import csv
import hashlib
import json
import time
from pathlib import Path

import numpy as np
from scipy.linalg import eigh
from scipy.optimize import brentq

import check_even_rank_sources as even

local, reference, ROOT = even.local, even.reference, even.ROOT
OUT = ROOT / "results/novelty_20261008/thermal_compensation"


def blocks(n, d, t, quad, c1, lc, rc, q):
    all_states = np.arange(d**n, dtype=np.int64)
    powers = d**np.arange(n-1, -1, -1)
    all_digits = (all_states[:, None]//powers) % d
    totals = all_digits.sum(axis=1)
    phases = np.exp(5j*q*np.arange(n))
    link = sum(np.kron(op, op) for op in t.values())
    kl = lc[0]*np.kron(np.eye(d), t["z"])+lc[1]*sum(np.kron(quad[a], t[a]) for a in t)
    kr = rc[0]*np.kron(t["z"], np.eye(d))+rc[1]*sum(np.kron(t[a], quad[a]) for a in t)
    result, checks = [], []
    for total in range(n*(d-1)+1):
        states = all_states[totals == total]
        digits = all_digits[totals == total]
        lookup = np.full(d**n, -1, dtype=np.int32)
        lookup[states] = np.arange(len(states))
        data = states, digits, powers, lookup
        h = sum(even.bond(link, i, (i+1)%n, data, d) for i in range(n)).toarray()
        k = sum(phases[i]*even.bond(kl, i, (i+1)%n, data, d)
                +phases[(i+1)%n]*even.bond(kr, i, (i+1)%n, data, d)
                for i in range(n)).toarray()/np.sqrt(5*n)
        diagonal = np.sum(((d-1)/2-digits)*phases, axis=1)/np.sqrt(5*n)
        assert np.linalg.norm(h-h.conj().T)<1e-10
        assert np.linalg.norm(k-k.conj().T)<1e-10
        e, v = eigh(h)
        de = v.conj().T@(diagonal[:, None]*v)
        ke = v.conj().T@k@v
        delta = e[:, None]-e[None, :]
        residual = float(np.linalg.norm(h@v-v*e)/max(1.,np.linalg.norm(h)))
        # 列是初态，行是末态；剔除完整等能子空间。
        checks.append({"dimension":len(states), "eigen_residual":residual,
            "D_trace_error":float(abs(np.sum(abs(de)**2)-np.sum(abs(diagonal)**2))),
            "K_trace_error":float(abs(np.sum(abs(ke)**2)-np.sum(abs(k)**2)))})
        result.append((e, de, ke, delta))
    assert sum(len(b[0]) for b in result) == d**n
    assert max(x["eigen_residual"] for x in checks)<1e-11
    assert max(max(x["D_trace_error"], x["K_trace_error"]) for x in checks)<1e-9
    return result, checks


def weight(data, temperature, fixed_lambda=None):
    ground = min(b[0][0] for b in data)
    ps = [(abs(b[0]-ground)<1e-9).astype(float) if temperature == 0
          else np.exp(-(b[0]-ground)/temperature) for b in data]
    partition = sum(p.sum() for p in ps)
    dd = kk = dk = 0.
    for (e, d, k, delta), p in zip(data, ps):
        weights = (delta>1e-9)*p[None, :]/partition
        dd += float(np.sum(weights*abs(d)**2))
        kk += float(np.sum(weights*abs(k)**2))
        dk += float(np.sum(weights*(d.conj()*k).real))
    lam = dk/dd
    minimum = fixed = balance = 0.
    for (e, d, k, delta), p in zip(data, ps):
        mask = delta>1e-9
        w = mask*p[None, :]/partition
        source = k-lam*d
        minimum += float(np.sum(w*abs(source)**2))
        fixed += float(np.sum(w*abs(k-(lam if fixed_lambda is None else fixed_lambda)*d)**2))
        if temperature>0:
            neg = float(np.sum((delta < -1e-9)*p[None, :]*abs(source)**2)/partition)
            thermal_factor = np.exp(-np.maximum(delta, 0)/temperature)
            predicted = float(np.sum(w*thermal_factor*abs(source)**2))
            balance = max(balance, abs(neg-predicted))
    assert abs(minimum-(kk-dk*dk/dd))<1e-10
    assert balance<1e-10
    return {"T_over_Jeff":temperature, "C_fixed_root":kk, "C_min":minimum,
        "C_fixed_zeroT_retuning":fixed,"D_positive_weight":dd,
        "lambda":lam,"detailed_balance_error":balance,
        "partition_shifted":float(partition)}


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    reference.write_json(OUT/"protocol.json",{
        "exploratory":True,"cells":[4,6],"spins":[.5,1.5],"boundary":"PBC",
        "Q_over_pi":1,"temperature_unit":"Jeff=beta*c1(alpha_root)^2",
        "temperature_scope":"fixed T/Jeff as beta tends to zero; T much less than local gap",
        "observable":"positive-frequency low-band integrated weight divided by beta^2",
        "all_Sz_sectors":True,"exclude_all_degenerate_transitions_abs_tolerance":1e-9,
        "wall_limit_seconds":300,"threads":1,
        "solver":"existing project embedding plus scipy.linalg.eigh; no package migration",
        "physics_outcome_not_an_acceptance_gate":True})
    rows, summaries = [], []
    for s, q, bracket in ((1.5,np.pi,(-1.,-.5)),(.5,3*np.pi/5,(.5,2.))):
        alpha = brentq(lambda a:local.amplitude(a,q), *bracket, xtol=1e-13)
        t, quad, c1, lc, rc, gap, error = local.local_probe(alpha,q)
        derivative=(local.amplitude(alpha+1e-5,q)-local.amplitude(alpha-1e-5,q))/2e-5
        for n in (4,6):
            assert time.perf_counter()-started<300
            data, checks=blocks(n,int(2*s+1),t,quad,c1,lc,rc,q)
            zero=weight(data,0.)
            case=[]
            for tau in (0.,.025,.05,.1,.2,.4,.8,1.6,3.2,10.):
                row=weight(data,tau,zero["lambda"])
                row.update({"spin":s,"cells":n,"alpha":alpha,"q_over_pi":q/np.pi,
                    "c1_squared":c1*c1,"local_gap":gap,"kappa":-row["lambda"]/derivative})
                rows.append(row); case.append(row)
            if s==.5:
                assert max(r["C_min"] for r in case)<1e-20
            if s==1.5 and n==6:
                assert abs(zero["C_min"]/.000443299659099-1)<1e-7
            if s==1.5 and n==4:
                assert zero["C_min"]<1e-20
            summaries.append({"spin":s,"cells":n,"alpha":alpha,"zero_T":zero,
                "T_over_Jeff_1p6":case[7],"numerical_checks":checks})
            print(json.dumps(summaries[-1]),flush=True)
            reference.write_csv(OUT/"thermal_weights.csv",rows)
    reference.write_json(OUT/"summary.json",{"numerical_gates_pass":True,
        "cases":summaries,"elapsed_seconds":time.perf_counter()-started,
        "finite_temperature_microscopic_validation":False,"thermodynamic_limit_claim":False})
    files=[Path(__file__),Path(even.__file__),Path(local.__file__),Path(local.dark.__file__),
           Path(reference.__file__),*sorted(OUT.iterdir())]
    reference.write_json(OUT/"sha256.json",{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files if p.is_file()})


if __name__ == "__main__":
    main()
