"""在同一五聚体模型的双重态侧检验有效探针的自旋秩限制。"""

from __future__ import annotations

import hashlib
import itertools
import time
from pathlib import Path

import validate_dark_multicell as original
import numpy as np
from scipy.linalg import eigh
from scipy.optimize import brentq
from scipy.sparse.linalg import LinearOperator, eigsh

reference, ROOT = original.reference, original.ROOT
OUT = ROOT / "results/novelty_20261004/doublet_control"
Q = .6*np.pi


def amplitude(alpha):
    cell, _, _ = reference.local_projection(alpha, np.linspace(0,2*np.pi,41))
    assert abs(cell["s"]-.5) < 1e-10
    return float(np.dot(cell["c"],np.cos(Q*(np.arange(5)-2))))


def effective_probe(alpha):
    half = {"x": np.array([[0,1],[1,0]])/2,
            "y": np.array([[0,-1j],[1j,0]])/2, "z": np.diag([.5,-.5])}
    spins = {a:[reference.site_operator(op,i) for i in range(5)] for a,op in half.items()}
    h = sum(c*spins[a][i]@spins[a][i+1] for i,c in enumerate((alpha,1,1,alpha)) for a in half)
    e,u = eigh(h)
    assert np.count_nonzero(abs(e-e[0])<1e-10) == 2
    p = u[:,:2]
    _,rotation = eigh(p.conj().T@sum(spins["z"])@p)
    up = p@rotation[:,-1]
    down = (sum(spins["x"])-1j*sum(spins["y"]))@up
    u = np.column_stack((up,down,u[:,2:]))
    ops = {a:[u.conj().T@op@u for op in values] for a,values in spins.items()}
    t = {a:sum(values)[:2,:2] for a,values in ops.items()}
    probe = sum(np.exp(1j*Q*(i-2))*op for i,op in enumerate(ops["z"]))
    unit = np.eye(32)[:,:2]
    v = sum(np.kron(ops[a][4][:,:2],ops[a][0][:,:2]) for a in t)
    gaps = (e[:,None]+e[None,:]-2*e[0]).ravel()
    resolvent = np.zeros_like(gaps)
    resolvent[gaps>1e-10] = 1/gaps[gaps>1e-10]
    rv = resolvent[:,None]*v
    # 非厄米 Fourier 探针的出入块不能互换为共轭。
    kl = -np.kron(probe[:2,:],unit.T)@rv-rv.conj().T@np.kron(probe[:,:2],unit)
    kr = -np.kron(unit.T,probe[:2,:])@rv-rv.conj().T@np.kron(unit,probe[:,:2])
    left_basis,right_basis = np.kron(np.eye(2),t["z"]),np.kron(t["z"],np.eye(2))
    al = np.vdot(left_basis,kl)/np.vdot(left_basis,left_basis)
    ar = np.vdot(right_basis,kr)/np.vdot(right_basis,right_basis)
    gamma = -(al+ar)
    residual = max(np.linalg.norm(kl-al*left_basis),np.linalg.norm(kr-ar*right_basis))
    assert residual < 1e-10 and abs(gamma.imag) < 1e-10
    quadrupole_norm = max(np.linalg.norm((t["z"]@ta+ta@t["z"])/2
                        -(.25*np.eye(2) if a=="z" else 0)) for a,ta in t.items())
    assert quadrupole_norm < 1e-10 and np.linalg.norm(probe[:2,:2]) < 1e-10
    c1 = float(ops["z"][0][0,0].real/.5)
    return {"gamma": float(gamma.real), "local_gap": float(e[2]-e[0]), "c1":c1,
            "left_scalar_real":float(al.real),"left_scalar_imag":float(al.imag),
            "right_scalar_real":float(ar.real),"right_scalar_imag":float(ar.imag),
            "operator_fit_error":float(residual),"quadrupole_norm":float(quadrupole_norm),
            "P_O_P_norm":float(np.linalg.norm(probe[:2,:2]))}


def main():
    start = time.perf_counter()
    OUT.mkdir(parents=True,exist_ok=False)
    alpha = brentq(amplitude,1.,1.5,xtol=1e-13)
    theory = effective_probe(alpha)
    derivative = (amplitude(alpha+1e-5)-amplitude(alpha-1e-5))/2e-5
    kappa = -theory["gamma"]/derivative
    reference.write_json(OUT/"protocol.json",{
        "model":"unchanged pentamer chain; expand positive alpha beyond old plotting interval",
        "root_bracket":[1.,1.5],"alpha":alpha,"q_over_pi":.6,"effective_q_over_pi":3.,
        "L":20,"cells":4,"boundary":"PBC","eigenpairs":7,"expected_low_excitations":5,
        "g_values":[.01,.02,.04,.08],"g_definition":"beta/Delta at isolated doublet zero",
        "kappa":float(kappa),"amplitude_derivative":float(derivative),
        "hypothesis":"doublet has no rank-2 tensor; first-order probe is scalar D and removable",
        "finite_path_prediction":"fixed root W=O(beta^2); linear retuning W=O(beta^4) or smaller",
        "first_three_fixed_slope_range":[1.8,2.2],"first_three_retuned_slope_range":[3.7,4.3],
        "numeric_residual_gate":1e-9,"threads":1,"wall_limit_seconds":1200,
        "scope":"operator algebra plus finite-chain exponent; no universal nonzero fourth-order coefficient"})
    reference.write_json(OUT/"local_theory.json",theory)
    h0 = original.sector_matrix(20,10,original.bonds(20,alpha,0))
    hb = original.sector_matrix(20,10,[(i,(i+1)%20,1.) for i in (4,9,14,19)])
    ha = original.sector_matrix(20,10,[(i,i+1,1.) for i in range(19) if i%5 in (0,3)])
    states = np.array([sum(1<<i for i in inds) for inds in itertools.combinations(range(20),10)])
    sz = np.column_stack([((states>>i)&1)-.5 for i in range(20)])
    op = sz@np.exp(1j*Q*np.arange(20))/np.sqrt(20)
    rows,lines = [],[]
    for g in (.01,.02,.04,.08):
        beta = g*theory["local_gap"]
        for mode in ("fixed","retuned"):
            shift = kappa*beta if mode=="retuned" else 0.
            h = h0+beta*hb+shift*ha
            def matvec(x):
                if time.perf_counter()-start>1200:
                    raise TimeoutError("达到双重态对照时间边界")
                return h@x
            print(f"START doublet g={g} mode={mode}",flush=True)
            e,v = eigsh(LinearOperator(h.shape,matvec=matvec,dtype=np.float64),k=7,
                        which="SA",ncv=60,tol=1e-13,maxiter=5000,
                        v0=np.random.default_rng(20261006).normal(size=len(states)))
            order=np.argsort(e)
            e,v=e[order],v[:,order]
            gaps=e-e[0]
            errors=np.linalg.norm(h@v-v*e,axis=0)
            low=(gaps>1e-9)&(gaps<theory["local_gap"]/2)
            source=op*v[:,0]
            source-=v[:,0]*np.vdot(v[:,0],source)
            weights=abs(v.T@source)**2
            weight=float(weights[low].sum())
            row={"g":g,"mode":mode,"alpha":float(alpha+shift),"beta":beta,
                 "W_low":weight,"W_over_beta2":weight/beta**2,"W_over_beta4":weight/beta**4,
                 "predicted_fixed_W_over_beta2":theory["gamma"]**2*2/15,
                 "low_states":int(low.sum()),"next_state":float(gaps[6]),
                 "ground_residual":float(errors[0]),"max_residual":float(errors.max()),
                 "numeric_pass":bool(low.sum()==5 and errors.max()<1e-9),
                 "elapsed_seconds":time.perf_counter()-start}
            rows.append(row)
            lines.extend({"g":g,"mode":mode,"level":i,"omega":float(gaps[i]),
                          "weight":float(weights[i]),"residual":float(errors[i])} for i in range(7))
            reference.write_csv(OUT/"comparisons.csv",rows)
            reference.write_csv(OUT/"spectral_lines.csv",lines)
            print(row,flush=True)
    slopes={}
    for mode in ("fixed","retuned"):
        selected=[r for r in rows if r["mode"]==mode][:3]
        slopes[mode]=float(np.polyfit(np.log([r["beta"] for r in selected]),np.log([r["W_low"] for r in selected]),1)[0])
    passed=all(r["numeric_pass"] for r in rows) and 1.8<slopes["fixed"]<2.2 and 3.7<slopes["retuned"]<4.3
    reference.write_json(OUT/"summary.json",{"all_gates_pass":passed,"slopes_first_three":slopes,
                         "elapsed_seconds":time.perf_counter()-start,"bulk_claim":False})
    reference.write_json(OUT/"sha256.json",{
        str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__),Path(original.__file__),Path(reference.__file__),
                  ROOT/"scripts/autoresearch_v5/analyze_negative_phase_independent_observables.py"]
        +sorted(OUT.iterdir()) if p.is_file()})
    if not passed:
        raise SystemExit(1)


if __name__=="__main__":
    main()
