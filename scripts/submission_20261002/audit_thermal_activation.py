"""用独立全空间装配复核四胞热激活及简并基变换不变性。"""

import os
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.linalg import eigh

import check_thermal_compensation as thermal

ROOT, reference = thermal.ROOT, thermal.reference
OUT=ROOT/"results/novelty_20261008/thermal_activation_audit_v2"


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    alpha=-(2+np.sqrt(7))/6
    t,quad,c1,lc,rc,gap,error=thermal.local.local_probe(alpha,np.pi)
    n,d=4,4
    def embed(op,i):
        return np.kron(np.kron(np.eye(d**i),op),np.eye(d**(n-i-1)))
    spins={a:[embed(op,i) for i in range(n)] for a,op in t.items()}
    quads={a:[embed(op,i) for i in range(n)] for a,op in quad.items()}
    h=np.zeros((d**n,d**n),complex)
    k=h.copy()
    for i in range(n):
        j=(i+1)%n
        h+=sum(spins[a][i]@spins[a][j] for a in t)
        k+=(-1)**i*(lc[0]*spins["z"][j]+lc[1]*sum(quads[a][i]@spins[a][j] for a in t))
        k+=(-1)**j*(rc[0]*spins["z"][i]+rc[1]*sum(spins[a][i]@quads[a][j] for a in t))
    k/=np.sqrt(5*n)
    dop=sum((-1)**i*spins["z"][i] for i in range(n))/np.sqrt(5*n)
    e,v=eigh(h)
    de,ke=v.conj().T@dop@v,v.conj().T@k@v
    delta=e[:,None]-e[None,:]
    data=[(e,de,ke,delta)]
    zero=thermal.weight(data,0.)
    triplets=np.flatnonzero(abs(e-e[0]-1)<1e-9)
    assert len(triplets)==3 and abs(e[0]+12)<1e-10
    residual=ke-zero["lambda"]*de
    prefactor=float(np.sum((delta[:,triplets]>1e-9)*abs(residual[:,triplets])**2))
    rng=np.random.default_rng(20261008)
    rotated=v.copy()
    begin=0
    while begin<len(e):
        end=begin+1
        while end<len(e) and abs(e[end]-e[begin])<1e-9:
            end+=1
        q,_=np.linalg.qr(rng.normal(size=(end-begin,end-begin))+1j*rng.normal(size=(end-begin,end-begin)))
        rotated[:,begin:end]=v[:,begin:end]@q
        begin=end
    rotated_data=[(e,rotated.conj().T@dop@rotated,rotated.conj().T@k@rotated,delta)]
    baseline=json.loads((thermal.OUT/"summary.json").read_text())["cases"][0]
    rows=[]
    for tau in (0.,.025,.05,.1,.2,1.6):
        row=thermal.weight(data,tau,zero["lambda"])
        alt=thermal.weight(rotated_data,tau,zero["lambda"])
        row["degenerate_rotation_error"]=abs(row["C_min"]-alt["C_min"])
        row["activation_coefficient"]=row["C_min"]*np.exp(1/tau) if tau>0 else None
        row["sector_full_relative_error"]=None
        if tau==1.6:
            row["sector_full_relative_error"]=abs(row["C_min"]/baseline["T_over_Jeff_1p6"]["C_min"]-1)
            assert row["sector_full_relative_error"]<1e-10
        assert row["degenerate_rotation_error"]<1e-12
        rows.append(row)
    assert abs(rows[1]["activation_coefficient"]/prefactor-1)<1e-7
    assert abs(rows[2]["activation_coefficient"]/prefactor-1)<1e-6
    comm=h@(k-zero["lambda"]*dop)-(k-zero["lambda"]*dop)@h
    reference.write_csv(OUT/"activation_checks.csv",rows)
    summary={"all_gates_pass":True,"independent_embedding":True,"independent_eigensolver":False,
        "spin":1.5,"cells":4,"alpha":alpha,"ground_energy_over_Jeff":float(e[0]),
        "first_thermal_gap_over_Jeff":1.,"first_thermal_multiplicity":len(triplets),
        "activation_prefactor":prefactor,"commutator_norm_at_zeroT_optimum":float(np.linalg.norm(comm)),
        "activation_law":"Cmin(T) = A exp(-Jeff/T) + o(exp(-Jeff/T)) in the leading effective N=4 model",
        "finite_beta_microscopic_claim":False,"rows":rows}
    reference.write_json(OUT/"summary.json",summary)
    files=[Path(__file__),Path(thermal.__file__),thermal.OUT/"summary.json",*sorted(OUT.iterdir())]
    reference.write_json(OUT/"sha256.json",{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files if p.is_file()})
    print(json.dumps(summary,indent=2))


if __name__=="__main__":
    main()
