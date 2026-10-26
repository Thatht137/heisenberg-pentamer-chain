"""在相同补偿参数下用偶数周期链排除奇数环特例。"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import eigsh

import probe_rank_geometry as local

ROOT, reference = local.ROOT, local.reference
BASE = ROOT/"results/novelty_20261004"
OUT = BASE/"rank_even_effective"


def sector(count,d):
    full=np.arange(d**count,dtype=np.int64)
    powers=d**np.arange(count-1,-1,-1)
    digits=(full[:,None]//powers[None,:])%d
    target=.5 if count%2 else 0.
    states=full[abs(np.sum((d-1)/2-digits,axis=1)-target)<1e-10]
    digits=(states[:,None]//powers[None,:])%d
    lookup=np.full(d**count,-1,dtype=np.int32)
    lookup[states]=np.arange(len(states))
    return states,digits,powers,lookup


def bond(op,i,j,data,d):
    states,digits,powers,lookup=data
    rows,cols,values=[],[],[]
    labels=d*digits[:,i]+digits[:,j]
    for col in range(d*d):
        selected=np.flatnonzero(labels==col)
        for row in np.flatnonzero(abs(op[:,col])>1e-13):
            target=states[selected]+(row//d-col//d)*powers[i]+(row%d-col%d)*powers[j]
            assert np.all(lookup[target]>=0)
            rows.append(lookup[target]); cols.append(selected)
            values.append(np.full(len(selected),op[row,col],dtype=complex))
    return coo_matrix((np.concatenate(values),(np.concatenate(rows),np.concatenate(cols))),
                      shape=(len(states),len(states))).tocsr()


def main():
    start=time.perf_counter()
    OUT.mkdir(exist_ok=False)
    cases=json.loads((BASE/"rank_geometry_probe/summary.json").read_text())["cases"]
    reference.write_json(OUT/"protocol.json",{
        "cells":[3,6],"boundary":"PBC","same_parameters_as_microscopic_three_cell_test":True,
        "complex_fourier_probe_preserved":True,"n3_cross_check_gate":1e-9,
        "eigen_residual_gate":1e-10,"doublet_zero_gate":1e-20,
        "threads":1,"wall_limit_seconds":60,"scope":"effective models, not microscopic L=30 ED"})
    rows,exports=[],[]
    for case in cases:
        alpha,q=case["alpha"],case["q_over_pi"]*np.pi
        t,quad,c1,lc,rc,gap,error=local.local_probe(alpha,q)
        d=len(t["z"])
        kl=lc[0]*np.kron(np.eye(d),t["z"])+lc[1]*sum(np.kron(quad[a],t[a]) for a in t)
        kr=rc[0]*np.kron(t["z"],np.eye(d))+rc[1]*sum(np.kron(t[a],quad[a]) for a in t)
        link=c1*c1*sum(np.kron(op,op) for op in t.values())
        exported={"spin":case["spin"],"alpha":alpha,"q_over_pi":case["q_over_pi"],
                  "c1":c1,"local_gap":gap,"A_prime":case["amplitude_derivative"]}
        for name,value in zip(("a_left","b_left","a_right","b_right"),(*lc,*rc)):
            exported[name+"_real"]=float(value.real)
            exported[name+"_imag"]=float(value.imag)
        exports.append(exported)
        for count in (3,6):
            assert time.perf_counter()-start<60
            data=sector(count,d)
            phase=np.exp(5j*q*np.arange(count))
            h=sum(bond(link,i,(i+1)%count,data,d) for i in range(count))
            k=sum(phase[i]*bond(kl,i,(i+1)%count,data,d)+phase[(i+1)%count]*bond(kr,i,(i+1)%count,data,d)
                  for i in range(count))/np.sqrt(5*count)
            assert np.max(abs(h.data.imag))<1e-10
            h=h.real
            if len(data[0])<10:
                e,v=np.linalg.eigh(h.toarray())
            else:
                e,v=eigsh(h,k=4,which="SA",tol=1e-13,ncv=min(40,len(data[0])),
                    v0=np.random.default_rng(20261009).normal(size=len(data[0])))
                order=np.argsort(e)
                e,v=e[order],v[:,order]
            ng=int(np.count_nonzero(abs(e-e[0])<1e-10))
            ground=v[:,:ng]
            diagonal=np.sum(((d-1)/2-data[1])*phase[None,:],axis=1)/np.sqrt(5*count)
            ds=diagonal[:,None]*ground
            ks=k@ground
            ds-=ground@(ground.conj().T@ds)
            ks-=ground@(ground.conj().T@ks)
            dd=np.vdot(ds,ds).real/ng
            kk=np.vdot(ks,ks).real/ng
            dk=np.vdot(ds,ks)/ng
            lam=dk.real/dd
            residual=ks-lam*ds
            minimum=float(np.vdot(residual,residual).real/ng)
            def mean_energy(source):
                norm=np.vdot(source,source).real
                return float(np.vdot(source,h@source-e[0]*source).real/norm) if norm>1e-20 else None
            eigerr=float(np.linalg.norm(h@v-v*e,axis=0).max())
            row={"spin":case["spin"],"cells":count,"sector_dimension":len(data[0]),
                "ground_count":ng,"W_fixed_over_beta2":float(kk),"W_min_over_beta2":minimum,
                "lambda_real":float(lam),"lambda_imag":float(dk.imag/dd),
                "kappa":float(-lam/case["amplitude_derivative"]),"eigen_residual":eigerr,
                "mean_fixed_over_beta":mean_energy(ks),"mean_retuned_over_beta":mean_energy(residual),
                "n3_cross_check_error":None}
            assert eigerr<1e-10 and abs(dk.imag/dd)<1e-9
            if count==3:
                row["n3_cross_check_error"]=max(abs(minimum-case["W_min_over_beta2"]),
                    abs(kk-case["W_fixed_over_beta2"]),abs(lam-case["lambda_real"]))
                assert row["n3_cross_check_error"]<1e-9
            if case["spin"]==.5:
                assert minimum<1e-20
            rows.append(row)
    reference.write_csv(OUT/"comparisons.csv",rows)
    reference.write_csv(OUT/"local_probe_coefficients.csv",exports)
    reference.write_json(OUT/"summary.json",{"all_gates_pass":True,"rows":rows,"elapsed_seconds":time.perf_counter()-start,
        "same_ring_frustration_not_required_in_effective_model":True,"microscopic_long_chain_claim":False})
    files=[Path(__file__),Path(local.__file__),BASE/"rank_geometry_probe/summary.json",*sorted(OUT.iterdir())]
    reference.write_json(OUT/"sha256.json",{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files if p.is_file()})
    print(json.dumps(rows,indent=2))


if __name__=="__main__":
    main()
