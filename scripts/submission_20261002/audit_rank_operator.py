"""检查双重态算符级抵消，并复算最弱微观信号。"""

from __future__ import annotations

import csv
import hashlib
import itertools
import json
import time
from pathlib import Path

import numpy as np
from scipy.sparse.linalg import LinearOperator, eigsh

import probe_rank_geometry as geometry
import validate_dark_multicell as microscopic

ROOT, reference = geometry.ROOT, geometry.reference
BASE = ROOT / "results/novelty_20261004"
OUT = BASE / "rank_operator_audit"


def main():
    start = time.perf_counter()
    OUT.mkdir(exist_ok=False)
    cases = json.loads((BASE / "rank_geometry_probe/summary.json").read_text())["cases"]
    with (BASE / "same_ring_microscopic/comparisons.csv").open(newline="") as handle:
        baseline = {(float(r["spin"]), float(r["g"])): r for r in csv.DictReader(handle)
                    if r["mode"] == "retuned"}
    reference.write_json(OUT / "protocol.json", {
        "operator_check":"full retained Hilbert space, not just ground-state sources",
        "doublet_operator_relative_residual_gate":1e-10,
        "g_values":[.005,.01], "repeat_seed":773119,"repeat_ncv":120,
        "repeat_eigsh_tolerance":1e-14,"repeat_weight_relative_gate":1e-3,
        "eigen_residual_gate":1e-11,"threads":1,"wall_limit_seconds":180,
        "scope":"same Hamiltonian assembly, independent numerical restart; not an independent method"})
    operators, repeats = [], []
    states = np.array([sum(1<<i for i in inds) for inds in itertools.combinations(range(15),8)])
    sz = np.column_stack([((states>>i)&1)-.5 for i in range(15)])
    hb = microscopic.sector_matrix(15,8,[(i,(i+1)%15,1.) for i in (4,9,14)])
    ha = microscopic.sector_matrix(15,8,[(i,i+1,1.) for i in range(14) if i%5 in (0,3)])
    for case in cases:
        alpha, q = case["alpha"], case["q_over_pi"]*np.pi
        t, quad, _, lc, rc, _, _ = geometry.local_probe(alpha,q)
        d = len(t["z"])
        def embed(op,i):
            return np.kron(np.kron(np.eye(d**i),op),np.eye(d**(2-i)))
        spins = {a:[embed(op,i) for i in range(3)] for a,op in t.items()}
        quads = {a:[embed(op,i) for i in range(3)] for a,op in quad.items()}
        phases = np.exp(5j*q*np.arange(3))
        dop = sum(phases[i]*spins["z"][i] for i in range(3))/np.sqrt(15)
        kop = np.zeros_like(dop)
        for i in range(3):
            j = (i+1)%3
            kop += phases[i]*(lc[0]*spins["z"][j]+lc[1]*sum(quads[a][i]@spins[a][j] for a in t))
            kop += phases[j]*(rc[0]*spins["z"][i]+rc[1]*sum(spins[a][i]@quads[a][j] for a in t))
        kop /= np.sqrt(15)
        lam = np.vdot(dop,kop)/np.vdot(dop,dop)
        residual = float(np.linalg.norm(kop+case["kappa"]*case["amplitude_derivative"]*dop)/np.linalg.norm(kop))
        operators.append({"spin":case["spin"],"full_dimension":len(dop),
            "retuned_operator_relative_norm":residual,
            "best_complex_operator_fit_residual":float(np.linalg.norm(kop-lam*dop)/np.linalg.norm(kop)),
            "doublet_gate":bool(residual<1e-10) if case["spin"]==.5 else None})
        h0 = microscopic.sector_matrix(15,8,microscopic.bonds(15,alpha,0))
        probe = sz@np.exp(1j*q*np.arange(15))/np.sqrt(15)
        for g in (.005,.01):
            beta = g*case["local_gap"]
            h = h0+beta*hb+case["kappa"]*beta*ha
            def matvec(x):
                if time.perf_counter()-start>180:
                    raise TimeoutError("达到弱信号复核时间边界")
                return h@x
            e,v = eigsh(LinearOperator(h.shape,matvec=matvec,dtype=np.float64),
                        k=case["sector_dim"]+6,which="SA",tol=1e-14,ncv=120,
                        v0=np.random.default_rng(773119).normal(size=len(states)))
            order = np.argsort(e)
            e,v = e[order],v[:,order]
            gaps = e-e[0]
            ng = int(np.count_nonzero(abs(gaps)<1e-9))
            low = (gaps>1e-9)&(gaps<case["local_gap"]/2)
            weights = np.sum(abs(v.T@(probe[:,None]*v[:,:ng]))**2,axis=1)/ng
            w = float(weights[low].sum())
            error = abs(w/float(baseline[case["spin"],g]["W_low"])-1)
            eigerr = float(np.linalg.norm(h@v-v*e,axis=0).max())
            repeats.append({"spin":case["spin"],"g":g,"W_repeat":w,
                "relative_weight_difference":error,"eigen_residual":eigerr,
                "ground_count":ng,"low_excitations":int(low.sum()),
                "pass":bool(error<1e-3 and eigerr<1e-11 and ng==2 and low.sum()==case["sector_dim"]-2)})
    passed = all(r["pass"] for r in repeats) and all(r["doublet_gate"] is not False for r in operators)
    reference.write_json(OUT / "summary.json", {"operator_checks":operators,"repeats":repeats,
        "all_gates_pass":passed,"elapsed_seconds":time.perf_counter()-start})
    files = [Path(__file__),Path(geometry.__file__),Path(microscopic.__file__),
             BASE/"rank_geometry_probe/summary.json",BASE/"same_ring_microscopic/comparisons.csv",
             *sorted(OUT.iterdir())]
    reference.write_json(OUT/"sha256.json",{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files if p.is_file()})
    print(json.dumps({"all_gates_pass":passed,"operators":operators,"repeats":repeats},indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
