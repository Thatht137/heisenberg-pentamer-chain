"""十自旋完整热谱对照，不截断热配分函数。"""

import os
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"

import hashlib
import itertools
import json
import time
from pathlib import Path

import numpy as np
from scipy.linalg import eigh
from scipy.optimize import brentq

import check_thermal_compensation as thermal
import validate_dark_multicell as micro

ROOT, reference = thermal.ROOT, thermal.reference
OUT=ROOT/"results/novelty_20261008/thermal_microscopic_two_cells"


def microscopic(alpha,beta,q,temperature,gap,deadline):
    blocks=[]
    largest_error=0.
    for up in range(11):
        assert time.perf_counter()<deadline
        states=np.array([sum(1<<i for i in inds) for inds in itertools.combinations(range(10),up)])
        h=micro.sector_matrix(10,up,micro.bonds(10,alpha,beta)+[(9,0,beta)]).toarray()
        e,v=eigh(h)
        error=float(np.linalg.norm(h@v-v*e)/max(1.,np.linalg.norm(h)))
        largest_error=max(largest_error,error)
        z=np.column_stack([((states>>i)&1)-.5 for i in range(10)])
        diagonal=z@np.exp(1j*q*np.arange(10))/np.sqrt(10)
        op=v.conj().T@(diagonal[:,None]*v)
        blocks.append((e,op))
    e0=min(e[0] for e,op in blocks)
    populations=[np.exp(-(e-e0)/temperature) for e,op in blocks]
    partition=sum(p.sum() for p in populations)
    weight=missing=balance=0.
    retained=0
    upper=0.
    next_energy=np.inf
    for (e,op),p in zip(blocks,populations):
        low=e-e0<gap/2
        retained+=int(low.sum())
        if low.any():
            upper=max(upper,float(max((e-e0)[low])))
        if (~low).any():
            next_energy=min(next_energy,float(min((e-e0)[~low])))
        delta=e[:,None]-e[None,:]
        window=low[:,None]&low[None,:]
        plus=window&(delta>1e-9)
        minus=window&(delta< -1e-9)
        intens=abs(op)**2
        weight+=float(np.sum(plus*p[None,:]*intens)/partition)
        missing+=float(p[~low].sum()/partition)
        reverse=float(np.sum(minus*p[None,:]*intens)/partition)
        expected=float(np.sum(plus*p[None,:]*intens*np.exp(-np.maximum(delta,0)/temperature))/partition)
        balance=max(balance,abs(reverse-expected))
    return {"W_positive_low":weight,"thermal_population_outside_band":missing,
        "retained_states_all_sectors":retained,"band_top":upper,"next_state":next_energy,
        "max_eigen_residual":largest_error,"detailed_balance_error":balance}


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    started=time.perf_counter()
    reference.write_json(OUT/"protocol.json",{
        "L":10,"cells":2,"boundary":"PBC; two distinct microscopic intercell bonds",
        "all_sectors":True,"total_dimension":1024,"largest_block":252,
        "g_values":[.005,.01,.02],"T_over_Jeff_values":[.4,1.6],
        "retuning":"alpha_root + kappa(T/Jeff)*beta from the effective two-cell model",
        "temperature_definition":"T=tau*beta*c1(alpha_root)^2; kB=1",
        "band_cutoff":"both initial and final energies below E0+Delta_root/2",
        "partition_function":"all 1024 microscopic states",
        "eigen_residual_gate":1e-10,"band_population_leakage_gate":1e-8,
        "quartet_weakest_coefficient_relative_gate":.05,
        "slope_windows":{"quartet":[1.8,2.2],"doublet":[3.7,4.3]},
        "threads":1,"wall_limit_seconds":180,"scope":"finite microscopic two-cell check, not long-chain validation"})
    rows=[]
    for spin,q,bracket in ((1.5,np.pi,(-1.,-.5)),(.5,3*np.pi/5,(.5,2.))):
        alpha=brentq(lambda a:thermal.local.amplitude(a,q),*bracket,xtol=1e-13)
        t,quad,c1,lc,rc,gap,error=thermal.local.local_probe(alpha,q)
        data,checks=thermal.blocks(2,int(2*spin+1),t,quad,c1,lc,rc,q)
        derivative=(thermal.local.amplitude(alpha+1e-5,q)-thermal.local.amplitude(alpha-1e-5,q))/2e-5
        for tau in (.4,1.6):
            predicted=thermal.weight(data,tau)
            kappa=-predicted["lambda"]/derivative
            for g in (.005,.01,.02):
                beta=g*gap
                shifted=alpha+kappa*beta
                temperature=tau*beta*c1*c1
                row=microscopic(shifted,beta,q,temperature,gap,started+180)
                row.update({"spin":spin,"g":g,"T_over_Jeff":tau,"alpha_root":alpha,
                    "alpha_retuned":shifted,"beta":beta,"T":temperature,"kappa":kappa,
                    "C_predicted":predicted["C_min"],"W_over_beta2":row["W_positive_low"]/beta**2,
                    "W_over_beta4":row["W_positive_low"]/beta**4,
                    "coefficient_relative_error":abs(row["W_positive_low"]/beta**2/predicted["C_min"]-1) if spin==1.5 else None,
                    "elapsed_seconds":time.perf_counter()-started})
                row["numerical_pass"]=bool(row["retained_states_all_sectors"]==int(2*spin+1)**2
                    and row["max_eigen_residual"]<1e-10 and row["thermal_population_outside_band"]<1e-8
                    and row["detailed_balance_error"]<1e-12)
                rows.append(row)
                reference.write_csv(OUT/"comparisons.csv",rows)
                print(json.dumps(row),flush=True)
    slopes=[]
    for spin in (1.5,.5):
        for tau in (.4,1.6):
            case=[r for r in rows if r["spin"]==spin and r["T_over_Jeff"]==tau]
            slope=float(np.polyfit(np.log([r["beta"] for r in case]),np.log([r["W_positive_low"] for r in case]),1)[0])
            slopes.append({"spin":spin,"T_over_Jeff":tau,"slope":slope,
                "pass":bool(1.8<slope<2.2 if spin==1.5 else 3.7<slope<4.3)})
    prediction_pass=all(r["coefficient_relative_error"]<.05 for r in rows if r["spin"]==1.5 and r["g"]==.005)
    passed=all(r["numerical_pass"] for r in rows) and all(s["pass"] for s in slopes) and prediction_pass
    reference.write_json(OUT/"summary.json",{"all_gates_pass":passed,"slopes":slopes,
        "weakest_prediction_pass":prediction_pass,"elapsed_seconds":time.perf_counter()-started,
        "microscopic_four_cell_thermal_claim":False})
    files=[Path(__file__),Path(micro.__file__),Path(thermal.__file__),Path(thermal.local.__file__),
        ROOT/"scripts/autoresearch_v5/analyze_negative_phase_independent_observables.py",*sorted(OUT.iterdir())]
    reference.write_json(OUT/"sha256.json",{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files if p.is_file()})
    if not passed:
        raise SystemExit(1)


if __name__=="__main__":
    main()
